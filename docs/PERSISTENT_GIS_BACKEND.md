# PLANEXUS AI: persistent GIS backend and acceptance gates

**Scope:** Source code and automated regression tests only. NO deployment.
This document does NOT establish online GIS availability.

## Why the current website shows no slope or elevation

The Next.js frontend renders polygon sketches on a MapLibre base map.
Slope and elevation overlays exist only after the Python GIS API analyzes a
verified DEM or a declared GeoTIFF and returns a saved TerrainReport with
non-empty slope_geojson and elevation_geojson features. The dark base map
is not a terrain dataset. The frontend production site currently lacks a
reachable backend; it cannot invent GIS results and must show offline status.

The data flow is:

1. Create a project in Project Workspace.
2. Import/draw its WGS84 boundary and save it with a backend revision.
3. Acquire Copernicus GLO-30 Public DSM (or upload documented GeoTIFF).
4. Validate CRS, NoData, resolution and source provenance; calculate slope
   and elevation in local UTM metres.
5. Atomically store result.json and the raster under the analysis UUID in the
   same persistent volume as the SQLite project registry.
6. Associate that report with the project; restore it after browser refresh.
7. Switch Slope / Elevation / Suitability layers and read the class legend.
8. Reopen the project in a separate browser session and verify exact report
   and boundary; only then claim save/recovery works.

## Private Docker pilot for storage verification

Run locally on a machine with Docker Engine and Compose:

    docker compose -f compose.gis.yml up --build -d

Health:

    curl http://127.0.0.1:8000/api/health

A healthy mounted volume reports status=ok and persistent=true.
The Compose file binds port 8000 to LOOPBACK only. It is not a public
deployment. The service uses a named volume for /data, running as a
non-root UID 10001, with ONE worker and SQLite.

Keep the volume on restart:

    docker compose -f compose.gis.yml down

NEVER use docker compose down -v unless intentionally deleting GIS data.
Keep private backups of BOTH SQLite and jobs. The backup script archives
database snapshots and raster/report files; verify a full restore on a fresh
volume before relying on it. No automatic backup scheduler has been added.

A container requires these settings:

- PLANEXUS_DATA_DIR=/data
- PLANEXUS_REQUIRE_PERSISTENT_VOLUME=1
- PLANEXUS_CORS_ORIGINS with explicit allowed frontend origin(s)

Without the volume, GET /api/health responds 503; all mutating API calls
(POST, PUT, PATCH, DELETE) respond 503 BEFORE writing any project or raster.
A writable container layer does NOT count as a durable volume. The health
check includes a file write/read probe plus SQLite quick_check for an
existing database. A healthy local path without strict mount mode never
claims verified cloud persistence. The strict mount check alone does NOT
verify a host provider's backup or replication policy.

## Conditions before a remote live deployment

- Secure private HTTPS ingress: authentication and authorization MUST
  precede any public-facing API. No accounts, project ownership checks or
  tenant separation exist here. CORS alone never grants security.
- A durable volume on a persistent container host. Do not run this
  SQLite+GeoTIFF backend on ephemeral Vercel Functions or split jobs from
  the database.
- A single trusted operator and one backend process. For multi-user or
  horizontally scaled service, implement a multi-tenant Postgres model and
  protected object storage with per-user authorization and migration tests.
- Set the frontend build-time NEXT_PUBLIC_API_BASE_URL to the HTTPS API
  origin, then rebuild the frontend. This is configuration, not something
  an unchanged deployed frontend can discover by itself.
- Ensure outbound HTTPS access to the official Copernicus public COG
  endpoints (data availability is never guaranteed). Do not silently
  fabricate DEM values when public tiles fail.
- Verify a loaded source actually produces non-empty slope_geojson AND
  elevation_geojson; missing raster evidence is an error/empty state.
- Prove persistence with a real restart: same project ID, boundary, revision,
  original raster, report and map overlays. Test data isolation and 409
  conflict protection.
- Validate GPP registry endpoints against the curated source index, and
  confirm that insufficient coverage is shown as UNKNOWN / not indexed.
- Validate mobile and desktop rendering. A successful compilation is
  necessary but is not sufficient to claim online features are working.

## Automated checks in GitHub Actions

- Python: API persistence tests, real synthetic GeoTIFF terrain processing,
  four slope classes, GIS provenance, scenario/GPP geometry and report
  restore. New checks cover volume enforcement and atomic result saving.
- Browser: mock API fixtures test Create/Open Project and refresh, Slope/
  Elevation/Suitability layer switching, layout and development scenarios.
  UI fixtures are synthetic; they are NOT a substitute for live DEM checks.
- A live public COG smoke check is non-blocking because external data
  availability is outside the repository. Inspect its logs before making
  claims about external Copernicus availability.

## What remains NOT solved by these GitHub changes

Current public frontend still has NO connected GIS backend, NO persistent
online projects, NO working live DEM retrieval and NO actual online report
save. These cannot be fixed by adding attractive cards or claiming the
existing frontend is READY. A remote secure backend+volume deployment is a
separate task and is NOT performed here.

PLANEXUS is a preliminary geospatial planning tool. Copernicus GLO-30
is DSM (buildings and vegetation included), not detailed bare-earth
survey DTM. Outputs do not establish PBT development approval.
