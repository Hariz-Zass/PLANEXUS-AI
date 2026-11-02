"""Terrain-only development suitability screening, derived from measured slope pixels.

These are illustrative PLANEXUS screening bands, NOT statutory Malaysian
planning rules and NOT a finding that construction is permitted or safe.
Do not silently extrapolate across NoData, unsampled areas or coarse DSM cells.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from rasterio.features import shapes
from rasterio.warp import transform_geom

# Do not equate these screening groups with statutory slope classification.
SUITABILITY_BANDS = (
    {"id": 1, "key": "lower_constraint", "label": "Lower terrain constraint",
     "min_deg": 0, "max_deg": 15, "color": "#7bd99e",
     "reason": "Slope below 15 degrees. Topographic screening only; not an approval."},
    {"id": 2, "key": "moderate_constraint", "label": "Moderate terrain constraint",
     "min_deg": 15, "max_deg": 25, "color": "#e7ca76",
     "reason": "Slope 15 to below 25 degrees. Detailed site and engineering checks required."},
    {"id": 3, "key": "higher_constraint", "label": "Higher terrain constraint",
     "min_deg": 25, "max_deg": None, "color": "#e78282",
     "reason": "Slope 25 degrees or above. Flag for closer assessment; not an automatic prohibition."},
    {"id": 4, "key": "unassessed", "label": "Not assessed",
     "min_deg": None, "max_deg": None, "color": "#80919a",
     "reason": "No validated slope sample at this cell. Suitability cannot be inferred."},
)

LIMITATIONS = (
    "The thresholds are provisional PLANEXUS terrain-screening assumptions, not "
    "RT/RSN/RKK/GPP, PBT approval conditions, engineering specifications or "
    "geotechnical safety classes. Results cannot establish permitted development, "
    "unit yield, zoning, road access, hydrology or slope stability."
)


def build_suitability(
    *,
    slope_degrees: np.ndarray,
    valid_slope: np.ndarray,
    inside_site: np.ndarray,
    pixel_area_m2: float,
    site_area_ha: float,
    transform: Any,
    crs: Any,
    source: dict[str, Any],
    max_features: int = 1200,
) -> dict[str, Any]:
    """Generate reproducible per-cell screening, summaries and limited WGS84 overlays.

    Areas are full-cell approximations in the projected metric raster. Border
    cells can exceed the true polygon area. Never force them to sum to a
    geodesic area or treat missing cells as gentle terrain.
    """
    if slope_degrees.shape != valid_slope.shape or valid_slope.shape != inside_site.shape:
        raise ValueError("Mismatch between slope, valid mask and site mask.")
    if (not np.isfinite(pixel_area_m2)) or pixel_area_m2 <= 0 or site_area_ha <= 0:
        raise ValueError("A positive projected pixel area and site area are required.")
    if not np.any(valid_slope):
        raise ValueError("No verified slope pixels are available for screening.")
    if max_features < 1:
        raise ValueError("max_features must be positive.")

    valid = inside_site & valid_slope & np.isfinite(slope_degrees) & (slope_degrees >= 0)
    if not np.any(valid):
        raise ValueError("No valid slope pixels inside the selected site.")
    codes = np.zeros(slope_degrees.shape, dtype="uint8")
    codes[inside_site] = 4
    codes[valid & (slope_degrees < 15)] = 1
    codes[valid & (slope_degrees >= 15) & (slope_degrees < 25)] = 2
    codes[valid & (slope_degrees >= 25)] = 3

    valid_count = int(np.count_nonzero(valid))
    inside_count = int(np.count_nonzero(inside_site))
    stats: list[dict[str, Any]] = []
    for band in SUITABILITY_BANDS:
        count = int(np.count_nonzero(codes == band["id"]))
        area = count * pixel_area_m2 / 10000
        stats.append({
            **band, "pixels": count,
            "area_ha_est": round(float(area), 4),
            "share_of_assessed_pct": (round(count * 100 / valid_count, 2) if band["id"] <= 3 else None),
        })

    measured_ha = valid_count * pixel_area_m2 / 10000
    unassessed_cells = (inside_count - valid_count) * pixel_area_m2 / 10000
    # Approximate uncovered area includes raster-grid boundary effects. It must
    # be labelled as an estimate rather than a measured land polygon.
    unassessed_total = max(site_area_ha - measured_ha, unassessed_cells, 0.0)
    oversampled = measured_ha > site_area_ha * 1.02
    features: list[dict[str, Any]] = []
    truncated = False
    for geom, category in shapes(codes, mask=codes > 0, transform=transform):
        if len(features) >= max_features:
            truncated = True
            break
        features.append({
            "type": "Feature",
            "properties": {"class_id": int(category), "screening_only": True},
            "geometry": transform_geom(crs, "EPSG:4326", geom, precision=6),
        })

    source_resolution = source.get("nominal_resolution_m")
    notes = [
        "Topographic-only screening, not a land use, structural safety or planning approval.",
        "Areas are projected-pixel estimates and do not exactly measure cadastral polygons.",
        "The classes are fixed provisional assumptions: 0–<15, 15–<25, and ≥25 degrees.",
    ]
    if "DSM" in str(source.get("data_type", "")).upper():
        notes.append("DSM may include buildings and vegetation; use an authorized DTM or survey for design.")
    if source_resolution is not None and float(source_resolution) >= 90:
        notes.append("Coarse ~90 m DSM may hide local slopes and is unsuitable for small-site decisions.")
    if valid_count < 100:
        notes.append("Fewer than 100 valid slope pixels; areas and classes are particularly uncertain.")
    if unassessed_total > site_area_ha * 0.05:
        notes.append("Part of the site is unassessed; do not classify absent measurements as gentle terrain.")
    if oversampled:
        notes.append("Projected cell count exceeds the geodesic site area due to coarse boundary cells; category hectares may exceed the polygon area.")
    if truncated:
        notes.append("Map polygons truncated to limit payload size; category statistics still use all eligible pixels.")

    return {
        "summary": {
            "version": "1.0.0",
            "method": "PLANEXUS provisional terrain-only screening from the analyzed projected DEM slope grid.",
            "bands": stats,
            "assessed_pixels": valid_count,
            "site_mask_pixels": inside_count,
            "assessed_area_ha_est": round(float(measured_ha), 4),
            "unassessed_area_ha_est": round(float(unassessed_total), 4),
            "coverage_of_site_pct_est": round(float(min(100, measured_ha / site_area_ha * 100)), 2),
            "area_exceeds_site_due_to_pixelization": bool(oversampled),
            "source_resolution_m": source_resolution,
            "class_overlay_truncated": truncated,
            "disclaimer": LIMITATIONS,
            "warnings": notes,
        },
        "geojson": {"type": "FeatureCollection", "features": features},
    }
