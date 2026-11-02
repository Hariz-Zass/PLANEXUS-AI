"""Import-time native GIS library preloading must not silently fake terrain data."""
from pathlib import Path

from app.native import preload_gis_libraries


def test_native_vendor_library_available_and_loadable():
    library = Path(__file__).resolve().parents[1] / "app/vendor/libexpat.so.1"
    assert library.is_file(), "The pinned native libexpat should be tracked with the backend"
    assert library.stat().st_size > 25000
    assert preload_gis_libraries() is True
