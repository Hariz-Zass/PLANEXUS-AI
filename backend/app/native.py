"""Opt-in native dependency loader for Vercel's minimal Python Lambda runtime.

The bundled Linux x86-64 libexpat was copied from Debian Bullseye by our
GitHub Actions vendor-native-gis workflow, with provenance on that commit.
The library is preloaded before rasterio; desktop environments may rely on
their own system library and need not use this helper.
"""
from __future__ import annotations

import ctypes
from pathlib import Path


def preload_gis_libraries() -> bool:
    expat = Path(__file__).resolve().parent / "vendor" / "libexpat.so.1"
    if not expat.is_file():
        return False
    ctypes.CDLL(str(expat), mode=ctypes.RTLD_GLOBAL)
    return True
