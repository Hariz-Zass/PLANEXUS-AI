from __future__ import annotations

import math
from typing import Any

from fastapi import HTTPException
from pyproj import CRS, Geod, Transformer
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import transform

from .settings import MAX_SITE_AREA_KM2

_GEOD = Geod(ellps="WGS84")


def validate_site(value: dict[str, Any]) -> dict[str, Any]:
    """Accept a GeoJSON WGS84 polygon (optionally wrapped in a Feature)."""
    if not isinstance(value, dict):
        raise HTTPException(422, "Tapak mesti GeoJSON Polygon atau MultiPolygon.")
    if value.get("type") == "Feature":
        value = value.get("geometry") or {}
    try:
        if value.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError("Hanya Polygon / MultiPolygon disokong.")
        geom = shape(value)
        if not isinstance(geom, (Polygon, MultiPolygon)) or geom.is_empty or not geom.is_valid:
            raise ValueError("Geometri tapak tidak sah atau mempunyai self-intersection.")
        if not all(math.isfinite(v) for xy in geom.bounds for v in [xy]):
            raise ValueError("Koordinat tidak sah.")
        west, south, east, north = geom.bounds
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("GeoJSON mesti menggunakan longitude/latitude WGS84 (EPSG:4326).")
        if east - west > 1 or north - south > 1:
            raise ValueError("Untuk V1, tapak perlu berada dalam extent 1° x 1°.")
        area_m2 = abs(_GEOD.geometry_area_perimeter(geom)[0])
        if area_m2 <= 0 or area_m2 / 1e6 > MAX_SITE_AREA_KM2:
            raise ValueError(f"Luas tapak mesti > 0 dan tidak melebihi {MAX_SITE_AREA_KM2:g} km² bagi V1.")
        # The number of vertices is bounded to reduce abuse / expensive raster masks.
        coordinates_count = sum(len(ring.coords) for poly in (geom.geoms if isinstance(geom, MultiPolygon) else [geom]) for ring in [poly.exterior, *poly.interiors])
        if coordinates_count > 5000:
            raise ValueError("Terlalu banyak vertex (>5,000) untuk V1.")
        return mapping(geom)
    except (ValueError, TypeError, KeyError, IndexError) as ex:
        raise HTTPException(422, str(ex)) from ex


def area_km2(geometry: dict[str, Any]) -> float:
    return abs(_GEOD.geometry_area_perimeter(shape(geometry))[0]) / 1e6


def local_utm_crs(geometry: dict[str, Any]) -> CRS:
    center = shape(geometry).centroid
    zone = int((center.x + 180) // 6) + 1
    zone = min(60, max(1, zone))
    return CRS.from_epsg((32600 if center.y >= 0 else 32700) + zone)


def to_crs(geometry: dict[str, Any], src_crs: Any, dst_crs: Any) -> dict[str, Any]:
    t = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    return mapping(transform(t.transform, shape(geometry)))
