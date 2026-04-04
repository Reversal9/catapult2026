import { useEffect, useMemo, useRef, useState } from 'react'
import Globe from 'react-globe.gl'
import './App.css'

const SOLAR_MODELS = ['SunForge SF-450', 'HelioMax HX-620', 'Atlas Bifacial AB-700']
const WIND_MODELS = ['AeroSpin 2MW', 'VentoCore 3.5MW', 'SkyGrid 5MW']
const PIN_COLORS = { p1: '#76f5c8', p2: '#ffd07c' }

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))
const normLng = (lng) => {
  let value = lng
  while (value > 180) value -= 360
  while (value < -180) value += 360
  return value
}

const toDmsPart = (raw, isLat) => {
  const value = Math.abs(raw)
  const deg = Math.floor(value)
  const minsFull = (value - deg) * 60
  const min = Math.floor(minsFull)
  const sec = (minsFull - min) * 60
  const hemi = isLat ? (raw >= 0 ? 'N' : 'S') : raw >= 0 ? 'E' : 'W'
  return `${deg}°${String(min).padStart(2, '0')}'${sec.toFixed(1)}"${hemi}`
}

const formatDmsPair = ({ lat, lng }) => `${toDmsPart(lat, true)} ${toDmsPart(lng, false)}`

const DMS_RE =
  /^\s*(\d{1,3})[°\s]+(\d{1,2})['\s]+(\d{1,2}(?:\.\d+)?)"?\s*([NnSs])\s+(\d{1,3})[°\s]+(\d{1,2})['\s]+(\d{1,2}(?:\.\d+)?)"?\s*([EeWw])\s*$/

const parseDmsPair = (value) => {
  const m = value.match(DMS_RE)
  if (!m) return null

  const latDeg = Number(m[1])
  const latMin = Number(m[2])
  const latSec = Number(m[3])
  const latHem = m[4].toUpperCase()
  const lngDeg = Number(m[5])
  const lngMin = Number(m[6])
  const lngSec = Number(m[7])
  const lngHem = m[8].toUpperCase()

  if (
    latDeg > 90 ||
    lngDeg > 180 ||
    latMin >= 60 ||
    lngMin >= 60 ||
    latSec >= 60 ||
    lngSec >= 60
  ) {
    return null
  }

  let lat = latDeg + latMin / 60 + latSec / 3600
  let lng = lngDeg + lngMin / 60 + lngSec / 3600
  if (latHem === 'S') lat *= -1
  if (lngHem === 'W') lng *= -1

  return { lat, lng }
}

const boundsFromTwoCoords = (p1, p2) => ({
  south: Math.min(p1.lat, p2.lat),
  north: Math.max(p1.lat, p2.lat),
  west: Math.min(p1.lng, p2.lng),
  east: Math.max(p1.lng, p2.lng),
})

const rectangleFeature = (bounds) => ({
  type: 'Feature',
  properties: { mode: 'rectangle' },
  geometry: {
    type: 'Polygon',
    coordinates: [[
      [bounds.west, bounds.south],
      [bounds.east, bounds.south],
      [bounds.east, bounds.north],
      [bounds.west, bounds.north],
      [bounds.west, bounds.south],
    ]],
  },
})

const polygonFeature = (coords, mode = 'polygon') => ({
  type: 'Feature',
  properties: { mode },
  geometry: {
    type: 'Polygon',
    coordinates: [[...coords, coords[0]]],
  },
})

const linePath = (coords) => ({
  id: 'draft',
  points: coords.map((c) => [c.lat, c.lng]),
})

const circleFromTwoPoints = (center, edge, segments = 48) => {
  const latDist = edge.lat - center.lat
  const lonDist = (edge.lng - center.lng) * Math.cos((center.lat * Math.PI) / 180)
  const radiusDeg = Math.sqrt(latDist * latDist + lonDist * lonDist)
  if (radiusDeg <= 0.001) return null

  const points = Array.from({ length: segments }, (_, i) => {
    const angle = (i / segments) * Math.PI * 2
    const lat = center.lat + radiusDeg * Math.sin(angle)
    const lon = normLng(center.lng + (radiusDeg * Math.cos(angle)) / Math.cos((center.lat * Math.PI) / 180))
    return { lat: clamp(lat, -89.999, 89.999), lng: lon }
  })
  return points
}

const centerFromBounds = (bounds) => ({
  lat: (bounds.south + bounds.north) / 2,
  lng: (bounds.east + bounds.west) / 2,
})

const boundsFromFeature = (feature) => {
  const ring = feature.geometry.coordinates[0]
  const lats = ring.map((c) => c[1])
  const lngs = ring.map((c) => c[0])
  return {
    south: Math.min(...lats),
    north: Math.max(...lats),
    west: Math.min(...lngs),
    east: Math.max(...lngs),
  }
}

function App() {
  const globeRef = useRef(null)
  const [landingVisible, setLandingVisible] = useState(true)
  const [p1, setP1] = useState({ lat: 43.7238, lng: -80.194 })
  const [p2, setP2] = useState({ lat: 43.6118, lng: -80.0706 })
  const [p1Text, setP1Text] = useState(formatDmsPair({ lat: 43.7238, lng: -80.194 }))
  const [p2Text, setP2Text] = useState(formatDmsPair({ lat: 43.6118, lng: -80.0706 }))
  const [activeCoordField, setActiveCoordField] = useState(null)
  const [draggingPin, setDraggingPin] = useState(null)
  const [drawMode, setDrawMode] = useState('none')
  const [drawPoints, setDrawPoints] = useState([])
  const [regionFeature, setRegionFeature] = useState(null)
  const [equipmentTypes, setEquipmentTypes] = useState(['solar', 'turbine'])
  const [solarModelMode, setSolarModelMode] = useState('select')
  const [windModelMode, setWindModelMode] = useState('select')
  const [solarModel, setSolarModel] = useState(SOLAR_MODELS[0])
  const [windModel, setWindModel] = useState(WIND_MODELS[0])
  const [isSearching, setIsSearching] = useState(false)
  const [statsVisible, setStatsVisible] = useState(false)
  const [dummyStats, setDummyStats] = useState(null)
  const [userMovedCamera, setUserMovedCamera] = useState(false)
  const [searchCount, setSearchCount] = useState(0)
  const [cameraLock, setCameraLock] = useState(true)

  const rectangleFeatureMemo = useMemo(() => rectangleFeature(boundsFromTwoCoords(p1, p2)), [p1, p2])
  const activeFeature = regionFeature || rectangleFeatureMemo
  const selectionBounds = useMemo(() => boundsFromFeature(activeFeature), [activeFeature])

  const pinPoints = useMemo(
    () => [
      { id: 'p1', lat: p1.lat, lng: p1.lng, color: PIN_COLORS.p1 },
      { id: 'p2', lat: p2.lat, lng: p2.lng, color: PIN_COLORS.p2 },
    ],
    [p1, p2],
  )

  const drawPaths = useMemo(() => {
    if (!drawPoints.length) return []
    return [linePath(drawPoints)]
  }, [drawPoints])

  const onFirstInteraction = () => setLandingVisible(false)

  const setPin = (id, coord) => {
    const next = { lat: clamp(coord.lat, -89.999, 89.999), lng: normLng(coord.lng) }
    if (id === 'p1') {
      setP1(next)
      setP1Text(formatDmsPair(next))
    } else {
      setP2(next)
      setP2Text(formatDmsPair(next))
    }
  }

  const updateFromText = (id, value) => {
    if (id === 'p1') setP1Text(value)
    else setP2Text(value)
    const parsed = parseDmsPair(value)
    if (parsed) setPin(id, parsed)
  }

  const handleGlobeClick = (coords) => {
    onFirstInteraction()

    if (activeCoordField) {
      setPin(activeCoordField, coords)
      setActiveCoordField(null)
      return
    }

    if (drawMode === 'circle') {
      setDrawPoints((current) => {
        const next = [...current, coords]
        if (next.length === 2) {
          const circle = circleFromTwoPoints(next[0], next[1])
          if (circle) setRegionFeature(polygonFeature(circle, 'circle'))
          return []
        }
        return next
      })
      return
    }

    if (drawMode === 'polygon') {
      setDrawPoints((current) => [...current, coords])
    }
  }

  const finalizePolygon = () => {
    if (drawPoints.length < 3) return
    setRegionFeature(polygonFeature(drawPoints, 'polygon'))
    setDrawPoints([])
  }

  const clearDrawing = () => {
    setDrawMode('none')
    setDrawPoints([])
    setRegionFeature(null)
  }

  const toggleEquipment = (value) => {
    setEquipmentTypes((current) =>
      current.includes(value) ? current.filter((v) => v !== value) : [...current, value],
    )
  }

  const refocusSelection = (duration = 950) => {
    const center = centerFromBounds(selectionBounds)
    globeRef.current?.pointOfView({ lat: center.lat, lng: center.lng, altitude: 1.35 }, duration)
    setCameraLock(false)
    window.setTimeout(() => setCameraLock(true), duration + 60)
  }

  const runSearch = () => {
    setIsSearching(true)
    setStatsVisible(false)
    refocusSelection(1000)

    window.setTimeout(() => {
      const areaApprox = Math.max(
        1,
        Math.abs(selectionBounds.north - selectionBounds.south) *
          Math.abs(selectionBounds.east - selectionBounds.west) *
          8200,
      )
      const result = {
        category:
          equipmentTypes.length === 2
            ? 'hybrid'
            : equipmentTypes[0] === 'solar'
              ? 'solar'
              : 'wind',
        areaKm2: areaApprox,
        powerMWhYr: Math.round(areaApprox * (equipmentTypes.length === 2 ? 1300 : 890)),
        placements: Math.round(areaApprox * (equipmentTypes.includes('solar') ? 115 : 4.2)),
        rating: ['below average', 'average', 'better than average'][searchCount % 3],
      }
      setDummyStats(result)
      setSearchCount((count) => count + 1)
      setIsSearching(false)
      setStatsVisible(true)
    }, 1250)
  }

  useEffect(() => {
    if (!draggingPin) return

    const onMove = (event) => {
      const coords = globeRef.current?.toGlobeCoords(event.clientX, event.clientY)
      if (!coords) return
      setPin(draggingPin, coords)
    }

    const onUp = () => setDraggingPin(null)

    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [draggingPin])

  useEffect(() => {
    const onKey = () => setLandingVisible(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (userMovedCamera || isSearching || statsVisible) return
    refocusSelection(700)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectionBounds.south, selectionBounds.north, selectionBounds.west, selectionBounds.east])

  return (
    <main className="immersive-root" onPointerDown={onFirstInteraction}>
      <Globe
        ref={globeRef}
        width={window.innerWidth}
        height={window.innerHeight}
        globeImageUrl="https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
        bumpImageUrl="https://unpkg.com/three-globe/example/img/earth-topology.png"
        backgroundImageUrl="https://unpkg.com/three-globe/example/img/night-sky.png"
        polygonsData={[activeFeature]}
        polygonCapColor={() => 'rgba(118, 245, 200, 0.18)'}
        polygonSideColor={() => 'rgba(68, 200, 158, 0.25)'}
        polygonStrokeColor={() => '#7cf5cd'}
        polygonAltitude={() => 0.012}
        pointsData={pinPoints}
        pointLat="lat"
        pointLng="lng"
        pointColor="color"
        pointRadius={0.42}
        pointAltitude={() => 0.034}
        pointLabel={(d) => `${d.id.toUpperCase()}<br/>${formatDmsPair({ lat: d.lat, lng: d.lng })}`}
        onPointClick={(point) => {
          onFirstInteraction()
          setDraggingPin(point.id)
        }}
        pathsData={drawPaths}
        pathPoints="points"
        pathPointLat={(arr) => arr[0]}
        pathPointLng={(arr) => arr[1]}
        pathPointAlt={() => 0.015}
        pathStroke={() => 0.52}
        pathColor={() => '#ffd07c'}
        onGlobeClick={handleGlobeClick}
        onPolygonClick={() => {
          if (dummyStats) setStatsVisible((v) => !v)
        }}
        onZoom={() => {
          if (!cameraLock) return
          setUserMovedCamera(true)
        }}
      />

      {landingVisible && (
        <section className="landing-layer" role="dialog" aria-label="Welcome">
          <div className="landing-card">
            <p className="tag">CATAPULT 2026</p>
            <h1>Clean Energy Mapper</h1>
            <p>Predictive siting for solar and wind fields on an interactive earth canvas.</p>
            <small>Click, tap, or press any key to begin.</small>
          </div>
        </section>
      )}

      <section className="overlay-top">
        <h2>Region Selection</h2>
        <p>
          Set two corner coordinates, or draw a circle/polygon. Click a coordinate field then click the globe to pick.
        </p>
      </section>

      <section className="overlay-bottom">
        <div className="coord-row">
          <label>
            Position 1
            <input
              value={p1Text}
              onChange={(event) => updateFromText('p1', event.target.value)}
              onFocus={() => setActiveCoordField('p1')}
              placeholder={`43°43'25.7"N 80°11'38.5"W`}
            />
          </label>
          <label>
            Position 2
            <input
              value={p2Text}
              onChange={(event) => updateFromText('p2', event.target.value)}
              onFocus={() => setActiveCoordField('p2')}
              placeholder={`43°43'25.7"N 80°11'38.5"W`}
            />
          </label>
        </div>

        <div className="draw-row">
          <button type="button" className={drawMode === 'circle' ? 'active' : ''} onClick={() => setDrawMode('circle')}>
            Draw Circle
          </button>
          <button type="button" className={drawMode === 'polygon' ? 'active' : ''} onClick={() => setDrawMode('polygon')}>
            Draw Polygon
          </button>
          <button type="button" onClick={finalizePolygon}>
            Finalize Polygon
          </button>
          <button type="button" onClick={clearDrawing}>
            Clear Drawing
          </button>
        </div>

        <div className="equip-row">
          <span>Equipment Types</span>
          <label className="check">
            <input
              type="checkbox"
              checked={equipmentTypes.includes('solar')}
              onChange={() => toggleEquipment('solar')}
            />
            Solar
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={equipmentTypes.includes('turbine')}
              onChange={() => toggleEquipment('turbine')}
            />
            Turbine
          </label>
        </div>

        <div className="model-row">
          {equipmentTypes.includes('solar') && (
            <div className="model-card">
              <p>Solar Model</p>
              <div className="mode-row">
                <button
                  type="button"
                  className={solarModelMode === 'select' ? 'active' : ''}
                  onClick={() => setSolarModelMode('select')}
                >
                  Select
                </button>
                <button
                  type="button"
                  className={solarModelMode === 'type' ? 'active' : ''}
                  onClick={() => setSolarModelMode('type')}
                >
                  Type
                </button>
              </div>
              {solarModelMode === 'select' ? (
                <select value={solarModel} onChange={(event) => setSolarModel(event.target.value)}>
                  {SOLAR_MODELS.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              ) : (
                <input value={solarModel} onChange={(event) => setSolarModel(event.target.value)} />
              )}
            </div>
          )}

          {equipmentTypes.includes('turbine') && (
            <div className="model-card">
              <p>Turbine Model</p>
              <div className="mode-row">
                <button
                  type="button"
                  className={windModelMode === 'select' ? 'active' : ''}
                  onClick={() => setWindModelMode('select')}
                >
                  Select
                </button>
                <button
                  type="button"
                  className={windModelMode === 'type' ? 'active' : ''}
                  onClick={() => setWindModelMode('type')}
                >
                  Type
                </button>
              </div>
              {windModelMode === 'select' ? (
                <select value={windModel} onChange={(event) => setWindModel(event.target.value)}>
                  {WIND_MODELS.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              ) : (
                <input value={windModel} onChange={(event) => setWindModel(event.target.value)} />
              )}
            </div>
          )}
        </div>

        <div className="action-row">
          <button type="button" className="search" onClick={runSearch}>
            Search
          </button>
          {userMovedCamera && (
            <button type="button" className="refocus" onClick={() => {
              setUserMovedCamera(false)
              refocusSelection(850)
            }}>
              Refocus Region
            </button>
          )}
        </div>
      </section>

      {isSearching && (
        <div className="search-overlay">
          <div className="search-popup">
            <p>Zooming to region and calculating dummy stats...</p>
          </div>
        </div>
      )}

      {statsVisible && dummyStats && !isSearching && (
        <aside className="stats-popup" onClick={() => setStatsVisible(false)}>
          <h3>Simulation Result</h3>
          <p>Category: {dummyStats.category}</p>
          <p>Region Area: {dummyStats.areaKm2.toFixed(1)} km²</p>
          <p>Total Yield: {dummyStats.powerMWhYr.toLocaleString()} MWh/year</p>
          <p>Potential Placements: {dummyStats.placements.toLocaleString()}</p>
          <p>Performance: {dummyStats.rating}</p>
          <small>Click this panel or selected region to close/open.</small>
        </aside>
      )}
    </main>
  )
}

export default App
