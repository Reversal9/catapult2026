import React, { useMemo, useState } from "react";
import TrendChart from "./TrendChart";
import { computeFinancials, formatUsd } from "../lib/financialProjection";

function BreakEvenChart({ financials }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const chart = useMemo(() => {
    if (!financials?.cashFlowByYear?.length) return null;
    const values = financials.cashFlowByYear.map((d) => d.cumulative);
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = Math.max(maxVal - minVal, 1);
    const width = 760;
    const height = 240;
    const padL = 60;
    const padR = 20;
    const padT = 20;
    const padB = 32;
    const innerW = width - padL - padR;
    const innerH = height - padT - padB;
    const n = values.length;
    const stepX = innerW / (n - 1);

    const toX = (i) => padL + i * stepX;
    const toY = (v) => padT + innerH - ((v - minVal) / range) * innerH;
    const zeroY = toY(0);

    const points = financials.cashFlowByYear.map((d, i) => ({
      ...d,
      x: toX(i),
      y: toY(d.cumulative),
    }));

    const linePath = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
      .join(" ");

    // Area path split into negative (red) and positive (green) would be complex;
    // use a single gradient area instead
    const areaPath = `${linePath} L ${points[n - 1].x.toFixed(1)} ${zeroY.toFixed(1)} L ${points[0].x.toFixed(1)} ${zeroY.toFixed(1)} Z`;

    // Find break-even crossing index
    let breakEvenX = null;
    for (let i = 0; i < points.length - 1; i++) {
      if (
        (points[i].cumulative < 0 && points[i + 1].cumulative >= 0) ||
        (points[i].cumulative >= 0 && points[i + 1].cumulative < 0)
      ) {
        const t =
          Math.abs(points[i].cumulative) /
          (Math.abs(points[i].cumulative) + Math.abs(points[i + 1].cumulative));
        breakEvenX = points[i].x + t * stepX;
        break;
      }
    }

    // Y axis labels
    const labelCount = 4;
    const yLabels = Array.from({ length: labelCount + 1 }, (_, i) => {
      const v = minVal + (range * i) / labelCount;
      return { y: toY(v), label: formatUsd(v) };
    });

    // X axis labels: years 1, 5, 10, 15, 20
    const xTicks = [1, 5, 10, 15, 20].filter((y) => y <= n);
    const xLabels = xTicks.map((y) => ({
      x: toX(y - 1),
      label: `Yr ${y}`,
    }));

    return {
      width,
      height,
      padL,
      zeroY,
      points,
      linePath,
      areaPath,
      breakEvenX,
      yLabels,
      xLabels,
      isAllNegative: maxVal < 0,
      isAllPositive: minVal >= 0,
    };
  }, [financials]);

  if (!chart) return null;

  const activePoint =
    hoveredIndex !== null ? chart.points[hoveredIndex] ?? null : null;

  return (
    <div className="breakeven-chart-block">
      <div className="trend-tooltip-row">
        {activePoint ? (
          <div className="trend-tooltip-card">
            <strong>Year {activePoint.year}</strong>
            <span
              style={{
                color: activePoint.cumulative >= 0 ? "var(--profit-color)" : "var(--loss-color)",
              }}
            >
              {activePoint.cumulative >= 0 ? "+" : ""}
              {formatUsd(activePoint.cumulative)}
            </span>
          </div>
        ) : (
          <div className="trend-tooltip-card muted">Hover a year to inspect.</div>
        )}
      </div>
      <div className="trend-scroll-shell">
        <svg
          viewBox={`0 0 ${chart.width} ${chart.height}`}
          className="trend-chart breakeven-svg"
          style={{ width: `${chart.width}px` }}
          onMouseLeave={() => setHoveredIndex(null)}
          onMouseMove={(e) => {
            const b = e.currentTarget.getBoundingClientRect();
            const x = ((e.clientX - b.left) / b.width) * chart.width;
            const idx = Math.round((x - chart.padL) / ((chart.width - chart.padL - 20) / (chart.points.length - 1)));
            setHoveredIndex(Math.max(0, Math.min(chart.points.length - 1, idx)));
          }}
        >
          {/* Zero reference line */}
          <line
            x1={chart.padL}
            y1={chart.zeroY}
            x2={chart.width - 20}
            y2={chart.zeroY}
            className="breakeven-zero-line"
          />

          {/* Area fill */}
          <path
            d={chart.areaPath}
            className={
              chart.isAllPositive
                ? "breakeven-area-positive"
                : chart.isAllNegative
                  ? "breakeven-area-negative"
                  : "breakeven-area-mixed"
            }
          />

          {/* Line */}
          <path d={chart.linePath} fill="none" className="breakeven-line" strokeWidth="2.5" />

          {/* Break-even marker */}
          {chart.breakEvenX !== null && (
            <>
              <line
                x1={chart.breakEvenX}
                y1={chart.padL - 10}
                x2={chart.breakEvenX}
                y2={chart.height - chart.padL + 10}
                className="breakeven-marker-line"
              />
            </>
          )}

          {/* Y labels */}
          {chart.yLabels.map((l, i) => (
            <text key={i} x={chart.padL - 6} y={l.y + 4} className="breakeven-axis-label" textAnchor="end">
              {l.label}
            </text>
          ))}

          {/* X labels */}
          {chart.xLabels.map((l, i) => (
            <text key={i} x={l.x} y={chart.height - 8} className="breakeven-axis-label" textAnchor="middle">
              {l.label}
            </text>
          ))}

          {/* Hover line */}
          {activePoint && (
            <line
              x1={activePoint.x}
              y1={20}
              x2={activePoint.x}
              y2={chart.height - 32}
              className="trend-hover-line"
            />
          )}
        </svg>
      </div>
    </div>
  );
}

function AnalysisModal({ open, onClose, result }) {
  const [tab, setTab] = useState("financial");

  const financials = useMemo(() => computeFinancials(result), [result]);
  const hasDailyTrend = result?.dailyGeneration?.length > 0;

  if (!open || !result) return null;

  return (
    <div className="trend-modal-shell" role="dialog" aria-label="Financial analysis">
      <div className="trend-modal-card analysis-modal-card">
        <div className="trend-modal-header">
          <div>
            <h3>{result.label} — Financial Analysis</h3>
            <p>Projections are estimates based on industry benchmarks.</p>
          </div>
          <button type="button" className="icon-button" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>

        {hasDailyTrend && (
          <div className="analysis-tab-bar">
            <button
              type="button"
              className={`analysis-tab ${tab === "financial" ? "active" : ""}`}
              onClick={() => setTab("financial")}
            >
              Financial projection
            </button>
            <button
              type="button"
              className={`analysis-tab ${tab === "trend" ? "active" : ""}`}
              onClick={() => setTab("trend")}
            >
              Daily generation
            </button>
          </div>
        )}

        {tab === "financial" && (
          <div className="analysis-financial-section">
            {financials ? (
              <>
                <div className="analysis-summary-row">
                  <div className="analysis-kpi">
                    <span>Annual revenue</span>
                    <strong className="kpi-positive">{formatUsd(financials.annualRevenue)}/yr</strong>
                    <small>{financials.revenueNote}</small>
                  </div>
                  <div className="analysis-kpi">
                    <span>Annual O&amp;M</span>
                    <strong>{formatUsd(financials.annualOM)}/yr</strong>
                    <small>Operating & maintenance</small>
                  </div>
                  <div className="analysis-kpi">
                    <span>Annual net income</span>
                    <strong className={financials.annualNet >= 0 ? "kpi-positive" : "kpi-negative"}>
                      {financials.annualNet >= 0 ? "+" : ""}
                      {formatUsd(financials.annualNet)}/yr
                    </strong>
                    <small>Revenue minus O&amp;M</small>
                  </div>
                  <div className="analysis-kpi">
                    <span>Payback period</span>
                    <strong className="kpi-accent">
                      {financials.breakEvenYears
                        ? financials.breakEvenYears <= 20
                          ? `~${Math.ceil(financials.breakEvenYears)} years`
                          : ">20 years"
                        : "—"}
                    </strong>
                    <small>Estimated break-even</small>
                  </div>
                </div>

                <p className="analysis-chart-label">20-year cumulative cash flow</p>
                <BreakEvenChart financials={financials} />

                <p className="analysis-disclaimer">
                  Revenue assumes {financials.isEnergyProject ? "$0.11/kWh grid rate" : "$900/kW/yr colocation pricing"}.
                  O&amp;M is estimated at {financials.isEnergyProject ? "1.5–2.2" : "2.8"}% of capital cost per year.
                  Actual returns depend on offtake agreements, financing terms, and local incentives.
                </p>
              </>
            ) : (
              <p className="trend-empty">Financial projection is not available for this result type.</p>
            )}
          </div>
        )}

        {tab === "trend" && hasDailyTrend && (
          <TrendChart
            points={result.dailyGeneration}
            label="Estimated daily output"
            unit="kWh"
          />
        )}
      </div>
    </div>
  );
}

export default AnalysisModal;
