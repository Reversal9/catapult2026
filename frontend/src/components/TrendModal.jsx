import React from "react";
import TrendChart from "./TrendChart";

function TrendModal({ open, onClose, result }) {
  if (!open || !result) return null;

  return (
    <div className="trend-modal-shell" role="dialog" aria-label="Generation trend">
      <div className="trend-modal-card">
        <div className="trend-modal-header">
          <div>
            <h3>{result.label} Daily Trend</h3>
            <p>
              Past-year estimate from {result.trendPeriodStart} to {result.trendPeriodEnd}.
            </p>
          </div>
          <button
            type="button"
            className="icon-button"
            aria-label="Close generation trend"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <TrendChart
          points={result.dailyGeneration}
          label="Estimated daily output"
          unit="kWh"
        />
      </div>
    </div>
  );
}

export default TrendModal;
