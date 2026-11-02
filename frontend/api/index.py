"""PLANEXUS AI FastAPI: pinned GIS engine with explicit native library loading."""
import os

os.environ["PLANEXUS_CLOUD_STORAGE"] = "blob"

# Vercel Python functions do not ship libexpat.so.1 as a system dependency.
# Load the vetted Debian 11 shared library *before* rasterio imports.
from app.native import preload_gis_libraries
preload_gis_libraries()

from app.main import app
