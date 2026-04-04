import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Circle,
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  Popup,
  TileLayer,
  useMapEvents,
} from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

const SOLAR_MODELS = ['SunForge SF-450', 'HelioMax HX-620', 'Atlas Bifacial AB-700']
const WIND_MODELS = ['AeroSpin 2MW', 'VentoCore 3.5MW', 'SkyGrid 5MW']

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))
const normLng = (lng) => {
  let value = lng
  while (value > 180) value -= 360
  while (value < -180) value += 360
  return value
}

const DMS_RE =
  /^\s*(\d{1,3})[°\s]+(\d{1,2})['\s]+(\d{1,2}(?:\.\d+)?)"?\s*([NnSs])\s+(\d{1,3})[°\s]+(\d{1,2})['\s]+(\d{1,2}(?:\.\d+)?)"?\s*([EeWw])\s*$/

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

const parseDmsPair = (value) => {
  const match = value.match(DMS_RE)
  if (!match) {
    return { ok: false, message: 'Use DMS format: 43°43\'25.7"N 80°11\'38.5"W' }
  }

  const latDeg = Number(match[1])
  const latMin = Number(match[2])
  const latSec = Number(match[3])
  const latHem = match[4].toUpperCase()
  const lngDeg = Number(match[5])
  const lngMin = Number(match[6])
  const lngSec = Number(match[7])
  const lngHem = match[8].toUpperCase()

  if (latDeg > 90 || lngDeg > 180 || latMin >= 60 || lngMin >= 60 || latSec >= 60 || lngSec >= 60) {
    return { ok: false, message: 'Latitude/longitude values are out of range.' }
  }

  let lat = latDeg + latMin / 60 + latSec / 3600
  let lng = lngDeg + lngMin / 60 + lngSec / 3600
  if (latHem === 'S') lat *= -1
  if (lngHem === 'W') lng *= -1

  return { ok: true, value: { lat, lng } }
}

const haversineMeters = (a, b) => {
  const radius = 6371000
  const lat1 = (a.lat * Math.PI) / 180
  const lat2 = (b.lat * Math.PI) / 180
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const sinLat = Math.sin(dLat / 2)
  const sinLng = Math.sin(dLng / 2)
  const h = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLng * sinLng
  return 2 * radius * Math.asin(Math.min(1, Math.sqrt(h)))
}

const markerIcon = (color) =>
  L.divIcon({
    className: 'map-pin-icon',
    html: `<span style="--pin:${color}"></span>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  })

const rectangleFromTwoPoints = (a, b) => {
  const south = Math.min(a.lat, b.lat)
  const north = Math.max(a.lat, b.lat)
  const west = Math.min(a.lng, b.lng)
  const east = Math.max(a.lng, b.lng)
  return [
    [south, west],
    [south, east],
    [north, east],
    [north, west],
  ]
}

const centroid = (points) => {
  if (!points.length) return { lat: 0, lng: 0 }
  const lat = points.reduce((sum, p) => sum + p[0], 0) / points.length
  const lng = points.reduce((sum, p) => sum + p[1], 0) / points.length
  return { lat, lng }
}

const polygonAreaKm2 = (points) => {
  if (points.length < 3) return 0
  const c = centroid(points)
  const latScale = 111320
  const lngScale = 111320 * Math.cos((c.lat * Math.PI) / 180)
  let twiceArea = 0

  for (let i = 0; i < points.length; i += 1) {
    const j = (i + 1) % points.length
    const x1 = points[i][1] * lngScale
    const y1 = points[i][0] * latScale
    const x2 = points[j][1] * lngScale
    const y2 = points[j][0] * latScale
    twiceArea += x1 * y2 - x2 * y1
  }

  return Math.abs(twiceArea / 2) / 1_000_000
}

const regionAreaKm2 = (region) => {
  if (region.type === 'circle') {
    const radiusKm = region.radiusMeters / 1000
    return Math.PI * radiusKm * radiusKm
  }
  return polygonAreaKm2(region.points)
}

const regionCenter = (region) => {
  if (region.type === 'circle') return region.center
  return centroid(region.points)
}

function MapEvents({ onMapClick, onMapMove }) {
  useMapEvents({
    click: (event) => onMapClick(event.latlng),
    movestart: onMapMove,
    zoomstart: onMapMove,
  })
  return null
}

function App() {
  const mapRef = useRef(null)
  const popupRef = useRef(null)

  const [theme, setTheme] = useState('light')
  const [landingState, setLandingState] = useState('visible')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [activeCoordField, setActiveCoordField] = useState(null)
  const [userMovedMap, setUserMovedMap] = useState(false)

  const [p1, setP1] = useState({ lat: 43.7238, lng: -80.194 })
  const [p2, setP2] = useState({ lat: 43.6118, lng: -80.0706 })
  const [p1Text, setP1Text] = useState(formatDmsPair({ lat: 43.7238, lng: -80.194 }))
  const [p2Text, setP2Text] = useState(formatDmsPair({ lat: 43.6118, lng: -80.0706 }))
  const [p1Error, setP1Error] = useState('')
  const [p2Error, setP2Error] = useState('')

  const [drawMode, setDrawMode] = useState('circle')
  const [draftPoints, setDraftPoints] = useState([])
  const [region, setRegion] = useState({
    type: 'polygon',
    points: rectangleFromTwoPoints({ lat: 43.7238, lng: -80.194 }, { lat: 43.6118, lng: -80.0706 }),
    source: 'rectangle',
  })

  const [energyType, setEnergyType] = useState('')
  const [modelMode, setModelMode] = useState('predefined')
  const [selectedModel, setSelectedModel] = useState('')
  const [customModel, setCustomModel] = useState('')

  const [submitError, setSubmitError] = useState('')
  const [searching, setSearching] = useState(false)
  const [statsVisible, setStatsVisible] = useState(false)
  const [result, setResult] = useState(null)

  const tilesUrl =
    theme === 'light'
      ? 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
      : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
  const tileAttribution =
    theme === 'light'
      ? '&copy; OpenStreetMap contributors'
      : '&copy; OpenStreetMap contributors &copy; CARTO'

  const enterApp = useCallback(() => {
    if (landingState !== 'visible') return
    setLandingState('fading')
    window.setTimeout(() => setLandingState('hidden'), 320)
  }, [landingState])

  useEffect(() => {
    if (landingState === 'hidden') return undefined
    const onKey = () => enterApp()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [enterApp, landingState])

  const applyCoord = (id, coord) => {
    const next = { lat: clamp(coord.lat, -89.999, 89.999), lng: normLng(coord.lng) }

    if (id === 'p1') {
      setP1(next)
      setP1Text(formatDmsPair(next))
      setP1Error('')
    } else {
      setP2(next)
      setP2Text(formatDmsPair(next))
      setP2Error('')
    }

    setRegion({ type: 'polygon', points: rectangleFromTwoPoints(id === 'p1' ? next : p1, id === 'p2' ? next : p2), source: 'rectangle' })
  }

  const onCoordChange = (id, value) => {
    if (id === 'p1') setP1Text(value)
    else setP2Text(value)

    const parsed = parseDmsPair(value)
    if (!parsed.ok) {
      if (id === 'p1') setP1Error(parsed.message)
      else setP2Error(parsed.message)
      return
    }

    applyCoord(id, parsed.value)
  }

  const onMapClick = (latlng) => {
    if (landingState !== 'hidden') enterApp()

    if (activeCoordField) {
      applyCoord(activeCoordField, latlng)
      setActiveCoordField(null)
      return
    }

    if (!advancedOpen) return

    if (drawMode === 'circle') {
      setDraftPoints((current) => {
        const next = [...current, [latlng.lat, latlng.lng]]
        if (next.length === 2) {
          setRegion({
            type: 'circle',
            center: { lat: next[0][0], lng: next[0][1] },
            radiusMeters: haversineMeters(
              { lat: next[0][0], lng: next[0][1] },
              { lat: next[1][0], lng: next[1][1] },
            ),
            source: 'circle',
          })
          return []
        }
        return next
      })
      return
    }

    if (drawMode === 'polygon') {
      setDraftPoints((current) => [...current, [latlng.lat, latlng.lng]])
    }
  }

  const finalizePolygon = () => {
    if (draftPoints.length < 3) {
      setSubmitError('Polygon needs at least three points.')
      return
    }
    setRegion({ type: 'polygon', points: draftPoints, source: 'polygon' })
    setDraftPoints([])
    setSubmitError('')
  }

  const removeLastPolygonPoint = () => {
    setDraftPoints((current) => current.slice(0, -1))
  }

  const useRectangleRegion = () => {
    setRegion({ type: 'polygon', points: rectangleFromTwoPoints(p1, p2), source: 'rectangle' })
    setDraftPoints([])
    setSubmitError('')
  }

  const mapBounds = useMemo(() => {
    if (region.type === 'circle') {
      const c = region.center
      const radiusKm = region.radiusMeters / 1000
      const latDelta = radiusKm / 111.32
      const lngDelta = radiusKm / (111.32 * Math.max(0.25, Math.cos((c.lat * Math.PI) / 180)))
      return [
        [c.lat - latDelta, c.lng - lngDelta],
        [c.lat + latDelta, c.lng + lngDelta],
      ]
    }

    return L.latLngBounds(region.points)
  }, [region])

  const fitRegion = useCallback(
    (duration = 0.6) => {
      const map = mapRef.current
      if (!map) return

      map.fitBounds(mapBounds, {
        padding: [56, 56],
        animate: true,
        duration,
      })
    },
    [mapBounds],
  )

  const modelOptions = energyType === 'solar' ? SOLAR_MODELS : energyType === 'wind' ? WIND_MODELS : []
  const modelValue = modelMode === 'predefined' ? selectedModel : customModel.trim()

  const isReady =
    !!energyType && !!modelValue && !p1Error && !p2Error && !!region &&
    ((region.type !== 'circle' || region.radiusMeters > 1) && (region.type !== 'polygon' || region.points.length >= 3))

  const runAnalysis = () => {
    const errors = []
    if (p1Error || p2Error) errors.push('Fix coordinate formatting first.')
    if (!energyType) errors.push('Choose an energy type.')
    if (!modelValue) errors.push('Choose or enter a model.')
    if (!region) errors.push('Define a region on the map.')

    if (errors.length) {
      setSubmitError(errors.join(' '))
      return
    }

    setSubmitError('')
    setSearching(true)
    fitRegion(0.55)

    window.setTimeout(() => {
      const areaKm2 = Math.max(0.1, regionAreaKm2(region))
      const isSolar = energyType === 'solar'
      const placements = isSolar ? Math.floor(areaKm2 * 145) : Math.floor(areaKm2 * 4.6)
      const equipmentCost = isSolar ? placements * 900 : placements * 1_850_000
      const constructionCost = isSolar ? areaKm2 * 430_000 : areaKm2 * 680_000
      const annualMWh = isSolar ? areaKm2 * 1_180 : areaKm2 * 4_900

      setResult({
        areaKm2,
        placements,
        equipmentCost,
        constructionCost,
        annualMWh,
        label: isSolar ? 'Solar panels' : 'Wind turbines',
      })
      setSearching(false)
      setStatsVisible(true)
    }, 900)
  }

  const popupPosition = useMemo(() => {
    const c = regionCenter(region)
    return [c.lat, c.lng]
  }, [region])

  useEffect(() => {
    if (!mapRef.current) return
    if (searching || statsVisible || userMovedMap) return
    fitRegion(0)
  }, [fitRegion, searching, statsVisible, userMovedMap])

  return (
    <main className={`app-root theme-${theme}`}>
      <div className="map-layer" aria-hidden={landingState !== 'hidden'}>
        <MapContainer
          className="map-canvas"
          center={[43.67, -80.13]}
          zoom={10}
          zoomControl
          scrollWheelZoom
          whenReady={(event) => {
            mapRef.current = event.target
            fitRegion(0)
          }}
        >
          <TileLayer url={tilesUrl} attribution={tileAttribution} maxZoom={20} subdomains={['a', 'b', 'c']} />
          <MapEvents onMapClick={onMapClick} onMapMove={() => setUserMovedMap(true)} />

          {region.type === 'circle' ? (
            <Circle
              center={[region.center.lat, region.center.lng]}
              radius={region.radiusMeters}
              eventHandlers={{ click: () => result && setStatsVisible((value) => !value) }}
              pathOptions={{ color: '#1b7d67', weight: 2, fillColor: '#65c9ad', fillOpacity: 0.16 }}
            />
          ) : (
            <Polygon
              positions={region.points}
              eventHandlers={{ click: () => result && setStatsVisible((value) => !value) }}
              pathOptions={{ color: '#1b7d67', weight: 2, fillColor: '#65c9ad', fillOpacity: 0.14 }}
            />
          )}

          {draftPoints.length > 0 && (
            <Polyline positions={draftPoints} pathOptions={{ color: '#b17d2f', weight: 2, dashArray: '5 7' }} />
          )}

          <Marker
            position={[p1.lat, p1.lng]}
            icon={markerIcon('#4ab394')}
            draggable
            eventHandlers={{
              drag: (event) => applyCoord('p1', event.target.getLatLng()),
              dragend: (event) => applyCoord('p1', event.target.getLatLng()),
            }}
          />
          <Marker
            position={[p2.lat, p2.lng]}
            icon={markerIcon('#c09244')}
            draggable
            eventHandlers={{
              drag: (event) => applyCoord('p2', event.target.getLatLng()),
              dragend: (event) => applyCoord('p2', event.target.getLatLng()),
            }}
          />

          {statsVisible && result && (
            <Popup
              ref={popupRef}
              position={popupPosition}
              closeButton
              autoClose={false}
              closeOnClick={false}
              eventHandlers={{ remove: () => setStatsVisible(false) }}
            >
              <div className="result-popup">
                <h3>{result.label} Estimate</h3>
                <p>Area: {result.areaKm2.toFixed(2)} km²</p>
                <p>Capacity fit: {result.placements.toLocaleString()}</p>
                <p>Construction cost: ${result.constructionCost.toLocaleString()}</p>
                <p>Equipment cost: ${result.equipmentCost.toLocaleString()}</p>
                <p>Estimated production: {result.annualMWh.toLocaleString()} MWh/year</p>
              </div>
            </Popup>
          )}
        </MapContainer>
      </div>

      <div className="ui-layer">
        <header className="top-strip">
          <div>
            <h1>Renewables Site Scout</h1>
            <p>Select a region and estimate practical solar or wind deployment outcomes.</p>
          </div>
          <div className="top-actions">
            <button type="button" onClick={() => setTheme((value) => (value === 'light' ? 'dark' : 'light'))}>
              {theme === 'light' ? 'Dark mode' : 'Light mode'}
            </button>
            {userMovedMap && (
              <button
                type="button"
                onClick={() => {
                  fitRegion(0.55)
                  setUserMovedMap(false)
                }}
              >
                Refocus region
              </button>
            )}
          </div>
        </header>

        <section className="bottom-panel" aria-label="Inputs">
          <div className="coords-row">
            <label>
              Point 1
              <input
                value={p1Text}
                onChange={(event) => onCoordChange('p1', event.target.value)}
                onFocus={() => setActiveCoordField('p1')}
                placeholder={'43°43\'25.7"N 80°11\'38.5"W'}
              />
              {p1Error && <small className="field-error">{p1Error}</small>}
            </label>

            <label>
              Point 2
              <input
                value={p2Text}
                onChange={(event) => onCoordChange('p2', event.target.value)}
                onFocus={() => setActiveCoordField('p2')}
                placeholder={'43°43\'25.7"N 80°11\'38.5"W'}
              />
              {p2Error && <small className="field-error">{p2Error}</small>}
            </label>
          </div>

          <div className="advanced-block">
            <button
              type="button"
              className={advancedOpen ? 'expanded' : ''}
              onClick={() => setAdvancedOpen((value) => !value)}
            >
              Advanced Settings
            </button>

            <div className={`advanced-menu ${advancedOpen ? 'open' : ''}`}>
              <div className="mode-row">
                <button type="button" className={drawMode === 'circle' ? 'active' : ''} onClick={() => { setDrawMode('circle'); setDraftPoints([]) }}>
                  Circle tool
                </button>
                <button type="button" className={drawMode === 'polygon' ? 'active' : ''} onClick={() => { setDrawMode('polygon'); setDraftPoints([]) }}>
                  Polygon tool
                </button>
                <button type="button" onClick={finalizePolygon}>
                  Close polygon
                </button>
                <button type="button" onClick={removeLastPolygonPoint} disabled={!draftPoints.length}>
                  Undo point
                </button>
                <button type="button" onClick={useRectangleRegion}>
                  Use rectangle
                </button>
              </div>
              <p className="helper">Click a coordinate field then map to populate it. In circle mode click center then edge. In polygon mode click vertices then Close polygon.</p>
            </div>
          </div>

          <div className="energy-row">
            <label>
              Energy type
              <select
                value={energyType}
                onChange={(event) => {
                  const nextType = event.target.value
                  setEnergyType(nextType)
                  setSelectedModel('')
                  setCustomModel('')
                }}
              >
                <option value="">Select type</option>
                <option value="solar">Solar panels</option>
                <option value="wind">Wind turbines</option>
              </select>
            </label>

            {energyType && (
              <label>
                Model source
                <select value={modelMode} onChange={(event) => setModelMode(event.target.value)}>
                  <option value="predefined">Predefined models</option>
                  <option value="custom">Custom specification</option>
                </select>
              </label>
            )}

            {energyType && modelMode === 'predefined' && (
              <label>
                Model
                <select value={selectedModel} onChange={(event) => setSelectedModel(event.target.value)}>
                  <option value="">Select model</option>
                  {modelOptions.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {energyType && modelMode === 'custom' && (
              <label>
                Custom spec
                <input
                  value={customModel}
                  onChange={(event) => setCustomModel(event.target.value)}
                  placeholder="Enter custom model or specs"
                />
              </label>
            )}
          </div>

          {submitError && <p className="submit-error">{submitError}</p>}

          <div className="actions-row">
            <button type="button" className="primary" disabled={!isReady || searching} onClick={runAnalysis}>
              {searching ? 'Computing...' : 'Search'}
            </button>
          </div>
        </section>
      </div>

      {landingState !== 'hidden' && (
        <section
          className={`landing ${landingState === 'fading' ? 'fading' : ''}`}
          role="dialog"
          aria-label="Welcome"
          onClick={enterApp}
        >
          <div className="landing-card">
            <p className="kicker">Catapult 2026</p>
            <h2>Renewables Site Scout</h2>
            <p>Plan clean-energy sites with precise map-based region selection and fast feasibility estimates.</p>
            <small>Click anywhere or press any key to begin.</small>
          </div>
        </section>
      )}
    </main>
  )
}

export default App
