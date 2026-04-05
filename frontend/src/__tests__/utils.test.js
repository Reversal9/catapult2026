/**
 * Frontend utility tests for geospatial, formatting, and data transformation functions.
 *
 * Test coverage for:
 * - Geographic calculations (haversine distance, bounds, projections)
 * - DMS coordinate formatting and parsing
 * - Region area and center calculations
 */

import { describe, expect, it } from "vitest";
import {
  clamp,
  haversineMeters,
  normLng,
  rectangleFromTwoPoints,
  regionCenter,
  polygonAreaKm2,
  regionAreaKm2,
} from "../utils/geo";
import { formatDmsPair, parseDmsPair } from "../utils/dms";

describe("Geographic Utilities", () => {
  describe("haversineMeters", () => {
    it("should calculate distance between two points", () => {
      // New York to Los Angeles is approximately 3,944 km
      const nyc = { lat: 40.7128, lng: -74.006 };
      const la = { lat: 34.0522, lng: -118.2437 };

      const distance = haversineMeters(nyc, la);
      expect(distance).toBeGreaterThan(3_900_000); // meters
      expect(distance).toBeLessThan(4_000_000);
    });

    it("should return 0 for same point", () => {
      const point = { lat: 40.7128, lng: -74.006 };
      expect(haversineMeters(point, point)).toBe(0);
    });

    it("should calculate distance across equator", () => {
      const north = { lat: 0, lng: 0 };
      const south = { lat: 0, lng: 90 };
      const distance = haversineMeters(north, south);

      // Should be approximately 1/4 of Earth's circumference
      const expectedApprox = (Math.PI * 2 * 6_371_000) / 4;
      expect(distance).toBeGreaterThan(expectedApprox - 50_000);
      expect(distance).toBeLessThan(expectedApprox + 50_000);
    });
  });

  describe("normLng", () => {
    it("should normalize longitudes to [-180, 180]", () => {
      expect(normLng(0)).toBe(0);
      expect(normLng(180)).toBe(180);
      expect(normLng(-180)).toBe(-180);
    });

    it("should wrap longitudes > 180", () => {
      expect(normLng(270)).toBeCloseTo(-90, 1);
      expect(normLng(360)).toBeCloseTo(0, 1);
      expect(normLng(540)).toBeCloseTo(180, 1);
    });

    it("should wrap longitudes < -180", () => {
      expect(normLng(-270)).toBeCloseTo(90, 1);
      expect(normLng(-360)).toBeCloseTo(0, 1);
    });
  });

  describe("rectangleFromTwoPoints", () => {
    it("should create rectangle from two corners", () => {
      const p1 = { lat: 40, lng: -75 };
      const p2 = { lat: 41, lng: -74 };

      const rect = rectangleFromTwoPoints(p1, p2);
      expect(rect).toHaveLength(4);
      // Check that south latitude <= north latitude
      expect(rect[0][0]).toBeLessThanOrEqual(rect[2][0]);
    });

    it("should normalize latitude order (smaller first)", () => {
      const p1 = { lat: 45, lng: -100 };
      const p2 = { lat: 35, lng: -80 };

      const rect = rectangleFromTwoPoints(p1, p2);
      // Should use min/max of lat and lng
      const lats = rect.map((p) => p[0]);

      expect(Math.min(...lats)).toBe(35);
      expect(Math.max(...lats)).toBe(45);
    });
  });

  describe("polygonAreaKm2", () => {
    it("should calculate polygon area", () => {
      const points = [
        [0, 0],
        [0, 1],
        [1, 1],
        [1, 0],
      ];

      const area = polygonAreaKm2(points);
      expect(area).toBeGreaterThan(0);
    });

    it("should return 0 for degenerate polygon", () => {
      const points = [
        [0, 0],
        [0, 1],
      ]; // Only 2 points
      expect(polygonAreaKm2(points)).toBe(0);
    });
  });

  describe("regionCenter", () => {
    it("should calculate center of polygon", () => {
      const region = {
        type: "polygon",
        points: [
          [0, 0],
          [0, 2],
          [2, 2],
          [2, 0],
        ],
      };

      const center = regionCenter(region);
      expect(center.lat).toBeCloseTo(1, 1);
      expect(center.lng).toBeCloseTo(1, 1);
    });

    it("should return circle center for circle region", () => {
      const region = {
        type: "circle",
        center: { lat: 45.5, lng: -122.7 },
        radiusMeters: 1000,
      };

      const center = regionCenter(region);
      expect(center.lat).toBe(45.5);
      expect(center.lng).toBe(-122.7);
    });
  });

  describe("regionAreaKm2", () => {
    it("should calculate polygon area", () => {
      const region = {
        type: "polygon",
        points: [
          [0, 0],
          [0, 1],
          [1, 1],
          [1, 0],
        ],
      };

      const area = regionAreaKm2(region);
      expect(area).toBeGreaterThan(0);
    });

    it("should calculate circle area from radius", () => {
      const region = {
        type: "circle",
        center: { lat: 0, lng: 0 },
        radiusMeters: 1000, // 1 km radius
      };

      const area = regionAreaKm2(region);
      // π * 1^2 ≈ 3.14 km²
      expect(area).toBeCloseTo(Math.PI, 1);
    });
  });

  describe("clamp", () => {
    it("should return value if within bounds", () => {
      expect(clamp(50, 0, 100)).toBe(50);
    });

    it("should return min if below", () => {
      expect(clamp(-10, 0, 100)).toBe(0);
    });

    it("should return max if above", () => {
      expect(clamp(150, 0, 100)).toBe(100);
    });
  });
});

describe("DMS Coordinate Formatting", () => {
  describe("formatDmsPair", () => {
    it("should format lat/lon pair as space-separated DMS", () => {
      const pair = formatDmsPair({ lat: 40.2649, lng: -122.7282 });
      // Output format: "deg°min'sec"HEM deg°min'sec"HEM" (space-separated)
      expect(pair).toContain("N"); // North for positive latitude
      expect(pair).toContain("W"); // West for negative longitude
      expect(pair).toMatch(/^\d+°\d+'\d+\.?\d*"[NS] \d+°\d+'\d+\.?\d*"[EW]$/);
    });

    it("should format with proper hemisphere labels", () => {
      const positive = formatDmsPair({ lat: 40, lng: 120 });
      expect(positive).toContain("N");
      expect(positive).toContain("E");

      const negative = formatDmsPair({ lat: -40, lng: -120 });
      expect(negative).toContain("S");
      expect(negative).toContain("W");
    });
  });

  describe("parseDmsPair", () => {
    it("should parse valid lat/lon space-separated pair", () => {
      // Format: 43°43'25.7"N 80°11'38.5"W
      const result = parseDmsPair("43°43'25.7\"N 80°11'38.5\"W");
      expect(result.ok).toBe(true);
      expect(result.value).toBeDefined();
      expect(result.value.lat).toBeCloseTo(43.7238, 3);
      expect(result.value.lng).toBeCloseTo(-80.194, 3);
    });

    it("should return error for invalid format", () => {
      const result = parseDmsPair("invalid");
      expect(result.ok).toBe(false);
      expect(result.message).toContain("Use DMS format");
    });

    it("should validate coordinate ranges", () => {
      // Latitude > 90 should fail
      const result = parseDmsPair("91°00'00\"N 180°00'00\"W");
      expect(result.ok).toBe(false);
      expect(result.message).toContain("out of range");
    });

    it("should validate latitude/longitude constraints", () => {
      // Minutes >= 60 should fail
      const result = parseDmsPair("40°75'00\"N 122°43'41\"W");
      expect(result.ok).toBe(false);
      expect(result.message).toContain("out of range");
    });
  });
});
