#!/usr/bin/env python3
"""Test the cost module integration in solar_analysis.py"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.schemas import SolarAnalysisRequest, Coordinate

# Create a mock request with state
request = SolarAnalysisRequest(
    points=[
        Coordinate(lat=33.4, lon=-112.1),
        Coordinate(lat=33.4, lon=-112.0),
        Coordinate(lat=33.3, lon=-112.0),
        Coordinate(lat=33.3, lon=-112.1),
    ],
    state="CA",  # With state - should use cost module
    panel_area_m2=2.0,
    panel_rating_w=420.0,
    panel_cost_usd=260.0,
    construction_cost_per_m2_usd=140.0,
    packing_efficiency=0.75,
    performance_ratio=0.8,
    sunlight_threshold_kwh_m2_yr=1400.0,
    panel_tilt_deg=20.0,
    panel_azimuth_deg=180.0,
)

print("Test request created:")
print(f"  Area: {request.panel_area_m2} m²")
print(f"  Rating: {request.panel_rating_w} W")
print(f"  State: {request.state}")
print(f"  Packing efficiency: {request.packing_efficiency}")

# Now test without state
request_no_state = SolarAnalysisRequest(
    points=[
        Coordinate(lat=33.4, lon=-112.1),
        Coordinate(lat=33.4, lon=-112.0),
        Coordinate(lat=33.3, lon=-112.0),
        Coordinate(lat=33.3, lon=-112.1),
    ],
    # No state - should use simple calculation
    panel_area_m2=2.0,
    panel_rating_w=420.0,
    panel_cost_usd=260.0,
    construction_cost_per_m2_usd=140.0,
    packing_efficiency=0.75,
    performance_ratio=0.8,
    sunlight_threshold_kwh_m2_yr=1400.0,
    panel_tilt_deg=20.0,
    panel_azimuth_deg=180.0,
)

print(f"\nRequest without state - state field: {request_no_state.state}")

# Test the cost module directly
print("\n--- Testing cost module directly ---")
from backend.cost.cost import estimate_solar_project_cost

# Estimate panel dimensions from area (as done in solar_analysis.py)
panel_area_m2 = 2.0
aspect_ratio = 1.7
width_m = (panel_area_m2 / aspect_ratio) ** 0.5
length_m = width_m * aspect_ratio

panel_specs = {
    "length_m": length_m,
    "width_m": width_m,
    "STC_W": 420.0,
}

result = estimate_solar_project_cost(
    area_m2=1000,
    panel_specs=panel_specs,
    state="CA",
    year=2026,
    ghi_kwh_m2_day=4.5,  # ~1642 kWh/m²/yr
    packing_factor=0.75,
    performance_ratio=0.8,
)

print(f"Panel dimensions: {length_m:.2f}m x {width_m:.2f}m = {panel_area_m2:.2f}m²")
print(f"Panel count: {result['layer_1_system_size']['n_panels']}")
print(f"Capacity: {result['layer_1_system_size']['capacity_kw_dc']} kW")
print(f"Base cost: ${result['layer_2_base_cost']['base_cost_usd']:,.2f}")
print(f"Adjusted cost: ${result['layer_3_regional_adjustment']['adjusted_cost_usd']:,.2f}")
print(f"Net cost (after ITC): ${result['layer_4_incentives']['net_cost_usd']:,.2f}")

# Compare with simple calculation
print("\n--- Simple calculation for comparison ---")
panel_count_simple = int((1000 * 0.75) // 2.0)  # area * packing // panel_area
panel_cost_simple = panel_count_simple * 260.0
construction_cost_simple = 1000 * 140.0
total_cost_simple = panel_cost_simple + construction_cost_simple

print(f"Panel count (simple): {panel_count_simple}")
print(f"Panel cost (simple): ${panel_cost_simple:,.2f}")
print(f"Construction cost (simple): ${construction_cost_simple:,.2f}")
print(f"Total cost (simple): ${total_cost_simple:,.2f}")