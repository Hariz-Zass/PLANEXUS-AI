FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLANEXUS_DATA_DIR=/data \
    PLANEXUS_REQUIRE_PERSISTENT_VOLUME=1

WORKDIR /srv/planexus
# Rasterio/GDAL wheels require these native runtime libraries on slim Debian.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libexpat1 libgomp1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && groupadd --system --gid 10001 planexus \
    && useradd --system --uid 10001 --gid 10001 --home-dir /nonexistent planexus \
    && mkdir -p /data /backups && chown 10001:10001 /data /backups
COPY app ./app
# Surface missing native GIS dependencies at image-build time, not after deploy.
RUN python -c "from app.main import app; print(app.title)"
USER 10001:10001
EXPOSE 8000
# Single SQLite writer / persistent volume. No public-user authentication.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
