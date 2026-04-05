import { render, screen } from "@testing-library/react";
import { waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { vi } from "vitest";
import App from "./App";

vi.mock("leaflet", () => ({
  default: {
    divIcon: () => ({}),
    latLngBounds: (...args) => args,
  },
}));

vi.mock("react-leaflet", () => {
  const passthrough = ({ children }) => <>{children}</>;

  return {
    MapContainer: ({ children, whenReady }) => {
      React.useEffect(() => {
        const fakeMap = {
          fitBounds: vi.fn(),
        };
        whenReady?.({ target: fakeMap });
      }, [whenReady]);

      return <div data-testid="map-container">{children}</div>;
    },
    TileLayer: passthrough,
    Circle: passthrough,
    Polygon: passthrough,
    Polyline: passthrough,
    Marker: passthrough,
    Popup: passthrough,
    useMapEvents: () => ({}),
  };
});

describe("Frontend UI/UX expectations", () => {
  it("shows landing first and fades to main app on click", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(
      screen.getByRole("dialog", { name: /welcome/i }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("dialog", { name: /welcome/i }));

    await waitFor(() => {
      expect(
        screen.queryByRole("dialog", { name: /welcome/i }),
      ).not.toBeInTheDocument();
    });
    expect(
      screen.getByRole("heading", { name: /site scouter/i }),
    ).toBeInTheDocument();
  });

  it("validates DMS coordinate format with actionable error text", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("dialog", { name: /welcome/i }));

    const point1 = screen.getByLabelText(/point 1/i, { selector: "input" });
    await user.clear(point1);
    await user.type(point1, "invalid coordinate");

    expect(screen.getByText(/use dms format/i)).toBeInTheDocument();
  });

  it("keeps search disabled until required fields are complete", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("dialog", { name: /welcome/i }));

    const searchButton = screen.getByRole("button", { name: /run analysis/i });
    expect(searchButton).toBeDisabled();

    await user.selectOptions(
      screen.getByLabelText(/asset type/i, { selector: "select" }),
      "solar",
    );
    await user.selectOptions(
      screen.getByLabelText(/preset/i, { selector: "select" }),
      "SunForge SF-450",
    );

    expect(searchButton).toBeEnabled();
  });

  it("toggles advanced settings dropdown", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("dialog", { name: /welcome/i }));

    const trigger = screen.getByRole("button", { name: /advanced settings/i });
    await user.click(trigger);

    expect(
      screen.getByText(
        /switch between rectangle, circle, and polygon region selection/i,
      ),
    ).toBeInTheDocument();
  });

  it("allows infrastructure analysis without selecting an equipment model", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("dialog", { name: /welcome/i }));
    await user.selectOptions(
      screen.getByLabelText(/asset type/i, { selector: "select" }),
      "infrastructure",
    );

    expect(screen.getByRole("button", { name: /run analysis/i })).toBeEnabled();
  });

  it("collapses the top menu into a compact button and can reopen it", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("dialog", { name: /welcome/i }));
    await user.click(screen.getByRole("button", { name: /close top menu/i }));

    expect(
      screen.getByRole("button", { name: /open top menu/i }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /open top menu/i }));
    expect(
      screen.getByRole("button", { name: /switch to dark mode/i }),
    ).toBeInTheDocument();
  });

  it("can collapse the planning panel for a larger map view", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("dialog", { name: /welcome/i }));
    const toggle = screen.getByRole("button", { name: /collapse panel/i });
    await user.click(toggle);

    expect(
      screen.getByRole("button", { name: /expand panel/i }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/point 1/i)).not.toBeInTheDocument();
  });
});
