import React, { useMemo, useState } from "react";

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function TrendChart({ points, label, unit = "kWh" }) {
  const [zoom, setZoom] = useState(1);
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const chart = useMemo(() => {
    if (!points?.length) return null;

    const width = Math.max(820, Math.round(820 * zoom));
    const height = 280;
    const padding = 36;
    const values = points.map((point) => point.generation_kwh);
    const maxValue = Math.max(...values, 1);
    const minValue = Math.min(...values, 0);
    const range = Math.max(maxValue - minValue, 1);
    const stepX = (width - padding * 2) / Math.max(points.length - 1, 1);

    const toY = (value) =>
      height - padding - ((value - minValue) / range) * (height - padding * 2);

    const path = points
      .map((point, index) => {
        const x = padding + stepX * index;
        const y = toY(point.generation_kwh);
        return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(" ");

    const areaPath = `${path} L ${padding + stepX * (points.length - 1)} ${height - padding} L ${padding} ${height - padding} Z`;

    const plottedPoints = points.map((point, index) => ({
      ...point,
      x: padding + stepX * index,
      y: toY(point.generation_kwh),
    }));

    return {
      width,
      height,
      padding,
      minValue,
      maxValue,
      plottedPoints,
      path,
      areaPath,
      stepX,
      startLabel: points[0].date,
      endLabel: points[points.length - 1].date,
      zoomLabel: zoom === 1 ? "Full year" : `${zoom.toFixed(1)}x zoom`,
    };
  }, [points, zoom]);

  if (!chart) {
    return (
      <div className="trend-empty">
        Daily production is not available for this asset type.
      </div>
    );
  }

  const activePoint =
    hoveredIndex === null
      ? null
      : chart.plottedPoints[
          clamp(hoveredIndex, 0, chart.plottedPoints.length - 1)
        ];

  return (
    <div className="trend-chart-block">
      <div className="trend-chart-header">
        <div>
          <strong>{label}</strong>
          <span>{chart.zoomLabel}</span>
        </div>
        <div className="trend-chart-controls">
          <button
            type="button"
            className="icon-button"
            aria-label="Zoom out trend chart"
            onClick={() => setZoom((value) => clamp(value / 1.5, 1, 12))}
          >
            −
          </button>
          <button
            type="button"
            className="icon-button"
            aria-label="Zoom in trend chart"
            onClick={() => setZoom((value) => clamp(value * 1.5, 1, 12))}
          >
            +
          </button>
        </div>
      </div>

      <div className="trend-tooltip-row">
        {activePoint ? (
          <div className="trend-tooltip-card">
            <strong>{activePoint.date}</strong>
            <span>
              {activePoint.generation_kwh.toLocaleString(undefined, {
                maximumFractionDigits: 1,
              })}{" "}
              {unit}
            </span>
          </div>
        ) : (
          <div className="trend-tooltip-card muted">
            Hover a day to inspect the value.
          </div>
        )}
      </div>

      <div className="trend-scroll-shell">
        <svg
          viewBox={`0 0 ${chart.width} ${chart.height}`}
          className="trend-chart"
          role="img"
          aria-label={label}
          style={{ width: `${chart.width}px` }}
          onMouseLeave={() => setHoveredIndex(null)}
          onMouseMove={(event) => {
            const bounds = event.currentTarget.getBoundingClientRect();
            const x =
              ((event.clientX - bounds.left) / bounds.width) * chart.width;
            const index = clamp(
              Math.round((x - chart.padding) / chart.stepX),
              0,
              chart.plottedPoints.length - 1,
            );
            setHoveredIndex(index);
          }}
        >
          <line
            x1={chart.padding}
            y1={chart.height - chart.padding}
            x2={chart.width - chart.padding}
            y2={chart.height - chart.padding}
            className="trend-axis-line"
          />
          <path d={chart.areaPath} className="trend-area-path" />
          <path
            d={chart.path}
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
          />
          {activePoint && (
            <>
              <line
                x1={activePoint.x}
                y1={chart.padding}
                x2={activePoint.x}
                y2={chart.height - chart.padding}
                className="trend-hover-line"
              />
              <line
                x1={chart.padding}
                y1={activePoint.y}
                x2={chart.width - chart.padding}
                y2={activePoint.y}
                className="trend-hover-guide"
              />
            </>
          )}
        </svg>
      </div>

      <div className="trend-chart-axis">
        <span>{chart.startLabel}</span>
        <span>
          Low {Math.round(chart.minValue).toLocaleString()} {unit}
        </span>
        <span>
          High {Math.round(chart.maxValue).toLocaleString()} {unit}
        </span>
        <span>{chart.endLabel}</span>
      </div>
    </div>
  );
}

export default TrendChart;
