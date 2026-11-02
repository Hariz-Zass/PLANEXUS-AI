"""Vercel Python Function for the real PLANEXUS FastAPI engine."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["PLANEXUS_CLOUD_STORAGE"] = "blob"
from app.main import app
