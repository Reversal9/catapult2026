import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it, vi } from "vitest";
import ControlPanel from "./ControlPanel";

const baseProps = {
  collapsed: false,
  onToggleCollapsed: vi.fn(),
  p1Text: "43°43'25.7\"N 80°11'38.5\"W",
  p2Text: "43°42'25.7\"N 80°10'38.5\"W",
  p1Error: "",
  p2Error: "",
  onCoordChange: vi.fn(),
  onCoordFocus: vi.fn(),
  advancedOpen: true,
  onToggleAdvanced: vi.fn(),
  drawMode: "circle",
  onDrawModeChange: vi.fn(),
  onFinalizePolygon: vi.fn(),
  onRemoveLastPoint: vi.fn(),
  onUseRectangle: vi.fn(),
  hasDraftPoints: false,
  energyType: "infrastructure",
  modelMode: "predefined",
  selectedModel: "",
  assetSpecFields: [],
  assetPresets: [],
  imageryProvider: "usgs",
  segmentationBackend: "auto",
  terrainProvider: "opentopodata",
  cellSizeMeters: 300,
  onEnergyTypeChange: vi.fn(),
  onModelModeChange: vi.fn(),
  onSelectedModelChange: vi.fn(),
  onAssetSpecChange: vi.fn(),
  onImageryProviderChange: vi.fn(),
  onSegmentationBackendChange: vi.fn(),
  onTerrainProviderChange: vi.fn(),
  onCellSizeMetersChange: vi.fn(),
  submitError: "",
  isReady: true,
  searching: false,
  result: null,
  selectedCandidateId: null,
  onSelectCandidate: vi.fn(),
  onRunAnalysis: vi.fn(),
  onOpenTrend: vi.fn(),
};

describe("ControlPanel", () => {
  it("renders the muted circular helper buttons", () => {
    render(<ControlPanel {...baseProps} />);

    const helpButtons = screen.getAllByRole("button", { name: /help for/i });
    expect(helpButtons[0]).toHaveClass("help-button");
  });

  it("runs analysis when the primary action is clicked", async () => {
    const user = userEvent.setup();
    render(<ControlPanel {...baseProps} />);

    await user.click(screen.getByRole("button", { name: /run analysis/i }));
    expect(baseProps.onRunAnalysis).toHaveBeenCalledTimes(1);
  });
});
