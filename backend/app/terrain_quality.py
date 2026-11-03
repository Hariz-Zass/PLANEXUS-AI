"""B3.3 GIS audit primitives — explicit Horn slope and provenance, no invented data.

The default QGIS Processing 'gdal:slope' is backed by GDAL's Horn 3x3
operator. All inputs here MUST first be reprojected to a metre-based UTM grid.
An insufficient 3x3 neighbourhood (NoData or raster edge) has no slope value.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from fastapi import HTTPException


def horn_slope_degrees(elevation: np.ndarray, x_m: float, y_m: float) -> np.ndarray:
    """GDAL Horn 3x3 convention without artificial NoData/edge interpolation."""
    if not math.isfinite(x_m) or not math.isfinite(y_m) or x_m <= 0 or y_m <= 0:
        raise ValueError("Slope grid requires finite positive horizontal metres.")
    z = np.asarray(elevation, dtype="float64")
    result = np.full(z.shape, np.nan, dtype="float32")
    if z.ndim != 2 or min(z.shape) < 3:
        return result
    rows, columns = z.shape
    patches = [z[dy:rows - 2 + dy, dx:columns - 2 + dx]
               for dy in range(3) for dx in range(3)]
    good = np.ones((rows-2, columns-2), dtype=bool)
    for value in patches:
        good &= np.isfinite(value)
    northwest, north, northeast, west, centre, east, southwest, south, southeast = patches
    dx = ((northeast + 2 * east + southeast)
          - (northwest + 2 * west + southwest)) / (8 * x_m)
    dy = ((southwest + 2 * south + southeast)
          - (northwest + 2 * north + northeast)) / (8 * y_m)
    slope = np.degrees(np.arctan(np.hypot(dx, dy)))
    inside = result[1:-1, 1:-1]
    inside[good] = slope[good].astype("float32")
    return result


def source_file_evidence(path: Path, *, input_crs: str, input_nodata: float | None,
                         source_resolution: tuple[float, float],
                         input_units: str | None) -> dict[str, Any]:
    sha = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            total += len(chunk)
            sha.update(chunk)
    return {
        "sha256": sha.hexdigest(), "size_bytes": total,
        "input_crs": input_crs,
        "input_nodata": input_nodata if input_nodata is not None and math.isfinite(input_nodata) else None,
        "input_pixel_size_in_crs_units": [round(float(v), 9) for v in source_resolution],
        "input_vertical_band_unit": input_units or "not declared in raster",
        "source_authenticity_independently_verified": False,
        "horizontal_reprojection": "Rasterio/GDAL bilinear -> local UTM metres",
    }


def assess_gis_quality(*, site_cells: int, elevation_cells: int, slope_cells: int,
                       raster_type: str, source_pixel_m: float | None,
                       analysed_pixel_m: float, site_area_ha: float,
                       pixel_area_m2: float, contour_count: int,
                       overlay_truncated: bool) -> dict[str, Any]:
    """Quality of THIS COMPUTATION, never field/survey accuracy certification."""
    if site_cells <= 0 or elevation_cells <= 0 or slope_cells <= 0:
        raise ValueError("Cannot assess empty raster/site intersection.")
    elevation_pct = 100 * elevation_cells / site_cells
    slope_pct = 100 * slope_cells / site_cells
    site_area_grid_ha = site_cells * pixel_area_m2 / 10_000
    area_disagreement_pct = (abs(site_area_grid_ha - site_area_ha) / site_area_ha * 100
                             if site_area_ha > 0 else None)
    flags: list[str] = []
    if elevation_pct < 95:
        flags.append("Elevation NoData/missing coverage exceeds 5% of the site-centre cells.")
    if slope_pct < 95:
        flags.append("Slope not computed for every site cell: 3x3 support/NoData or edge is missing.")
    if slope_cells < 100:
        flags.append("Fewer than 100 valid slope cells; statistics sensitive to raster resolution.")
    if source_pixel_m and analysed_pixel_m < source_pixel_m * .65:
        flags.append("Projected processing grid is finer than source nominal resolution; no additional detail is created.")
    if area_disagreement_pct is not None and area_disagreement_pct > 10:
        flags.append("Pixel-centre area differs by over 10% from geodesic site area.")
    if "DSM" in raster_type.upper():
        flags.append("DSM includes trees/buildings; it is NOT a bare-earth DTM or site survey.")
    if raster_type in ("DEM-unknown", "unknown", ""):
        flags.append("Elevation surface type is not independently confirmed.")
    if overlay_truncated:
        flags.append("Map overlay features were truncated; statistics still use all valid raster cells.")
    if contour_count == 0:
        flags.append("No contours generated at the selected interval; low relief or insufficient cells may explain this.")
    return {
        "version": "b3.3-horn-v1",
        "status": "limited" if slope_pct < 90 or elevation_pct < 90 or slope_cells < 25 else
                  "review" if flags else "screening",
        "elevation_site_cell_coverage_pct": round(elevation_pct, 2),
        "slope_site_cell_coverage_pct": round(slope_pct, 2),
        "site_center_cells": int(site_cells),
        "site_grid_area_ha_est": round(site_area_grid_ha, 3),
        "geodesic_vs_cell_area_difference_pct": round(area_disagreement_pct, 2)
        if area_disagreement_pct is not None else None,
        "method": "Horn 3x3 (same algorithm option as QGIS gdal:slope, scale=1, no edge interpolation); metre-based UTM.",
        "external_gdal_qgis_comparison": "Not performed on this analysis; CI separately tests the exact raster method on synthetic surfaces.",
        "terrain_screening_only": True,
        "field_vertical_accuracy_verified": False,
        "flags": flags,
    }


def save_projected_qa_grids(directory: Path, elevation: np.ndarray, slope: np.ndarray,
                            utm_crs: Any, transform: Any) -> None:
    """Preserve the EXACT projected DEM and slope surface for external QGIS QA."""
    directory.mkdir(parents=True, exist_ok=True)
    for filename, array in (("elevation_utm.tif", elevation),
                            ("slope_degrees_utm.tif", slope)):
        with rasterio.open(
            directory / filename, "w", driver="GTiff",
            width=array.shape[1], height=array.shape[0], count=1,
            crs=utm_crs, transform=transform, dtype="float32",
            nodata=-9999., compress="deflate",
        ) as dst:
            dst.write(np.where(np.isfinite(array), array, -9999.).astype("float32"), 1)


def validate_raster_metadata(src: rasterio.io.DatasetReader, source: dict[str, Any]) -> None:
    if src.crs is None or src.count != 1:
        raise HTTPException(422, "GeoTIFF ketinggian mesti mempunyai satu band dan CRS yang sah.")
    if src.dtypes[0].startswith(("complex", "uint64", "int64")):
        raise HTTPException(422, "Jenis data band ketinggian tidak disokong.")
    if not all(math.isfinite(v) for v in tuple(src.transform)[:6]):
        raise HTTPException(422, "GeoTransform mengandungi nilai bukan nombor.")
    if not all(math.isfinite(x) and x > 0 for x in map(abs, src.res)):
        raise HTTPException(422, "Resolusi/transform geospatial tidak sah.")
    declared_unit = src.units[0] if src.units else None
    if declared_unit and declared_unit.strip().lower() in (
        "ft", "foot", "feet", "us survey foot", "us-ft", "international foot"
    ):
        raise HTTPException(422, "Raster menyatakan unit kaki sedangkan PLANEXUS V1 mengira dalam meter. Tukar unit ketinggian terlebih dahulu.")
    if not isinstance(source.get("data_type"), str):
        raise HTTPException(422, "Jenis DEM/DSM/DTM mesti dinyatakan sebagai metadata.")
