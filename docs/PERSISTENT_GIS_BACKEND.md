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


## B3.1 — Verified backup and OFFLINE restore (source code only)

PLANEXUS currently uses SQLite metadata and GIS files on a **single local or
mounted durable volume**. A new version-2 backup archives the database, original
GeoTIFFs, and saved GIS overlays (including Slope and Elevation). Every archived
file has a SHA-256 checksum. Before a backup is accepted, verification checks
SQLite integrity, GIS report IDs, linked source rasters and stored project,
scenario and layout counts.

### Windows workflow

1. Stop both local PLANEXUS terminal windows so no analysis is writing data.
2. Double-click `BACKUP-PLANEXUS.bat` in the repository root. It refuses to
   run while port 8000 is listening.
3. It creates and verifies a ZIP in the Git-ignored `private-backups/` folder.
4. Copy this ZIP to encrypted, access-controlled OFF-COMPUTER backup storage.
   Backups contain confidential site data and are **not encrypted or signed**.

### Offline CLI

From `backend/` using the backend Python virtual environment:

```bash
python -m app.backup --output-dir ../private-backups
python -m app.backup_restore verify --archive ../private-backups/PLANEXUS-backup-TIMESTAMP.zip
python -m app.backup_restore restore --archive ../private-backups/PLANEXUS-backup-TIMESTAMP.zip --destination ../recovered-planexus-data
```

The restore destination **must not exist** (even if it is empty). The tool
refuses to overwrite live project data. It verifies every checksum, rejects
unsafe ZIP paths, duplicate members and symbolic links, checks linked GIS
raster/report evidence, and publishes a verified new directory by atomic
rename. Stop the API before restoring; then point a local test backend at
the restored directory and check projects, boundary, revision, analysis,
source raster, saved scenarios and layout. Do not rename over a running
Docker volume. Never use `docker compose down -v` unless deliberately deleting
its stored data.

### Acceptance and limitations

CI regression tests use actual synthetic GeoTIFF bytes, FastAPI, SQLite and
scenario/layout records. They test backup and restore into a *different*
directory and reject deliberate corruption. These are NOT measurements from
any real planning site, nor evidence of a cloud recovery procedure.

**Still needed before any public online deployment:** private durable host
and monitored volume, encrypted independently stored backup snapshots, a
practised recovery runbook, HTTPS, user authentication/authorization, rate
limits, audit logs, and tenant separation. This code does not install a
cloud PostgreSQL server or remote object store; a single SQLite writer and
one volume are suitable only for a trusted private pilot. Checksum integrity
detects accidental corruption, not a malicious party who can rewrite the
unsigned manifest. B3.2 will address user access control. Vercel unchanged.

## B3.2 — Invite-only accounts and project authorization (GitHub only)

All private `/api/` endpoints except `/api/health`, `/api/auth/login` and
`/api/auth/register` require a real SQLite session. The browser uses an
opaque HttpOnly session cookie; only the SHA-256 digest is stored in SQLite.
Passwords use salted scrypt, not plaintext. Sessions expire after 12 hours.
POST/PUT/PATCH/DELETE require CSRF token and an allowed origin. The CORS
allowlist is NOT authentication. Cross-user project/analysis requests return
404, including direct URLs, exports, AI Copilot evidence, scenarios, terrain
uploads and Smart Layout. The list endpoints filter by project owner.

**Local Windows first run:** `START-PLANEXUS.bat` prompts for the FIRST
admin email, display name and password (12–128 characters). Password input
is hidden. No fixed account or shared default password is provided.

**Offline CLI, from backend directory:**

```bash
python -m app.auth create-admin --email admin@example.com --name "Admin Planner"
python -m app.auth create-invite --admin-email admin@example.com --hours 48
python -m app.auth claim-legacy --admin-email admin@example.com
python -m app.auth disable-user --admin-email admin@example.com --email staff@example.com
python -m app.auth status
```

The one-time invite must be delivered PRIVATELY to an intended planner.
They select "Daftar dengan jemputan" and register with email and password.
Invites expire; used invites cannot be reused. Admins do NOT automatically
see other users' projects. To revoke access, run `disable-user` offline: it
disables the account and revokes its sessions.

**Existing projects:** on migration, all previous projects remain intact
with NULL owner. They are HIDDEN to every user until an operator explicitly
claims them with `claim-legacy`, after checking the rightful owner and
making a private backup. This offline action assigns ALL unowned legacy
projects to the nominated admin; it does not delete geometry, scenarios,
layout, raster files or historical analyses.

**Local browser:** open frontend at http://localhost:3000 or
http://127.0.0.1:3000. In development, the GIS API automatically follows
the same loopback hostname on port 8000, avoiding cross-site cookie failures.
In production, use trusted same-site HTTPS origins, explicit
`PLANEXUS_CORS_ORIGINS`, and `PLANEXUS_COOKIE_SECURE=1`.

**Security limitations:** no MFA, email verification, password recovery,
audited invitation delivery, organization/team sharing, managed WAF, or
horizontally scaled session store yet. OAuth or an audited identity provider
is recommended before opening access beyond a small trusted pilot. SQL user
accounts alone do NOT make this a safe internet-facing multi-tenant service.
No Vercel deployment was made in this phase.

### Session revocation during offline disaster recovery

Restoring a v2 backup deliberately **deletes all prior sessions and unused
invitation codes** inside the new SQLite copy. No old browser can inherit
authorization after a disaster recovery. Password hashes and user accounts
are retained so each authorized planner can login afresh. The original
backup archive is never modified; the restored database is validated again
before publication. Do not put private archive files in the repository.
