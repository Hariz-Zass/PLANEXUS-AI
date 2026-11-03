# PLANEXUS AI — B3.4 Automated Backup, Recovery & GIS Export

**Status:** Source code only, GitHub main. No Vercel/backend production deploy.

## 1. Preservation architecture

The GIS API uses SQLite in PLANEXUS_DATA_DIR, with project-scoped original
GeoTIFFs and derived terrain files under jobs/<analysis-UUID>. A shared
cross-process file lock (file .planexus-data.lock inside the mounted volume)
coordinates ALL mutating FastAPI requests with the private backup CLI.
A backup holds the exclusive lock across its entire SQLite backup snapshot,
raster copy, SHA verification and atomic publication.

- A scheduled backup never appears as *.zip until its manifest and every file
  have passed integrity validation. A failed run never prunes valid backups.
- Retention keeps the newest N archives (default 14; minimum 2) inside a
  dedicated automatic backup folder. The user's manual backup ZIPs are not
  rotated by the default schedule.
- Every archive contains SQLite, account/project metadata, linked terrain
  reports and raster evidence. It is UNENCRYPTED and PRIVATE. Treat it like a
  database dump containing personal information and sensitive project sites.
- Separate mirror storage is an OPTION, not created or configured
  automatically. A mirror is SHA-256 checked and independently reverified.
- Backup archive recovery is offline and always into a NEW location. Restore
  refuses overwriting existing projects and revokes old sessions/invites.
- Direct database/raster writes outside FastAPI's locking protocol are not
  coordinated. Stop such workers before starting a backup. A local filesystem
  lock cannot guarantee consistency across a network filesystem without
  reliable cross-host locks. Single-host/single-writer pilot only.

## 2. Windows daily scheduled backup — explicit opt-in

1. Obtain the latest GitHub code and launch START-PLANEXUS.bat at least once.
   Create the admin, check a saved project and confirm the Python environment.
2. Double-click INSTALL-PLANEXUS-AUTO-BACKUP.bat.
3. Windows Task Scheduler installs PLANEXUS-GIS-Verified-Backup for **02:00
   local time every day** when the SAME Windows user is signed in.
4. Test manually by running this command from backend/ using its .venv Python:

       python -m app.backup_scheduler once --output-dir ../private-backups/automatic --keep 14 --restore-drill

5. Inspect the result:

       python -m app.backup_scheduler status --output-dir ../private-backups/automatic
       python -m app.backup_scheduler drill --output-dir ../private-backups/automatic

6. To cancel scheduled jobs, double-click REMOVE-PLANEXUS-AUTO-BACKUP.bat.
   This removes the schedule only; it does not delete archived projects.

Windows Task Scheduler does NOT run this task while the computer is off,
asleep, or its chosen user is signed out. Missed runs are not silently counted
as successful. Check the status and independently monitor backup age.
The INSTALL file only installs a Windows task when a user explicitly runs it;
GitHub pushes do not create local tasks.

The existing BACKUP-PLANEXUS.bat remains the MANUAL archive workflow and
is not subject to automatic retention. That older launcher deliberately
requires you to STOP the backend before use. The new scheduled backup worker
can run while the API is online because it coordinates with PLANEXUS' shared
write lock. Direct file/database writers outside that lock must still stop.
For large analyses, an automatic backup may wait or fail with a clear message;
retry later.

## 3. Docker private pilot (opt-in profile)

Compose has an additional service 'backup' behind the optional profile.
Launch it ONLY after the GIS service itself is ready:

       docker compose -f compose.gis.yml --profile backup up --build -d

The worker runs independently of Vercel, creates a verified snapshot, then
repeats every 24 hours while its container is running. It mounts BOTH:
- planexus-gis-data:/data — same durable data volume as the GIS backend.
- planexus-gis-backups:/backups — separate named archive volume.

**Both named volumes are still on the same Docker host**; loss of that host
can destroy BOTH. This is NOT disaster recovery unless protected copies are
sent to an independently managed off-host location.

Never use 'docker compose down -v' to stop a running pilot;
the -v option destroys named volumes. Never expose /backups over a public URL.

## 4. Independent protected backup destination

To copy each successful archive to a separate, operator-mounted location:

       python -m app.backup_scheduler once --data-dir PATH_TO_GIS_DATA --output-dir PATH_TO_AUTOMATIC_ARCHIVES --mirror-dir PATH_TO_PROTECTED_INDEPENDENT_STORAGE --keep 14

The mirror destination cannot be nested inside GIS data or primary backup
directories. The copy is reverified before the local retention policy runs.
The operator is responsible for filesystem encryption, access controls,
off-host sync and disaster recovery of the mirrored location. SHA-256 detects
accidental changes, NOT attacker substitution of an unsigned archive.

## 5. Rehearse recovery (B3.4B)

1. Stop all backend/container writers and KEEP existing data unmodified.
2. Choose a verified ZIP. Run:

       python -m app.backup_restore verify --archive PLANEXUS-backup-TIMESTAMP.zip
       python -m app.backup_restore restore --archive PLANEXUS-backup-TIMESTAMP.zip --destination NEW_NONEXISTENT_DIRECTORY

3. The destination must NOT exist. Reopen a PRIVATE backend pointing at the
   restored volume and check exact project IDs, boundaries, revisions,
   active analysis IDs, reports, original/UTM rasters, saved proposals
   and Smart Layout.
4. Reauthenticate: restored databases invalidate all old sessions and unused
   invitation codes. The operator's account/password hash remains.
5. Repeat using an alternate host/location. The built-in automatic restore
   drill extracts to a temporary clean directory and checks database/report
   integrity, but it does not substitute for a real remote-host rehearsal.

No public browser action can restore or download whole SQLite backups.

## 6. GIS export contract (B3.4C)

After opening an OWNED project with a saved site boundary, use:
- Project Workspace > Download GIS Package (.zip)
- Terrain Intelligence > GIS DATA QUALITY > Complete GIS Package (.zip)
- GIS Layers (.gpkg), Site Boundary (.geojson) and protected UTM .tif links

The exported ZIP includes:
- vector/planexus_layers.gpkg: a real Fiona/GDAL-created OGC GeoPackage.
- vector/site_boundary.geojson: project boundary, EPSG:4326 WGS84.
- vector/slope_classes.geojson, elevation_bands.geojson, contours.geojson,
  suitability.geojson, IF present in the saved active analysis.
- raster/elevation_utm.tif and raster/slope_degrees_utm.tif, if saved.
- raster/uploaded_source.tif or source_clipped.tif, if available.
- export-manifest.json: project UUID/revision, analysis ID, input source
  provenance, horizontal CRS, quality warnings, per-layer feature counts,
  preview/completeness flags, and SHA-256 for each exported file.

GeoJSON and GeoPackage vectors use EPSG:4326, not UTM. The GeoTIFFs retain
their own metric UTM CRS + NoData tags and full computed pixel grids.
GeoPackage is VECTOR-ONLY; raster data is separate TIFF, not fake GPKG
raster embedding.

**Important truthfulness:** Polygons and contour features saved for display
can be capped for MapLibre performance. Their exports are explicitly
marked PREVIEW-ONLY. If overlay_status flags indicate truncation, do not
treat the vector features as a complete cadastral/terrain classification.
Use the full-resolution source/UTM GeoTIFF instead and create detailed
vectors in QGIS. Older reports without flags are marked completeness unknown.

The export must not infer statutory setback/density/zoning approval; its
geospatial output is a planning-screening record only. Copernicus GLO-30
is a DSM (vegetation and buildings included), not a site survey DTM.
Independent QGIS algorithm parity is separate from field vertical accuracy.

### Private API endpoints (session required)

    GET /api/projects/{project-uuid}/exports/site_boundary.geojson
    GET /api/projects/{project-uuid}/exports/slope_classes.geojson
    GET /api/projects/{project-uuid}/exports/elevation_bands.geojson
    GET /api/projects/{project-uuid}/exports/contours.geojson
    GET /api/projects/{project-uuid}/exports/suitability.geojson
    GET /api/projects/{project-uuid}/exports/layers.gpkg
    GET /api/projects/{project-uuid}/exports/gis-package.zip

A different logged-in user receives 404 for that project. The FastAPI route
also validates ownership of the active analysis before reading its files.
Downloads are generated in private temporary directories and cleaned up
after the response, not uploaded to public storage.

## 7. Tests and acceptance (B3.4D)

GitHub CI exercises:
- Real SQLite + GeoTIFF snapshot; SHA verification and manifest checks.
- Offline restore into a DIFFERENT directory; sessions revoked.
- Automatic generations and bounded retention; failures never prune archives.
- Shared writer lock, fail-closed on corrupted ZIP and mirror failures.
- External-path mirror SHA and ZIP verification.
- Fiona opens each GPKG layer and confirms WGS84, valid feature counts.
- Rasterio reads each UTM TIFF and verifies CRS, dimensions and pixels.
- Binary ZIP content manifest, source SHA, origin restrictions, cross-user
  project ownership and corrupted-source rejection.
- Actual Next.js/Playwright browser downloads a non-empty private ZIP with
  the real backend and verifies button visibility.

**Not yet proven:** Scheduled Windows task executes on the user's computer at
02:00, external encrypted off-host backup, multi-host scaling, field survey
accuracy, production disaster recovery RTO/RPO, or deployment to Vercel.
Those require user-controlled infrastructure and actual operational checks.

## Next stages

B3.5: final multi-device workflow checks, failed network/DEM scenarios, and
an operator-accepted readiness checklist. B4: hydrology, zoning and more
advanced evidence-grounded planning intelligence. Neither is claimed
complete by this B3.4 source-code development.
