FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLANEXUS_DATA_DIR=/data \
    PLANEXUS_REQUIRE_PERSISTENT_VOLUME=1

WORKDIR /srv/planexus
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && groupadd --system --gid 10001 planexus \
    && useradd --system --uid 10001 --gid 10001 --home-dir /nonexistent planexus \
    && mkdir /data && chown 10001:10001 /data
COPY app ./app
USER 10001:10001
EXPOSE 8000
# Single SQLite writer / persistent volume. No public-user authentication.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
