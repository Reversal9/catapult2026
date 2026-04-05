import React from "react";

function TopBar({
  theme,
  expanded,
  onToggleExpanded,
  onToggleTheme,
  userMovedMap,
  onRefocus,
}) {
  if (!expanded) {
    return (
      <button
        type="button"
        className="floating-menu-button"
        aria-label="Open top menu"
        onClick={onToggleExpanded}
      >
        ≡
      </button>
    );
  }

  return (
    <div className="top-strip">
      <div className="title-chip">
        <h1>Site Scouter</h1>
        <p>
          Choose a region, pick an asset, and compare build-ready results with
          clear explanations.
        </p>
      </div>

      <div className="top-icon-actions">
        <button
          type="button"
          className="icon-button"
          aria-label={
            theme === "light" ? "Switch to dark mode" : "Switch to light mode"
          }
          onClick={onToggleTheme}
        >
          {theme === "light" ? "◐" : "☀"}
        </button>
        <button
          type="button"
          className="icon-button"
          aria-label="Refocus selected region"
          onClick={onRefocus}
          disabled={!userMovedMap}
        >
          ⌖
        </button>
        <button
          type="button"
          className="icon-button"
          aria-label="Close top menu"
          onClick={onToggleExpanded}
        >
          ×
        </button>
      </div>
    </div>
  );
}

export default TopBar;
