# PLANEXUS — PostGIS-first Malaysia OSM operations (opt-in, no Vercel)

## What is implemented

**Planner request:** Site Context -> indexed local PostGIS OSM snapshot -> if unavailable,
public Overpass -> if configured, GeoPackage local fallback -> if none succeed,
HTTP 503 or an explicitly labelled previously saved site snapshot. The service
NEVER fills missing facilities with synthetic features.

**Operator import:** licensed Geofabrik Malaysia/Singapore/Brunei free GIS
GeoPackage -> Fiona/pyproj -> PostGIS table with WGS84 geometry and GiST
spatial indexes. Snapshots are updated inside one transaction, so broken
imports cannot replace a complete dataset.

**Evidence:** CI job `postgis-osm-integration` uses a real Docker PostGIS
server with a **synthetic, clearly labelled test GeoPackage** to verify
SQL, bounds, counts, metadata and repeatable replacement. Live Malaysia
production extract has not been provisioned by these code changes.

## First-time server setup

Requires Docker Compose and a backend Docker image built from this repo.
No need for planners to install PostGIS or upload OSM files per project.

1. Download the **latest free GIS GeoPackage archive** for Malaysia, Singapore
   and Brunei from the source:
   https://download.geofabrik.de/asia/malaysia-singapore-brunei.html .
   Preserve Geofabrik/OSM attribution and respect ODbL terms.
2. Extract the original GeoPackage(s) to a folder on the server, for example
   `./data/osm`. The importer accepts either one `.gpkg` or the folder.
   Confirm layers include `gis_osm_pois_free_1`, `gis_osm_roads_free_1`,
   `gis_osm_waterways_free_1` where provided; this is a filtered community
   extract, **not all OSM attributes**, land titles or official zoning.
3. Set **server-only environment variables** (PowerShell example):

   ```powershell
   $env:PLANEXUS_POSTGIS_PASSWORD = "USE_A_LONG_RANDOM_URL_SAFE_PASSWORD"
   $env:PLANEXUS_OSM_EXTRACT_DIR = "./data/osm"
   $env:PLANEXUS_OSM_SNAPSHOT_DATE = "YYYY-MM-DD"
   ```

   The snapshot date must match the downloaded source's actual publication
   date, NOT the day a user performs their site scan. Never put secrets in
   Git, frontend NEXT_PUBLIC env or screenshots.
4. Start the local backend and private PostGIS service together:

   ```powershell
   docker compose -f compose.gis.yml -f compose.osm.yml up -d --build gis osm-db
   ```

5. Import once as a **manual, operator-only task** (regional import may be
   large; the API will continue using online sources until a complete
   snapshot is committed):

   ```powershell
   docker compose -f compose.gis.yml -f compose.osm.yml --profile osm-import run --rm osm-import
   ```

6. Visit the authenticated API endpoint `/api/osm/status` to confirm
   `postgis.ready=true` and see the imported row count. Only then treat the
   server-local extract as provisioned.
7. Run a Site Context scan on a Malaysian project. It should return
   `source_id=geofabrik-osm-postgis-snapshot` and a real
   `dataset_timestamp_utc`. Data Registry advertises the configured
   provider; `app.postgis_context.readiness()` verifies a completed,
   nonempty imported snapshot. Do not claim ready until step 5 succeeds.

## Keeping the dataset fresh

The backend **never downloads the large regional archive during a planner
request**. After the initial optional server setup, the operator can activate
a weekly refresh worker. It downloads Geofabrik's HTTPS archive (bounded
download and ZIP extraction), checks its publication time, skips unchanged
sources and atomically imports a changed snapshot:

```powershell
docker compose -f compose.gis.yml -f compose.osm.yml --profile osm-refresh up -d osm-updater
```

The worker runs at start and repeats every seven days. It logs a warning on
failure and retains the last fully imported snapshot. Source availability,
disk space and network bandwidth still require monitoring.

**Date caveat:** the automatic updater currently uses the ZIP archive's
HTTP `Last-Modified` date as its snapshot publication timestamp. The exact
cutoff of individual OSM edits can differ. Do not interpret this as a legally
verified feature update time.

The importer is transactional and repeatable; the previous valid snapshot
remains when a refresh fails. The running Docker volume persists across
container replacement; protect it with off-host backups. The service uses a
persistent temporary volume `planexus-osm-work`; ensure sufficient disk
capacity for the archive and its decompressed GeoPackages. Do not publish
the database port.

## Technical caveats

- Spatial search uses `ST_DWithin` on WGS84 geography, with GiST index and
  nearest-on-geometry distance. This is NOT network/walking travel time or a
  legal road access test.
- The snapshot includes *selected* Geofabrik free GIS classes. A site with
  zero recorded schools may still have untagged or missing schools.
- A coarse dataset bounds check rejects sites beyond the imported extent.
  Missing data **inside** that extent can still occur; this is not a
  comprehensive official infrastructure inventory.
- The date of the OSM snapshot is displayed separately from the time PLANEXUS
  retrieved the result.
- Per-site cache remains private to each authenticated project and its exact
  site geometry.
- No official PLANMalaysia RT/zoning or JPS flood hazards are provided by
  community OSM. Those require authoritative datasets and permissions.
- This compose overlay is **opt-in**. The default Windows localhost
  launcher and basic Compose service continue operating without PostGIS,
  using existing live-OSM/GeoPackage fallback.

## Source

- Geofabrik: https://download.geofabrik.de/asia/malaysia-singapore-brunei.html
- OSM copyright and ODbL: https://www.openstreetmap.org/copyright
- PostGIS ST_DWithin: https://postgis.net/docs/ST_DWithin.html
