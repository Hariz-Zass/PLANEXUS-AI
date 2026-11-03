"""Owner-protected PLANEXUS GIS vector and raster export.

Vector layers intentionally represent saved WGS84 map overlays and may be
truncated. Full-resolution elevations and slopes are in the attached UTM
GeoTIFF rasters. Fiona creates a real OGC GeoPackage, not a renamed GeoJSON.
"""
from __future__ import annotations

import json
import math
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fiona
import rasterio
from fastapi import HTTPException
from shapely.geometry import shape
from .backup_restore import sha256_file

VECTOR_KEYS = {
    "slope_classes": "slope_geojson",
    "elevation_bands": "elevation_geojson",
    "contours": "contours_geojson",
    "suitability": "suitability_geojson",
}
GPKG_SCHEMA = {
    "geometry": "Unknown",
    "properties": {
        "class_id": "int",
        "elevation_m": "float",
        "site_name": "str:100",
        "analysis_id": "str:40",
        "screening": "int",
    },
}


def iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def vector_layers(project: dict[str, Any], report: dict[str, Any] | None) -> dict[str, Any]:
    geometry = project.get("geometry")
    if geometry is None:
        raise HTTPException(422, "Simpan sempadan projek sebelum mengeksport GIS.")
    data = {"site_boundary": {
        "type": "FeatureCollection",
        "features": [{"type": "Feature",
                      "properties": {"site_name": project["name"]},
                      "geometry": geometry}],
    }}
    if report:
        for name, key in VECTOR_KEYS.items():
            collection = report.get(key)
            if collection is None:
                # A legacy analysis without a layer cannot be silently
                # advertised as a complete vector export.
                continue
            if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection":
                raise HTTPException(503, "Lapisan GIS yang disimpan rosak.")
            data[name] = collection
    return data


def _validated_features(collection: dict[str, Any]) -> list[dict[str, Any]]:
    values = collection.get("features")
    if not isinstance(values, list) or len(values) > 10000:
        raise HTTPException(503, "GIS vector feature list invalid or exceeds export limit.")
    validated = []
    for item in values:
        if not isinstance(item, dict) or not isinstance(item.get("geometry"),dict):
            raise HTTPException(503, "Invalid GIS feature in saved report.")
        try:
            geom = shape(item["geometry"])
            if geom.is_empty or not geom.is_valid or geom.geom_type not in (
                "Polygon","MultiPolygon","LineString","MultiLineString"
            ):
                raise ValueError("Invalid or unsupported geometry.")
            props = item.get("properties") or {}
            if not isinstance(props, dict):
                raise ValueError("Invalid vector attributes.")
        except (TypeError, ValueError, KeyError) as exc:
            raise HTTPException(503, "Corrupted saved GIS vector geometry.") from exc
        validated.append(item)
    return validated


def create_geopackage(destination: Path, project: dict[str, Any],
                      report: dict[str, Any] | None) -> dict[str, int]:
    """Write multiple real EPSG:4326 feature layers with Fiona/GDAL."""
    layers = vector_layers(project,report)
    counts: dict[str,int] = {}
    for name, collection in layers.items():
        features = _validated_features(collection)
        with fiona.open(
            destination,mode="w",driver="GPKG",layer=name,crs="EPSG:4326",
            schema=GPKG_SCHEMA,encoding="UTF-8"
        ) as sink:
            for feature in features:
                attrs=feature.get("properties") or {}
                class_id=attrs.get("class_id")
                elevation=attrs.get("elevation_m")
                try:
                    cid=int(class_id) if class_id is not None else None
                    height=float(elevation) if elevation is not None else None
                except (TypeError, ValueError, OverflowError) as exc:
                    raise HTTPException(503,"Invalid GIS class/elevation attributes.") from exc
                if height is not None and not math.isfinite(height):
                    raise HTTPException(503,"Non-finite contour elevation in saved report.")
                sink.write({
                    "type":"Feature",
                    "geometry":feature["geometry"],
                    "properties":{
                        "class_id":cid,
                        "elevation_m":height,
                        "site_name":project["name"][:100],
                        "analysis_id":report["analysis_id"] if report else None,
                        "screening":1,
                    }
                })
        counts[name]=len(features)
    return counts


def manifest(project: dict[str, Any], report: dict[str, Any] | None,
             feature_counts: dict[str,int]) -> dict[str, Any]:
    truncation = (report or {}).get("overlay_status") or {}
    status={}
    for name,count in feature_counts.items():
        flag = (name + "_geojson_truncated")
        # Existing slope status key differs from exported friendly layer.
        mapping = {
            "slope_classes":"slope_geojson_truncated",
            "elevation_bands":"elevation_geojson_truncated",
            "contours":"contours_geojson_truncated",
            "suitability":"suitability_geojson_truncated",
        }
        key=mapping.get(name)
        status[name]={
            "feature_count":count,
            "preview_only":name!="site_boundary",
            "truncated":truncation.get(key) if key else False,
            "completeness_known":name=="site_boundary" or key in truncation,
        }
    return {
        "format_version":"b3.4-v1",
        "generated_at_utc":iso(),
        "project":{"id":project["id"],"name":project["name"],
                   "revision":project["revision"],"geometry_crs":"EPSG:4326"},
        "analysis_id":report["analysis_id"] if report else None,
        "source":report.get("source") if report else None,
        "quality":report.get("quality") if report else None,
        "source_file":report.get("source_file") if report else None,
        "analysis_crs":report.get("metrics",{}).get("horizontal_crs") if report else None,
        "vector_layers":status,
        "vector_crs":"EPSG:4326",
        "raster_crs":"UTM metres; read individual GeoTIFF CRS tags",
        "vertical_units":"metres assumed; validate source vertical datum independently",
        "warnings":[
            "Slope/elevation/suitability GeoPackage vectors reflect rendered layers; "
            "they are NOT guaranteed complete full-resolution polygons.",
            "Consult the full-resolution UTM GeoTIFF layers for analysis.",
            "Project site boundary and saved active analysis geometry may differ; "
            "check project revision and reanalyse after boundary changes.",
            "Preliminary DSM/DTM screening is not zoning, engineering or PBT approval.",
        ],
    }


def _raster_assets(job: Path, report: dict[str, Any]) -> dict[str, Path]:
    sources = {}
    for label, filename in (
        ("elevation_utm.tif","elevation_utm.tif"),
        ("slope_degrees_utm.tif","slope_degrees_utm.tif"),
        ("uploaded_source.tif","uploaded_source.tif"),
        ("source_clipped.tif","source_clipped.tif"),
    ):
        target=job/filename
        if target.is_symlink():
            raise HTTPException(503,"Raster symlink is not accepted for export.")
        if target.is_file():
            try:
                with rasterio.open(target) as grid:
                    if grid.crs is None or grid.count < 1:
                        raise ValueError("GeoTIFF must have CRS and raster bands.")
            except (rasterio.errors.RasterioError, ValueError) as exc:
                raise HTTPException(503,"Saved raster is corrupt or missing CRS.") from exc
            if filename in ("uploaded_source.tif","source_clipped.tif"):
                expected=(report.get("source_file") or {}).get("sha256")
                if expected and sha256_file(target)[1] != expected:
                    raise HTTPException(503,"Original GIS raster SHA-256 no longer matches report.")
            sources[label]=target
    return sources


def create_export_bundle(directory: Path, project: dict[str, Any],
                         report: dict[str, Any] | None, job_dir: Path | None) -> Path:
    directory.mkdir(parents=True,exist_ok=True)
    layers=vector_layers(project,report)
    gpkg=directory/"planexus_layers.gpkg"
    counts=create_geopackage(gpkg,project,report)
    documented=manifest(project,report,counts)
    assets:dict[str,Path]={}
    assets["vector/planexus_layers.gpkg"]=gpkg
    for name,collection in layers.items():
        target=directory/(name+".geojson")
        _validated_features(collection)
        target.write_text(json.dumps(collection,ensure_ascii=False,allow_nan=False),
                          encoding="utf-8")
        assets["vector/"+name+".geojson"]=target
    if report and job_dir:
        for name,path in _raster_assets(job_dir, report).items():
            assets["raster/"+name]=path
        if not any(n.startswith("raster/") for n in assets):
            documented["warnings"].append(
                "This LEGACY analysis had no accessible original or derived raster; only cartographic vectors exported."
            )
    documented["files"]={
        name:{"size_bytes":sha256_file(path)[0],"sha256":sha256_file(path)[1]}
        for name,path in assets.items()
    }
    documented["gpkg_layer_counts"]=counts
    manifest_path=directory/"export-manifest.json"
    manifest_path.write_text(json.dumps(documented,indent=2,ensure_ascii=False,allow_nan=False),
                             encoding="utf-8")
    zip_path=directory/"PLANEXUS-GIS-export.zip"
    with zipfile.ZipFile(zip_path,mode="x",compression=zipfile.ZIP_DEFLATED,
                         compresslevel=5,allowZip64=True) as archive:
        for name,path in sorted(assets.items()):
            archive.write(path,arcname=name)
        archive.write(manifest_path,arcname="export-manifest.json")
    return zip_path
