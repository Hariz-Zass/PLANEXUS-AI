from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Make backend/.env work with uvicorn, CLI and the Windows launcher.
# Existing shell variables always take precedence.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


DATA_DIR = Path(os.getenv("PLANEXUS_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
CORS_ORIGINS = [value.strip() for value in os.getenv("PLANEXUS_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if value.strip()]
MAX_UPLOAD_BYTES = 60 * 1024 * 1024
MAX_SITE_AREA_KM2 = 50.0
MAX_RASTER_PIXELS = 2_000_000
AI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
