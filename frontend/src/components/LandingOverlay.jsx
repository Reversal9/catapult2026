import React from "react";

function LandingOverlay({ landingState, onEnter }) {
  if (landingState === "hidden") return null;

  return (
    <section
      className={`landing ${landingState === "fading" ? "fading" : ""}`}
      role="dialog"
      aria-label="Welcome"
      onClick={onEnter}
    >
      <div className="landing-card">
        <p className="kicker">Catapult 2026</p>
        <h2>Renewables Site Scout</h2>
        <p>
          Plan solar, wind, and digital-infrastructure sites with precise
          map-based region selection and fast feasibility estimates.
        </p>
        <small>Click anywhere or press any key to begin.</small>
      </div>
    </section>
  );
}

export default LandingOverlay;
