"""PLANEXUS AI FastAPI: installed, version-pinned geospatial engine."""
import os
os.environ["PLANEXUS_CLOUD_STORAGE"] = "blob"
from app.main import app
