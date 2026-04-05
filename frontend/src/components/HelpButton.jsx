import React, { useState } from "react";

function HelpButton({ label, help }) {
  const [open, setOpen] = useState(false);

  return (
    <span className={`help-wrap ${open ? "open" : ""}`}>
      <span className="label-with-help">
        <span>{label}</span>
        <button
          type="button"
          className="help-button"
          aria-label={`Help for ${label}`}
          aria-expanded={open}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            setOpen((value) => !value);
          }}
        >
          ?
        </button>
      </span>
      {open && (
        <span className="help-popover" role="note">
          {help}
        </span>
      )}
    </span>
  );
}

export default HelpButton;
