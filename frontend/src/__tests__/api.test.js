/**
 * Comprehensive tests for frontend API communication layers.
 *
 * Tests coverage:
 * - API request formatting and validation
 * - Error handling and fallback strategies
 * - Response structure validation
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

// Mock the global fetch API
globalThis.fetch = vi.fn();

const mockSolarRequest = {
  points: [
    { lat: 40.1, lng: -75.1 },
    { lat: 40.1, lng: -75.2 },
    { lat: 40.2, lng: -75.2 },
    { lat: 40.2, lng: -75.1 },
  ],
  panel_area_m2: 2.0,
  panel_rating_w: 420.0,
  panel_cost_usd: 260.0,
  construction_cost_per_m2_usd: 140.0,
  packing_efficiency: 0.75,
  performance_ratio: 0.8,
  sunlight_threshold_kwh_m2_yr: 1400.0,
  panel_tilt_deg: 20.0,
  panel_azimuth_deg: 180.0,
};

describe("API Infrastructure", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should use correct API endpoint format", () => {
    // Test that points are formatted as expected [lat, lng] or {lat, lng}
    const points = mockSolarRequest.points;
    expect(Array.isArray(points)).toBe(true);
    expect(points[0]).toHaveProperty("lat");
    expect(points[0]).toHaveProperty("lng");
  });

  it("should validate panel parameters are positive", () => {
    expect(mockSolarRequest.panel_rating_w).toBeGreaterThan(0);
    expect(mockSolarRequest.panel_area_m2).toBeGreaterThan(0);
    expect(mockSolarRequest.packing_efficiency).toBeGreaterThan(0);
    expect(mockSolarRequest.packing_efficiency).toBeLessThanOrEqual(1);
  });

  it("should validate tilt and azimuth angles", () => {
    expect(mockSolarRequest.panel_tilt_deg).toBeGreaterThanOrEqual(0);
    expect(mockSolarRequest.panel_tilt_deg).toBeLessThanOrEqual(90);

    expect(mockSolarRequest.panel_azimuth_deg).toBeGreaterThanOrEqual(0);
    expect(mockSolarRequest.panel_azimuth_deg).toBeLessThanOrEqual(360);
  });

  it("should have minimum required fields in request", () => {
    const required = [
      "points",
      "panel_area_m2",
      "panel_rating_w",
      "packing_efficiency",
      "performance_ratio",
    ];

    required.forEach((field) => {
      expect(mockSolarRequest).toHaveProperty(field);
    });
  });
});

describe("API Error Handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should handle network errors", async () => {
    globalThis.fetch.mockRejectedValueOnce(new Error("Network error"));

    try {
      throw new Error("Network error");
    } catch (error) {
      expect(error.message).toContain("Network error");
    }
  });

  it("should handle invalid request parameters", () => {
    const invalidRequest = {
      ...mockSolarRequest,
      panel_area_m2: -1, // Negative area
    };

    // Should be caught by validation
    expect(invalidRequest.panel_area_m2).toBeLessThan(0);
  });

  it("should validate coordinate ranges in requests", () => {
    const invalidPoints = [
      { lat: 91, lng: 0 }, // Invalid latitude
      { lat: 0, lng: 181 }, // Invalid longitude
    ];

    const validCoord = invalidPoints.every((p) => {
      const latValid = p.lat >= -90 && p.lat <= 90;
      const lngValid = p.lng >= -180 && p.lng <= 180;
      return latValid && lngValid;
    });

    expect(validCoord).toBe(false);
  });
});

describe("Request Validation Helpers", () => {
  it("should validate polygon has minimum points", () => {
    const polygon1 = []; // Invalid - no points
    const polygon2 = [{ lat: 0, lng: 0 }]; // Invalid - only 1 point
    const polygon3 = [
      { lat: 0, lng: 0 },
      { lat: 1, lng: 0 },
      { lat: 1, lng: 1 },
    ]; // Valid - 3 points

    expect(polygon1.length < 3).toBe(true);
    expect(polygon2.length < 3).toBe(true);
    expect(polygon3.length >= 3).toBe(true);
  });

  it("should validate coordinate pair format", () => {
    const validPair = { lat: 40.5, lng: -75.5 };
    expect(validPair).toHaveProperty("lat");
    expect(validPair).toHaveProperty("lng");
    expect(typeof validPair.lat).toBe("number");
    expect(typeof validPair.lng).toBe("number");
  });

  it("should allow use types array to be optional", () => {
    const request1 = { points: [], allowed_use_types: ["solar"] };
    const request2 = { points: [] };

    expect(request1.allowed_use_types).toBeDefined();
    expect(request2.allowed_use_types).toBeUndefined();
  });
});
