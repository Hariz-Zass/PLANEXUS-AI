"""Public Copernicus COG adapter: bounded, source-attributed, no invented raster."""
from __future__ import annotations

import math
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from fastapi import HTTPException
from rasterio.enums import Resampling
from rasterio.merge import merge

from .settings import MAX_RASTER_PIXELS

SOURCE_CATALOG = [
    {
        "id": "copernicus-glo30-public", "name": "Copernicus DEM GLO-30 Public",
        "publisher": "Copernicus Programme / ESA; public AWS distribution",
        "data_type": "DSM (includes vegetation and built structures)",
        "nominal_resolution_m": 30, "resolution_arcsec": 10,
        "access": "Public AWS Cloud Optimized GeoTIFF windows, without API key",
        "reference": "https://registry.opendata.aws/copernicus-dem/",
        "metadata": "https://copernicus-dem-30m.s3.amazonaws.com/readme.html",
        "intended_use": "Preliminary terrain screening only",
        "warning": "DSM is not a surveyed bare-earth DTM. GLO-30 Public does not cover every land tile.",
    },
    {
        "id": "copernicus-glo90-public", "name": "Copernicus DEM GLO-90 Public (fallback)",
        "publisher": "Copernicus Programme / ESA; public AWS distribution",
        "data_type": "DSM (includes vegetation and built structures)",
        "nominal_resolution_m": 90, "resolution_arcsec": 30,
        "access": "Public AWS Cloud Optimized GeoTIFF windows, without API key",
        "reference": "https://registry.opendata.aws/copernicus-dem/",
        "metadata": "https://copernicus-dem-90m.s3.amazonaws.com/readme.html",
        "intended_use": "Coarser preliminary screening when GLO-30 Public is unavailable",
        "warning": "Fallback raster has roughly 90 m native resolution; small sites may have insufficient pixels.",
    },
]


def tile_name(latitude: int, longitude: int, resolution_arcsec: int = 10) -> str:
    if resolution_arcsec not in (10, 30):
        raise ValueError("Unsupported Copernicus COG angular resolution.")
    lat = f"{'N' if latitude >= 0 else 'S'}{abs(latitude):02d}_00"
    lon = f"{'E' if longitude >= 0 else 'W'}{abs(longitude):03d}_00"
    return f"Copernicus_DSM_COG_{resolution_arcsec}_{lat}_{lon}_DEM"


def copernicus_tiles(bounds: tuple[float, float, float, float], resolution_arcsec: int = 10) -> list[str]:
    west, south, east, north = bounds
    if not all(math.isfinite(v) for v in bounds) or not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise HTTPException(422, "Invalid WGS84 bounds for DEM retrieval.")
    bucket = "copernicus-dem-30m" if resolution_arcsec == 10 else "copernicus-dem-90m"
    tiles = [
        f"https://{bucket}.s3.amazonaws.com/{tile_name(lat, lon, resolution_arcsec)}/{tile_name(lat, lon, resolution_arcsec)}.tif"
        for lat in range(math.floor(south), math.ceil(north))
        for lon in range(math.floor(west), math.ceil(east))
    ]
    if not tiles or len(tiles) > 9:
        raise HTTPException(422, "Site spans too many DEM tiles for V1 (max 9).")
    return tiles


def _clip_cogs(urls: list[str], bounds: tuple[float, float, float, float], path: Path) -> None:
    """Read only a small window from authenticated-by-provenance public COG URLs."""
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        GDAL_HTTP_TIMEOUT="30", GDAL_HTTP_MAX_RETRY="2",
        GDAL_HTTP_RETRY_DELAY="1", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    ):
        with ExitStack() as stack:
            sources = [stack.enter_context(rasterio.open(url)) for url in urls]
            if any(src.crs is None or src.count < 1 for src in sources):
                raise ValueError("Copernicus tile has no readable CRS or elevation band.")
            if any(src.crs != sources[0].crs for src in sources):
                raise ValueError("Incompatible tile CRS.")
            if sources[0].crs.to_epsg() != 4326:
                raise ValueError("Expected georeferenced EPSG:4326 Copernicus COG tiles.")
            west, south, east, north = bounds
            native_x = min(abs(src.res[0]) for src in sources)
            native_y = min(abs(src.res[1]) for src in sources)
            if native_x <= 0 or native_y <= 0:
                raise ValueError("Invalid raster pixel size.")
            estimated_pixels = (math.ceil((east-west) / native_x) + 4) * (math.ceil((north-south) / native_y) + 4)
            if estimated_pixels > MAX_RASTER_PIXELS:
                raise ValueError("Requested DEM area exceeds safe processing size.")
            array, transform = merge(
                sources, bounds=bounds, nodata=-9999.0,
                indexes=1, resampling=Resampling.bilinear,
            )
            if array.shape[1] * array.shape[2] > MAX_RASTER_PIXELS:
                raise ValueError("Merged DEM exceeds the raster pixel limit.")
            valid = np.isfinite(array) & (array != -9999.0)
            if not bool(np.any(valid)):
                raise ValueError("No valid land elevation data in Copernicus tile windows.")
            profile = sources[0].profile.copy()
            profile.update(
                driver="GTiff", width=array.shape[2], height=array.shape[1],
                count=1, dtype="float32", nodata=-9999.0, transform=transform,
                compress="deflate", tiled=False,
            )
            with rasterio.open(path, "w", **profile) as out:
                out.write(array[0].astype("float32"), 1)


def acquire_copernicus(bounds: tuple[float, float, float, float], output_dir: Path) -> tuple[Path, dict[str, Any]]:
    """Retrieve public 30m COG windows; attempt a clearly labelled 90m fallback.

    Missing source tiles, network failures or invalid raster data are errors,
    never fabricated DEM observations. Testing uses local GeoTIFF fixtures.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "source_clipped.tif"
    west, south, east, north = bounds
    padding = 0.001
    padded = (max(-180, west-padding), max(-90, south-padding), min(180, east+padding), min(90, north+padding))
    failures: list[str] = []
    for item in SOURCE_CATALOG:
        urls = copernicus_tiles(padded, item["resolution_arcsec"])
        try:
            _clip_cogs(urls, padded, path)
        except (rasterio.errors.RasterioError, OSError, ValueError) as exc:
            failures.append(f"{item['name']}: {type(exc).__name__}: {str(exc)[:180]}")
            path.unlink(missing_ok=True)
            continue
        metadata = {
            **item,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_tile_urls": urls,
            "vertical_datum": "Check official Copernicus DEM documentation (not field verified)",
            "verified": "Public COG provenance checked by URL and GDAL raster reading; site-level accuracy NOT field verified",
            "retrieval_mode": "public-cog-window",
            "fallback_used": item["resolution_arcsec"] == 30,
            "fallback_reason": failures[0] if failures else None,
        }
        return path, metadata
    raise HTTPException(
        503,
        "Cannot retrieve verified Copernicus GLO-30 or GLO-90 DSM data for this site. "
        "Check connectivity/public tile coverage or upload an authorized GeoTIFF. "
        "No elevation values were invented. Details: " + " | ".join(failures)[:400],
    )
