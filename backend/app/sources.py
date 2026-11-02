"""Trusted-source adapter. Never performs unverified search/scraping."""
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
        "id": "copernicus-glo30-public",
        "name": "Copernicus DEM GLO-30 Public",
        "publisher": "Copernicus Programme / ESA; public AWS distribution",
        "data_type": "DSM (includes vegetation and built structures)",
        "nominal_resolution_m": 30,
        "access": "Public Cloud Optimized GeoTIFF tiles (without API key)",
        "reference": "https://registry.opendata.aws/copernicus-dem/",
        "metadata": "https://copernicus-dem-30m.s3.amazonaws.com/readme.html",
        "intended_use": "Preliminary terrain screening only",
        "warning": "Not a ground-survey DTM or proof of engineering design suitability.",
    }
]


def tile_name(latitude: int, longitude: int) -> str:
    latitude_part = f"{'N' if latitude >= 0 else 'S'}{abs(latitude):02d}_00"
    longitude_part = f"{'E' if longitude >= 0 else 'W'}{abs(longitude):03d}_00"
    return f"Copernicus_DSM_COG_10_{latitude_part}_{longitude_part}_DEM"


def copernicus_tiles(bounds: tuple[float, float, float, float]) -> list[str]:
    west, south, east, north = bounds
    tiles = []
    for lat in range(math.floor(south), math.ceil(north)):
        for lon in range(math.floor(west), math.ceil(east)):
            name = tile_name(lat, lon)
            tiles.append(f"https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif")
    if not tiles or len(tiles) > 9:
        raise HTTPException(422, "Tapak merentasi terlalu banyak tile DEM untuk V1.")
    return tiles


def acquire_copernicus(bounds: tuple[float, float, float, float], output_dir: Path) -> tuple[Path, dict[str, Any]]:
    """Read only required COG windows, persist the clipped mosaic on local disk."""
    urls = copernicus_tiles(bounds)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "source_clipped.tif"
    west, south, east, north = bounds
    pad = 0.001  # 1-4 source cells around the site for gradient estimation
    try:
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_TIMEOUT="30", GDAL_HTTP_MAX_RETRY="1"):
            with ExitStack() as stack:
                sources = [stack.enter_context(rasterio.open(url)) for url in urls]
                if any(src.crs is None or src.count < 1 for src in sources):
                    raise ValueError("Raster sumber tiada CRS atau band yang boleh digunakan.")
                if any(src.crs != sources[0].crs for src in sources):
                    raise ValueError("CRS sumber tidak konsisten.")
                array, transform = merge(sources, bounds=(west - pad, south - pad, east + pad, north + pad), nodata=-9999.0, resampling=Resampling.bilinear)
                if array.shape[1] * array.shape[2] > MAX_RASTER_PIXELS:
                    raise ValueError("Saiz raster melebihi had pemprosesan V1.")
                if not np.any(np.isfinite(array) & (array != -9999.0)):
                    raise ValueError("Dataset tidak meliputi tapak yang dipilih.")
                profile = sources[0].profile.copy()
                profile.update(driver="GTiff", width=array.shape[2], height=array.shape[1], count=1, dtype="float32", nodata=-9999.0, transform=transform, compress="deflate", tiled=False)
                with rasterio.open(path, "w", **profile) as out:
                    out.write(array[0].astype("float32"), 1)
    except (rasterio.errors.RasterioError, OSError, ValueError) as ex:
        raise HTTPException(503, "Tidak dapat mendapatkan DEM Copernicus yang boleh disahkan untuk tapak ini. Tiada data rekaan digunakan. Cuba upload GeoTIFF sendiri. Butiran: " + str(ex)[:250]) from ex
    metadata = {
        **SOURCE_CATALOG[0],
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_tile_urls": urls,
        "vertical_datum": "Refer to official source metadata; not independently field-validated",
        "verified": "Source provenance identified; site-level accuracy NOT field verified",
    }
    return path, metadata
