"""Reproducible site-specific raster processing. All slope calculations are metric."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from fastapi import HTTPException
from rasterio.enums import Resampling
from rasterio.features import geometry_mask, shapes
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject, transform_geom
from shapely.geometry import mapping, shape
from shapely.ops import transform as geometry_transform
from pyproj import Transformer

from .geometry import area_km2, local_utm_crs
from .overlays import build_terrain_overlays
from .suitability import build_suitability
from .settings import MAX_RASTER_PIXELS
from .terrain_quality import (
    horn_slope_degrees, assess_gis_quality, save_projected_qa_grids,
    source_file_evidence, validate_raster_metadata,
)

SLOPE_CLASSES = [
    {"id": 1, "name": "Class I", "min_deg": 0, "max_deg": 15, "color": "#4cc9a3"},
    {"id": 2, "name": "Class II", "min_deg": 15, "max_deg": 25, "color": "#e5c46d"},
    {"id": 3, "name": "Class III", "min_deg": 25, "max_deg": 35, "color": "#eb8c64"},
    {"id": 4, "name": "Class IV", "min_deg": 35, "max_deg": None, "color": "#cb626f"},
]


def analyze_terrain(geom_wgs84: dict[str, Any], raster_path: Path, source_metadata: dict[str, Any],
                    analysis_id: str, artifacts_dir: Path | None = None) -> dict[str, Any]:
    """Returns evidence and WGS84 slope polygons, never a planning approval verdict."""
    try:
        with rasterio.open(raster_path) as src:
            validate_raster_metadata(src, source_metadata)
            input_crs = src.crs.to_string()
            input_nodata = src.nodata
            input_resolution = tuple(src.res)
            input_units = src.units[0] if src.units else None
            if src.width * src.height > 150_000_000:
                raise ValueError("Raster input terlalu besar untuk V1.")
            dst_crs = local_utm_crs(geom_wgs84)
            dst_transform, width, height = calculate_default_transform(src.crs, dst_crs, src.width, src.height, *src.bounds)
            # Calculate an output grid limited to site's projected extent + 2 pixels.
            project = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)
            projected_site = geometry_transform(project.transform, shape(geom_wgs84))
            xmin, ymin, xmax, ymax = projected_site.bounds
            resolution_x = abs(dst_transform.a)
            resolution_y = abs(dst_transform.e)
            if resolution_x < 0.01 or resolution_y < 0.01:
                raise ValueError("Unit atau resolusi raster tidak munasabah.")
            left, bottom = xmin - 3 * resolution_x, ymin - 3 * resolution_y
            right, top = xmax + 3 * resolution_x, ymax + 3 * resolution_y
            width = max(1, int(np.ceil((right - left) / resolution_x)))
            height = max(1, int(np.ceil((top - bottom) / resolution_y)))
            if width * height > MAX_RASTER_PIXELS:
                raise ValueError("Raster tapak melebihi had 2 juta pixel. Kurangkan saiz tapak/resolusi untuk V1.")
            from rasterio.transform import from_origin
            target_transform = from_origin(left, top, resolution_x, resolution_y)
            elevation = np.full((height, width), np.nan, dtype="float32")
            reproject(
                source=rasterio.band(src, 1), destination=elevation,
                src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                dst_transform=target_transform, dst_crs=dst_crs, dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
    except (ValueError, rasterio.errors.RasterioError, OSError) as ex:
        raise HTTPException(422, str(ex)) from ex

    inside = geometry_mask([mapping(projected_site)], out_shape=elevation.shape, transform=target_transform, invert=True)
    valid = inside & np.isfinite(elevation)
    if valid.sum() < 9:
        raise HTTPException(422, "Terlalu sedikit pixel DEM yang sah di dalam tapak (<9). Muat naik data lebih terperinci.")

    # QGIS gdal:slope uses GDAL's default Horn 3x3 derivative. Here the
    # source is FIRST reprojected to UTM metres; no edge interpolation and
    # no slope at/adjacent to a NoData source cell (no invented zero heights).
    slope = horn_slope_degrees(elevation, resolution_x, resolution_y)
    slope_valid = valid & np.isfinite(slope)
    if slope_valid.sum() < 9:
        raise HTTPException(422, "Pixel kecerunan sah tidak mencukupi. Semak liputan dan nilai NoData raster.")
    heights = elevation[valid].astype("float64")
    slopes = slope[slope_valid]
    classes = np.zeros(elevation.shape, dtype="uint8")
    classes[slope_valid] = 1
    classes[slope_valid & (slope >= 15)] = 2
    classes[slope_valid & (slope >= 25)] = 3
    classes[slope_valid & (slope >= 35)] = 4
    pixel_area_m2 = resolution_x * resolution_y
    site_area_km2 = area_km2(geom_wgs84)
    # Both numerator and denominator use the SAME cell-centre site mask.
    # Comparing pixel area directly with geodesic polygon area gives >100%
    # coverage on narrow/angled sites and hides missing cells.
    site_center_count = int(np.count_nonzero(inside))
    coverage_pct = min(100.0, float(np.count_nonzero(valid)) / site_center_count * 100)

    cls_stats = []
    for item in SLOPE_CLASSES:
        count = int(np.count_nonzero(classes == item["id"]))
        cls_stats.append({**item, "area_ha_est": round(count * pixel_area_m2 / 10000, 3), "percent_of_valid_slope": round(count / slope_valid.sum() * 100, 2)})

    geojson_features: list[dict[str, Any]] = []
    truncated_overlay = False
    for geometry, value in shapes(classes, mask=(classes > 0), transform=target_transform):
        if len(geojson_features) >= 1200:
            truncated_overlay = True
            break
        wgs84_geom = transform_geom(dst_crs, "EPSG:4326", geometry, precision=6)
        geojson_features.append({"type": "Feature", "properties": {"class_id": int(value)}, "geometry": wgs84_geom})

    overlays = build_terrain_overlays(elevation, valid, target_transform, dst_crs, source_metadata)
    suitability = build_suitability(
        slope_degrees=slope, valid_slope=slope_valid, inside_site=inside,
        pixel_area_m2=pixel_area_m2, site_area_ha=site_area_km2 * 100,
        transform=target_transform, crs=dst_crs, source=source_metadata,
    )
    quality = assess_gis_quality(
        site_cells=site_center_count,
        elevation_cells=int(valid.sum()), slope_cells=int(slope_valid.sum()),
        raster_type=str(source_metadata.get("data_type", "unknown")),
        source_id=str(source_metadata.get("id", "")),
        vertical_datum=str(source_metadata.get("vertical_datum", "")),
        source_pixel_m=float(source_metadata["nominal_resolution_m"])
        if source_metadata.get("nominal_resolution_m") else None,
        analysed_pixel_m=float((resolution_x + resolution_y) / 2),
        site_area_ha=site_area_km2 * 100, pixel_area_m2=pixel_area_m2,
        contour_count=len(overlays["contours_geojson"]["features"]),
        overlay_truncated=truncated_overlay or overlays["contours_truncated"]
                          or overlays["elevation_overlay_truncated"],
    )
    provenance = source_file_evidence(
        raster_path, input_crs=input_crs, input_nodata=input_nodata,
        source_resolution=input_resolution, input_units=input_units,
    )
    if artifacts_dir is not None:
        save_projected_qa_grids(artifacts_dir, elevation, slope, dst_crs, target_transform)

    warnings = [
        "Penilaian ini ialah saringan topografi, BUKAN keputusan keseluruhan kesesuaian pembangunan atau kelulusan PBT.",
        "Kecerunan menggunakan Horn 3x3 pada grid UTM dalam meter, seperti pilihan lalai GDAL/QGIS gdal:slope. NoData dan tepi 3x3 tidak dinilai.",
        "Luas mengikut kelas ialah anggaran berasaskan pixel; kawasan sempadan mungkin mempunyai ralat pengukuran.",
    ]
    if "DSM" in str(source_metadata.get("data_type", "")):
        warnings.append("DSM mungkin mengandungi bangunan/vegetasi; tidak setara dengan DTM ukur tanah untuk reka bentuk kerja tanah.")
    if source_metadata.get("fallback_used"):
        warnings.append("GLO-30 Public tidak tersedia; sistem menggunakan GLO-90 DSM sekitar 90 m. Hasil kurang terperinci.")
    if overlays["contours_truncated"] or overlays["elevation_overlay_truncated"]:
        warnings.append("Overlay kontur/elevasi disederhanakan untuk prestasi; statistik GIS menggunakan pixel sah sepenuhnya.")
    if not overlays["contours_geojson"]["features"]:
        warnings.append("Tiada garis kontur pada sela yang munasabah untuk julat ketinggian dan resolusi sumber ini.")
    if source_metadata.get("id") == "user-upload":
        warnings.append("Dataset pengguna belum disahkan sumber, datum menegak, unit ketinggian atau ketepatan ukur. Semak metadata asal sebelum keputusan teknikal.")
    if coverage_pct < 95:
        warnings.append(f"Liputan elevasi bagi sel pusat dalam tapak ialah {coverage_pct:.1f}%; bahagian tanpa data bukan tanah sesuai.")
    if quality["slope_site_cell_coverage_pct"] < 95:
        warnings.append("Liputan cerun lebih rendah daripada liputan elevasi kerana semakan kejiranan 3x3; sel tiada cerun tidak boleh dianggap landai.")
    warnings.extend(f"GIS QA: {flag}" for flag in quality["flags"])
    if valid.sum() < 100:
        warnings.append("Kurang daripada 100 pixel ketinggian sah di tapak; statistik cerun sangat sensitif kepada resolusi.")
    if truncated_overlay:
        warnings.append("Peta polygon cerun dihadkan kepada 1,200 features untuk prestasi; statistik raster penuh tidak dihadkan.")
    if suitability["summary"]["area_exceeds_site_due_to_pixelization"]:
        warnings.append("Keluasan piksel kelas saringan melebihi keluasan geodesik tapak kerana resolusi/sel sempadan; bukan ukuran lot.")
    if suitability["summary"]["class_overlay_truncated"]:
        warnings.append("Polygon kesesuaian dihadkan untuk paparan; statistik kelas tetap berdasarkan semua piksel sah.")

    return {
        "analysis_id": analysis_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "geometry": geom_wgs84,
        "source": source_metadata,
        "metrics": {
            "site_area_ha": round(site_area_km2 * 100, 3),
            "valid_elevation_pixels": int(valid.sum()),
            "valid_slope_pixels": int(slope_valid.sum()),
            "coverage_percent_est": round(coverage_pct, 2),
            "coverage_method": "valid elevation cells / all site-centre cells in the same UTM grid",
            "slope_coverage_percent": quality["slope_site_cell_coverage_pct"],
            "site_mask_pixels": site_center_count,
            "elevation_min_m": round(float(heights.min()), 2),
            "elevation_mean_m": round(float(heights.mean()), 2),
            "elevation_max_m": round(float(heights.max()), 2),
            "elevation_range_m": round(float(heights.max() - heights.min()), 2),
            "slope_mean_deg": round(float(np.mean(slopes)), 2),
            "slope_max_deg": round(float(np.max(slopes)), 2),
            "slope_classes": cls_stats,
            "contour_interval_m": overlays["contour_interval_m"],
            "contour_features": len(overlays["contours_geojson"]["features"]),
            "elevation_legend": overlays["elevation_legend"],
            "analysis_resolution_m_est": round(float((resolution_x + resolution_y) / 2), 2),
            "method": "Rasterio bilinear reprojection to local UTM; GDAL Horn-equivalent 3x3 z-per-metre; atan(hypot(dz/dx,dz/dy)), degrees; no edge/NoData interpolation; cell-area estimates.",
            "horizontal_crs": dst_crs.to_string(),
            "vertical_units_assumption": "metres (MUST be checked against original source metadata)",
        },
        "slope_geojson": {"type": "FeatureCollection", "features": geojson_features},
        "suitability": suitability["summary"],
        "suitability_geojson": suitability["geojson"],
        "elevation_geojson": overlays["elevation_geojson"],
        "contours_geojson": overlays["contours_geojson"],
        "quality": quality,
        "source_file": provenance,
        "qa_artifacts": {"projected_elevation": "elevation_utm.tif",
                         "projected_slope": "slope_degrees_utm.tif",
                         "qgis_verification": "pending_external_comparison"}
        if artifacts_dir is not None else None,
        "warnings": warnings,
        "assessment_scope": "Terrain screening only; no planning-law compliance, hydrology, geotechnical, or development approval conclusion.",
    }
