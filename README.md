# PLANEXUS AI — Terrain Intelligence V1

**Your Geospatial Planning Copilot for Urban & Regional Planning.**

> **Status:** GitHub development repository. Local GIS tests and a private single-workspace Docker backend template are available. Cloud backend, authentication, and production data persistence are NOT deployed. A frontend-only Vercel build is not a functioning online terrain analysis service.
>
> **Brand caution:** PLANEXUS is a working project name; check Malaysia trademark and existing planning-sector usage before external branding or commercial release.

PLANEXUS is an **evidence-first** geospatial decision-support project. V1 focuses **only on terrain screening** and supports future modules for site context, statutory planning, transport, hydrology and integrated development scenarios. **No verified data → no unsupported conclusion.**

## What is implemented

- Mobile-responsive professional workspace with MapLibre GL JS map and polygon drawing / GeoJSON import.
- Automatic Copernicus DEM GLO-30 Public **DSM** raster retrieval from public COG tiles (does not require an API key). Fetch is bounded by site geometry; availability is dependent on Copernicus public coverage and an internet connection.
- Manual elevation GeoTIFF upload with explicit source/type and metre-unit declaration; source authenticity is not automatically verified.
- API validates WGS84 polygon, geodesic area, site limits, raster CRS, NoData and coverage.
- GIS engine projects into site-local UTM, computes slope in **degrees** using pixel gradients, minimum/mean/maximum elevation, mean/maximum slope, and four indicative slope classes (0–15, 15–25, 25–35, ≥35 degrees).
- Site-specific slope polygons, class area estimates, metadata, caveats, and reproducible Markdown report.
- Local persistent storage: source raster and result JSON per UUID; local saved analyses can be reopened.
- Planning Copilot: OpenAI Responses API when an API key is configured; when not configured, a **clearly identified non-LLM deterministic summary**, which uses real calculated stats only.
- Minimal Python tests for geometry validation, tile selection, raster gradient, upload, saved report and assistant fallback.

## NOT implemented in V1

- A production site, login / user data permissions, hosted object storage, rate limiting and robust ingestion queues.
- Contour/hillshade/section views, shapefile/GPKG ingestion, regulatory zoning or RT/RSN/RFN/GPP checking.
- Hydrological or geotechnical validation; surrounding amenities, parcel-title or approved development suitability.
- Verified high-resolution cadastral/survey data automatically; Copernicus GLO-30 is **DSM** and **screening-only**.
- PDF report export (the current export is Markdown). No live deployment to Vercel.

**Do not use this prototype as a substitute for registered surveying, engineering/geotechnical assessment or statutory planning checks.**

## One-click start on Windows (recommended)

**You do not need to type terminal commands.** Install **Node.js 22+** and **Python 3.11 / 3.12** once. Download this repository from GitHub (**Code → Download ZIP**), extract it to a normal folder, and **double-click `START-PLANEXUS.bat`**. The batch launcher runs `scripts/start-planexus.ps1`, which:

1. Checks Node.js and Python versions; checks ports 3000/8000.
2. Creates `backend/.venv` and installs GIS Python packages if missing.
3. Creates `frontend/.env.local` from the example and installs npm packages if missing.
4. Starts two separate PowerShell terminals for the backend and frontend, waits for both endpoints to respond, then opens `http://localhost:3000` in your browser.

**Important:** On first launch the downloads require internet access. Keep both server terminals open while using PLANEXUS; close both to stop. The scripts bind only to **127.0.0.1** and do not publish your data online. The startup process does **not** ask for an API key; without one, Copilot returns a clearly labelled rule-based summary. For installation errors take a screenshot of the red error in the launcher or server terminal. The one-click script has been written for Windows PowerShell but cannot be executed from the Linux development environment used to prepare this repository, so first-run Windows behavior must still be verified.

## Getting started (Windows PowerShell)

Use Python 3.11 or 3.12 and Node.js 22 or later. In one terminal:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

In a **second** terminal:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open <http://localhost:3000>. API docs: <http://localhost:8000/docs>. For full AI answers, set `OPENAI_API_KEY` in the **backend process environment** before launching it; never put it in frontend `.env.local` or Git. `OPENAI_MODEL` can override the default model. Without a key the system still generates a labelled, rule-based GIS summary, **not** generative AI.

### Typical local workflow

1. Draw site polygon (double-click to finish) or upload a single WGS84 polygon `.geojson`.
2. Click **Get DEM & Run Analysis**. This reads public Copernicus raster COG tiles; if access/coverage fails, the app reports an error and never fabricates data.
3. Alternatively select **Configure Upload** for your own elevation GeoTIFF and declare its source, surface type, vertical datum (if known) and metre units.
4. Inspect the class histogram, source/coverage warnings and map overlay. The four slope classes are descriptive; they do **not** imply automatic development permission.
5. Ask planning questions in Copilot, view the evidence mode and download the Markdown evidence report.
6. Reopen previous analyses via **Saved Analyses**. Results persist while the backend's `PLANEXUS_DATA_DIR` directory persists.

## Architecture

```text
frontend/                    Next.js + TypeScript + MapLibre
  app/                       Workspace, Data Sources and Saved Analyses pages
  components/TerrainMap.tsx  Map drawing, site and class polygon visualisation
  lib/api.ts                 Typed API client
backend/
  app/main.py                FastAPI routes, local job storage, reports
  app/sources.py             Explicit trusted-source Copernicus COG adapter
  app/geometry.py            WGS84 polygon/area validation, local UTM
  app/terrain.py             Raster reprojection and geospatial metrics
  app/copilot.py             LLM evidence guard + honest no-key fallback
  tests/test_core.py         Offline deterministic tests with synthetic test raster
```

### Data provenance / quality policy

Every analysis records the original source designation, time of retrieval, CRS, source type, approximate resolution, method, valid-pixel coverage and warnings. For **user-provided datasets**, source and vertical datum are only self-declared, **not independently authenticated**. For **Copernicus GLO-30 Public**, these are 2021-release public DSM COGs distributed on AWS; site-specific survey accuracy is not assured.

The engine rejects invalid polygons, raster regions with insufficient valid cells, impossible unit declarations and missing source files. It never substitutes empty raster data with synthetic terrain. Synthetic data are used **only inside automated tests**, never presented as real site analysis.

Slope formula: `atan(sqrt((dz/dx)^2 + (dz/dy)^2)) * 180/pi`, after bilinear reprojection to local UTM with pixel dimensions in metres. Raster cell-area proportions are approximate and edge/NoData cells are excluded.

### Reliable sources (documentation)

- Copernicus DEM public AWS registry: https://registry.opendata.aws/copernicus-dem/
- Copernicus DEM public dataset readme: https://copernicus-dem-30m.s3.amazonaws.com/readme.html
- GDAL/Rasterio processing documentation: https://rasterio.readthedocs.io/
- OpenTopography developer API (potential later source; API key/terms apply): https://opentopography.org/developers

## Test

```bash
cd backend
python -m pytest -q
```

CI workflows also attempt frontend type-check and build, once the repository is uploaded to GitHub with network access.

## Production hardening roadmap

1. Add validated data model and better site-resolution gating (including terrain pixel density and vertical-datum checks).
2. Harden COG downloads with source tile allow-lists/cache, retry/quotas, checksum/provenance and job status.
3. Move source rasters and result artifacts to persistent object storage; add database metadata and authentication / row-level access.
4. Add slope reference methodology, detailed QA against QGIS and registered ground-survey benchmarks.
5. Introduce contours/hillshade, PDF reports, policy module with versioned citations, and surrounding-site analysis **only after V1 acceptance tests pass**.

## License

Source code license not yet selected. Third-party datasets retain **their own provider licenses**. Review terms and any commercial API conditions before public operation.


## PLANEXUS V2.2 — site recovery, GIS and Copilot testing (NOT DEPLOYED)

**Site boundary bug:** The MapLibre map must finish its asynchronous `load` event and add its `site`/ `slope` GeoJSON sources before applying saved geometry. V2.2 synchronizes the latest boundary after the sources exist; it restores the polygon and fits its bounding box. The existing versioned browser localStorage key is `planexus:site-boundary:v1`. A saved polygon is **local to the same browser + exact origin** (localhost vs vercel.app are different). It is not a cross-device cloud save. Use **Export GeoJSON** for backup; do not clear browser site data without backup. For full cloud history, authentication and a spatial database will be needed later.

**Terrain GIS:** The included FastAPI backend handles actual `/api/terrain/auto` (Copernicus GLO-30 DSM tile retrieval), `/api/terrain/upload` (GeoTIFF), slope/elevation statistics, and `/api/analyses`. Valid DEM coverage and internet access are prerequisites. No invented results: failed tile access is an explicit error. Verify real-site raster results independently in QGIS before using them in a planning report.

**Copilot:** After a successful analysis, `/api/copilot/assess` provides an evidence-based deterministic GIS summary without credentials. To enable generative AI, copy `backend/.env.example` to `backend/.env` and set `OPENAI_API_KEY` and an available `OPENAI_MODEL`; `python-dotenv` loads them when the Python API starts. API credentials must never be committed. This system is not a substitute for RSN, RT, RKK, GPP or engineering confirmation.

**Vercel remains unchanged.** The existing live site deploys only the frontend, so GIS/AI endpoints will not work there until a real hosted backend with persistent object storage is configured and connected. The repository fixes can be tested locally with the two-server launcher; no Vercel deployment has been triggered for V2.2. Next.js should be configured with `NEXT_PUBLIC_API_BASE_URL` pointing to the authorized backend only when its public origin is ready and protected. Do not expose an unauthenticated GIS backend publicly.

### Manual acceptance checks

1. On localhost, draw a 4-corner polygon, finish, and confirm the `SITE AUTOSAVED` chip. Refresh and assert the outline returns at the original coordinates and the map zooms there. Navigate Data Registry / Saved Analyses / Terrain and repeat. Export GeoJSON and reimport it.
2. Import a valid WGS84 polygon and refresh; confirm it returns. Start a redraw, then cancel; the previous polygon must remain. Clear only after export and confirmation.
3. Test `POST /api/site/inspect` with a WGS84 polygon. Run DEM auto on a small real site with public source coverage. Compare slope class areas to QGIS, inspect data provenance and warnings; test deliberate missing coverage/error.
4. Upload a trusted local DEM/DTM with declared metadata. Check elevation range, slope mean, saved analysis, evidence report and Copilot question. Without API key, response must say `deterministic_evidence_summary`; with a valid configured key, check `llm_grounded`. No unsupported approval claims should appear.



## Terrain upgrade V2.3 (GitHub only, not deployed)

- Automatic source selection: attempts real public Copernicus GLO-30 DSM COG raster windows; if unavailable, transparently tries GLO-90 Public DSM with a warning about coarser (~90 m) source resolution. No fake data and no concealed fallback. A missing tile, insufficient DEM pixels, connectivity failure or invalid CRS must produce an explicit error.
- Derived from actual raster pixels in projected metric coordinates: elevation min/mean/max, slope mean/max, four slope classes, coverage percentage; coloured elevation class overlay and bounded contour-line preview. The map now offers **Slope / Elevation / Contours** controls once the backend returns results. The contour interval is resolution-aware; this is not a surveyed contour plan.
- Evidence provenance always identifies source data type (DSM vs DTM), nominal resolution, fallback use, valid coverage and warnings. View the report source metadata and quality caveats before any planning interpretation.
- Tests include offline miniature public-COG stand-in GeoTIFFs and synthetic slope/elevation fixtures. A green test certifies local algorithm/integration behavior under fixtures, **not** live public AWS availability or survey-level validation.
- On a laptop, start both servers using START-PLANEXUS.bat (Python 3.11/3.12, Node 22+) and define a WGS84 polygon. Click Get DEM & Run Analysis; wait for publicly available DEM cells. The site must contain at least 9 valid slope pixels, so tiny sites may require a higher-resolution uploaded DEM. If public GLO-30 cannot be retrieved, the 90 m fallback may also be too coarse.
- Cloud Vercel remains on the earlier frontend-only deployment until requested. The GitHub repository is the authoritative next test version. The Python GIS API requires a separate deployment/persistent storage architecture for actual hosted analysis. Never expose a GIS upload endpoint anonymously on the public internet.

---

## PLANEXUS Copilot V2.4 - GIS-grounded assistance (GitHub-only)

The Copilot has two distinct modes:

- **Before analysis:** truthful operational/workflow guidance, with no claimed site-specific slope, zoning, flood risk or housing yield.
- **After a saved GIS report:** focused responses to slope, elevation and preliminary housing questions grounded in the measured analysis. Every API response returns a separate machine-readable evidence object with the analysis ID, dataset type, source, coverage, resolution and measurements.
- **Without an OpenAI key:** deterministic question-aware GIS interpretations. This is NOT generative AI.
- **With a valid OpenAI key:** optional model-generated planning interpretation based on compact GIS evidence, with graceful fallback on provider errors. The presence of a key does not prove the model is connected; human verification is mandatory.
- **Without official RT/RSN/RFN/RKK/GPP, hydrology, soil and layout data:** the Copilot must not infer statutory zoning, approved density, flood safety, a permissible unit count or development approval. These topics receive scope-limited answers even when a model key is set.

### Windows local setup

1. Start both servers with START-PLANEXUS.bat or use the manual backend/frontend commands above.
2. Inspect GIS health at http://localhost:8000/api/health and capabilities at http://localhost:8000/api/copilot/capabilities.
3. You can ask about workflow before DEM analysis with no API key. A completed analysis unlocks GIS-specific measured questions.
4. For optional generative AI, copy backend/.env.example to backend/.env, add an authorized OPENAI_API_KEY and compatible OPENAI_MODEL, then restart the Python server. Never place secrets in Next.js or GitHub.
5. Confirm source, vertical-unit assumption, approximate coverage, data resolution and slope statistics against the saved report. For planning reports, compare results with an independent GIS workflow and official survey data.

### Tests and limitations

Automated GitHub Actions run Python terrain tests, API/Copilot safety tests, Next.js build checks, Chromium site persistence and Copilot UI checks. A separate live S3 diagnostic uses public Copernicus GLO-30 raster cells to test actual tile retrieval; this is a connectivity and calculation smoke test, not a field-survey or QGIS accuracy certificate.

Deployment is intentionally unchanged. The older Vercel site is a frontend preview and will not receive these commits until explicitly requested. GIS/Copilot features require a running Python backend; a public deployment would additionally need authorization, resource limits and persistent object storage.


---

## Phase 4 — Durable Project Workspace (local backend, GitHub only)

### What is actually persisted

- **SQLite project registry** inside `PLANEXUS_DATA_DIR/planexus-workspace.sqlite3`: names, descriptions, active site polygons, revision counters, linked terrain analysis IDs and created/updated timestamps.
- **GIS raster artifacts & evidence reports** in `PLANEXUS_DATA_DIR/jobs/<analysis UUID>/`: compressed GeoTIFF source and `result.json`, including derived slope, elevation and contour layers plus source metadata. Historical analyses are retained even after a project boundary is edited.
- **Browser localStorage** contains only the ID of the most recently opened project (`planexus:active-project:v1`) and the legacy polygon backup. On refresh, the current project and latest analysis are reloaded from SQLite/report JSON; localStorage is not the canonical project database.
- Projects are **separate**. Switching projects replaces the map geometry, slope/elevation/contour overlays and available analysis history with those belonging to the selected project.

### How to use (Windows local, not the old Vercel site)

1. Download the latest GitHub repository, extract the entire ZIP, and run `START-PLANEXUS.bat` (Node.js 22+; Python 3.11 or 3.12).
2. Open the new **Project Workspace** sidebar module. Choose **New project**, enter a name, and optionally attach your current browser-drawn polygon to migrate a browser-only site.
3. Open the project, draw or import your site polygon, and wait for **PROJECT SAVED**. Database writes use a revision counter: if another browser tab updated the same project, a stale write returns HTTP 409 instead of silently losing data.
4. Run **Get DEM & Run Analysis**, or upload a trusted local GeoTIFF. The analysis ID, source details, raster data, results and links are associated with the project in local persistent storage.
5. Switch to another project, refresh the browser, or restart the localhost servers. Open your saved project; the boundary and selected GIS analysis/layers should be restored automatically.
6. In **Saved Analyses**, choose any analysis associated with the active project to reopen its historical report. Reopening an older analysis intentionally restores the corresponding historical boundary.

### Data preservation, migration and security

**Back up the whole backend data directory regularly.** Stop both server terminals first, then copy `backend/data` (or the custom `PLANEXUS_DATA_DIR`) including the SQLite database and the entire `jobs` folder. The SQLite journal/WAL files may contain committed changes while the server is running; copying a live folder without a consistent snapshot can lose data. Do not commit this directory, rasters or API credentials to GitHub.

Deleting a project only removes its project index and associations; the archived analysis reports/raster files remain on disk by design. This prevents accidental destruction of evidence but requires deliberate disk management.

There is **no account login, user isolation, public API authentication, remote synchronization or cloud database yet**. The backend is for a single trusted local user and should run on `127.0.0.1` only. Do not expose ports 8000/3000 directly to the public internet. A real hosted deployment requires a protected API, tenant-aware permissions, a managed database, persistent object storage for DEMs/exports, resource quotas, backup/restore, and an authorization/ownership model. Vercel has **not** been redeployed.

### Project API

- `GET /api/projects` — list locally stored projects.
- `POST /api/projects` — create a project with optional WGS84 geometry.
- `GET /api/projects/{id}` — project boundary, revision and linked analysis history.
- `PATCH /api/projects/{id}` — rename / update site; requires `expected_revision` to prevent conflicting edits.
- `DELETE /api/projects/{id}` — delete project index only; raster reports remain.
- `POST /api/projects/{id}/activate-analysis` — reopen a historical project-linked analysis and its original site geometry.
- `POST /api/terrain/auto` and `POST /api/terrain/upload` optionally accept `project_id` so new reports are persisted and associated with the correct project.

For independent validation, run backend tests using `python -m pytest -q` in `backend` and browser tests using `npm run test:e2e` in `frontend`. The dedicated project test suite exercises SQLite durability across TestClient restarts, two-project isolation, stale revision rejection, correct analysis assignment, historical layer recovery and deletion behavior. Browser tests use a **synthetic mocked backend** for end-to-end UI behavior; no simulated raster should be presented as real site measurements.

### One-click local backup

After at least one project has been saved, stop the frontend/backend server terminals and double-click **BACKUP-PLANEXUS.bat**. This runs the Python SQLite backup API and creates a dated ZIP archive under the repository's `backups/` folder. The archive includes the project database, saved report JSONs, source GeoTIFFs and a `BACKUP-MANIFEST.json` file. It excludes unrelated secrets such as `.env` files. Store a private copy of the ZIP on another drive. The archive is not encrypted.

To restore onto another local machine: stop both PLANEXUS servers, first preserve any existing backend data directory, then extract the contents of the ZIP into the configured `PLANEXUS_DATA_DIR`. Remove stale SQLite `-wal`/`-shm` sidecar files left from the **old** database only while both servers are stopped. Restart the backend and confirm all projects/reports in the UI. Do not overwrite an existing workspace without a separate backup.

---

## Phase 5 - Terrain Suitability Engine (Module 1; GitHub/local only)

PLANEXUS now produces a **terrain constraint screening** overlay after a verified DEM/DSM raster analysis. It does NOT determine permission to develop land, official zoning, slope stability, permitted housing units, drainage suitability or engineering feasibility. This module is deterministic raster analysis, NOT an ML prediction.

### Explicit provisional thresholds

| Raster slope (degrees) | Screening label | Meaning |
|---|---|---|
| 0 to below 15 | Lower terrain constraint | Relatively lower slope constraints only |
| 15 to below 25 | Moderate terrain constraint | Detailed technical review needed |
| 25 and above | Higher terrain constraint | Closer assessment recommended, not an automatic statutory ban |
| No valid slope | Not assessed | Cannot infer suitability; do not assume the area is gentle |

These are PLANEXUS's provisional groupings, NOT official RT/RSN/RKK/GPP thresholds, land-use approval, geotechnical standards or a survey-based construction classification. All projects still require checks of policy, drainage, flooding, roads, geotechnics, ownership, verified DTM and site layout.

### How it works

- Bands are derived from the SAME projected metric raster slope grid and validity mask as the terrain engine. Pixel count multiplied by projected full-cell area produces an approximate hectare estimate. Band percentages are calculated from assessed slope pixels only.
- Invalid or missing slope pixels within the site are assigned to Not assessed rather than lower constraint. The approximate unassessed area also includes boundary differences between geodesic site area and raster-cell area.
- Raster-grid pixels at the polygon border may cause the area summed across all classes to exceed surveyed parcel area, particularly at coarse resolution. The system provides a warning instead of forcing pixel counts to match land title or cadastral areas.
- Vector map features are capped for browser performance; the class statistics use all valid slope cells. GLO-90 and DSM surface models may miss local gradients or include buildings/vegetation.
- The saved GIS report now includes a suitability summary and a suitability GeoJSON overlay. The markdown export includes method caveats and grouped areas. Legacy saved reports show an explicit request to rerun the DEM analysis rather than invent historical suitability.

### Test it locally (no Vercel deployment)

1. Update the repository locally and run START-PLANEXUS.bat. Ensure both FastAPI and Next.js are running.
2. Create/open a project and draw/import a real WGS84 polygon. Run Get DEM & Run Analysis, or upload an authorized raster.
3. Select the Suitability map layer next to Slope and Elevation. Review the colours, source, coverage, hectares and category distribution. Click a coloured map cell for a category explanation. Unassessed cells are not to be treated as developable.
4. Refresh and reopen the same project. The suitability overlay and counts should return with the stored analysis. Switch to a different project and verify there is no data leakage across projects.
5. Compare results with independent QGIS slope classification and the original raster before using in any professional planning report.

Unit tests cover the 15-degree and 25-degree thresholds, NoData, full-cell area estimates, overlay truncation and persistence. Chromium tests cover the suitability map layer and project restoration with a declared synthetic fixture. Live public GLO-30 retrieval is checked separately; it does not certify survey accuracy.

**Not included in Module 1:** development proposal input, housing unit/density calculation, layout scenarios, official policy lookup, hydrological assessment or AI approvals. These require additional inputs and will be handled in later modules. No Vercel deployment has been requested or performed.

---

## Phase 5 - Development Proposal Input (Module 2, GitHub/local only)

Use the new **Development Studio** sidebar module to define and save up to 20 independent, explicitly assumed development options per saved project. This module models **landed residential plots, shoplots and other landed lots only**. It does **not** model apartments, floors, GFA, FAR, engineering design, official density permissions, zoning or planning approval.

### Auditable, editable land-budget formula

- Inputs: scenario name; type of landed use; integer proposed unit/lot count; frontage (metres); depth (metres); user-assumed road, open-space, community-facility and other-reserve percentages.
- Plot hectares = units x frontage_m x depth_m / 10,000.
- Total reserved percentage = roads + open_space + facilities + other. This must be below 85%; each individual share is validated as 0-70%. Each allocation refers to a share of **required total gross land**, not of the net plot area.
- Required gross hectares = plot hectares / (1 - total_reserved_pct / 100). Individual reserve hectares are then calculated as a percentage of required gross hectares.
- Gross site density = proposed unit count / current gross project hectares. It remains a decimal; **one unit is not rounded to zero**. This is a proposal density, not the density permitted by the relevant RT/GPP.
- Gross area margin = gross project hectares - required gross hectares. Positive margin means the arithmetic land budget is not larger than the polygon, **not** that a compliant or connected layout is feasible.

**Updated default scheme (editable, not a national minimum):** 300 mid-cost terrace lots at **20 x 70 ft** (exactly 6.096 x 21.336 m), 20% assumed roads, 10% open space, 5% facilities and 5% other reserves produce approximately **3.90193 ha plot area** and **6.50321 ha required gross**. The previous 6.0 ha example applied to a different 6 x 20 m plot and is not the present default. All percentages remain user assumptions and are not planning standards.

### Comparison with measured terrain only

Saved scenarios evaluate against a project's active GIS suitability report only when it is the **same saved boundary and active analysis** used when the scenario was saved/reassessed. The calculator optionally compares gross requirement with the **raster-derived lower terrain-constraint cell-area estimate**, capped to site area. The result is labelled either an indicative cell-area envelope or a cell-area shortfall, always with warnings. It does not calculate spatially contiguous buildable land, real road layout, zoning, flood/drainage restrictions or allowable housing yield.

If a project boundary or active DEM analysis is changed, the scenario becomes **CONTEXT CHANGED / REVIEW GIS**. Its previous terrain comparison is withheld rather than silently carried across projects or datasets. Reopen and update the scenario to bind it explicitly to the current site and report. If no slope analysis is available, the form remains usable as an **area-only worksheet** with no GIS conclusion.

### Persistence and testing

- Scenarios are in the existing local SQLite project database's `project_proposals` table and are automatically included in `BACKUP-PLANEXUS.bat` because they share the database. There is no cloud sync or user authentication.
- `GET /api/projects/{project_id}/proposals` lists saved proposals and their current context-aware calculations; `POST` creates; `GET /{proposal_id}` fetches; `PUT /{proposal_id}` updates with `expected_revision` optimistic concurrency; `DELETE /{proposal_id}` removes only that proposal.
- Pydantic validates each submitted input and rejects invalid units, empty names, unsupported apartments, negative dimensions, NaN/Infinity and allocation totals of 85% or higher.
- Backend tests verify 300-unit area arithmetic, one-unit density, stale GIS context, different projects, editing concurrency and cascading project deletions. The Chromium browser test exercises live form editing, local persistence, reload and stale-context messages using explicitly MOCKED API responses; those mocks are not real terrain data.

### Test it locally

1. Update `Hariz-Zass/PLANEXUS-AI` to the latest main branch. Start the backend and frontend locally with `START-PLANEXUS.bat`.
2. Create/open a project and draw/import its polygon. Open **Development Studio** from the sidebar.
3. Set a proposal, adjust all assumptions, and inspect the live **gross land requirement**. Click **Save scenario**.
4. Reload the browser. Select the saved scenario and verify that units, lot sizes and reserve percentages return. Use **Update scenario** to edit.
5. Run a real DEM analysis for that project, then return to Development Studio. Previous scenarios will show **REVIEW GIS** until they are explicitly updated. Any comparison is **screening only**.
6. Save a second scenario and compare arithmetic land demand; test each project's isolation and back up your SQLite workspace before migrating machines.

**No Vercel redeployment** has been triggered. The previous public frontend remains unchanged. Module 3 (full option comparison / spatial layout suitability) and Module 4 (AI planning recommendation with verified policy inputs) are future work.

### Phase 5 GPP Knowledge Registry - evidence-linked planning guideline checks

The **GPP Knowledge Registry** now lists indexed versus catalog-only official PLANMalaysia sources. In Development Studio choose National GP001-A (2016) or Perak Housing (2023), specify house type and storeys, optionally input Perak price category/floor space/bedrooms/height, and press **Semak GPP**. Checks have source URLs and printed pages. You can replace a proposal dimension with a national minimum by choosing **Use GPP minimum (replaces proposal size)**, but this does not mean the PBT approves that lot or the whole development.

The first numerical edition includes selected national housing lot and one-storey floor-area minima (GP001-A Jadual 2) and state-level Perak PR1–PR6 floor/storey requirements; PR1 service-road/lane/setback dimensions are also listed as **unchecked references** because there is no measured layout geometry. Commercial, parking, community facilities and hillside GPP are **catalog only** until independently validated. Maximum house lot dimensions are left **unknown** when not expressly stated. Saved scenarios record a GPP registry version and require manual review when that version changes.

**Full coverage and editorial rules:** [docs/GPP_COVERAGE.md](docs/GPP_COVERAGE.md). No external GPP PDF is republished into this repository; only small sourced numerical checks and official links are stored.


### Low / Mid / High terrace sizes re-audited against GP001-A (November 2026)

**Development Studio now starts at Mid 20 × 70 ft** as a practical project layout example. The GPP panel adds **Low 20 × 55 ft**, **Mid 20 × 70 ft** and **High 22 × 75 ft (editable example)** buttons. These are design input presets, **NOT three statutory minima**. The official national GP001-A 2016 standard lists separate terrace **kos rendah**, **kos sederhana rendah** and **kos sederhana** bands; a dedicated national **teras kos tinggi** lot minimum is not provided in Jadual 2. GP001-A middle-cost minima are **20 × 65 ft (1–1½ storeys)** or **18 × 65 ft (2–3 storeys)**, whereas 20 × 70 ft is a legitimate project size and the older MBK review checklist calls 20 × 70 ft *teras biasa*, distinct from *kos sederhana* 20 × 65 ft.

Input values in exact feet (20 ft = 6.096 m) no longer fail because a GPP rounds the same figure to 6.1 m. The backend still compares each selected category and number of storeys against its actual official numeric minimum with document/page citations. Perak 2023 PR1 gives different **house floor area** minima, not a new 20 × 70 ft land lot rule. The user must choose appropriate state/PBT scope; "high" is not automatically mapped to a Perak market cost band.

Sources, foot/metre accuracy, all housing-category audits and comparison rules: [docs/GPP_COVERAGE.md](docs/GPP_COVERAGE.md). No Vercel deployment is performed by this change.


### Smart Layout Studio - projected road and land envelopes (Phase 5 Module 3, Steps 1–2)

The new local-only Smart Layout Studio sidebar module lets planners sketch/import/export WGS84 road-centreline GeoJSON, enter assumed reservation width and conceptual road-front/perimeter offsets, preview their **projected UTM polygon footprint** and save one revisioned layout concept per project in SQLite. Overlaps are unioned, not double-counted. With a complete matching GIS suitability overlay, an **indicative lower-slope area** and disconnected-patch count are displayed; otherwise no slope-backed land claim is made. Widths are user assumptions, not measured existing road/lot widths.

Optional Perak PR1 road and front setback numeric comparisons only compare typed input values to cited reference amounts: they are NOT verified building setback compliance or PBT approval. Stored lines are invalidated if project boundary changes; DEM changes require review. SQLite backups include layout sketches.

Read [the Smart Layout limits and QA guide](docs/LAYOUT_SCREENING.md). This feature remains on GitHub only, without a Vercel deployment.


### Step 3A — Road Network Validation (local GitHub-only)

Smart Layout Studio now screens road-sketch topology in projected UTM metres. It reports separately drawn road components, endpoint-based T-junction connections, **unconfirmed interior-only crossings**, close-but-unjoined lines, dangling sketch endpoints and outer site-boundary contact *candidates*. Matching map markers and a mobile-friendly diagnostics panel make disconnected conceptual alignments visible before any lot-generator work. A line crossing without an explicit endpoint is not assumed to be an at-grade road connection. A line touching the site edge is **not** proof of a legal/public road access point; grade, ownership, external streets, engineering design, accessibility and PBT review remain outside this check.

Detailed method and local QA: [docs/LAYOUT_SCREENING.md](docs/LAYOUT_SCREENING.md). No automatic lot placement, no Vercel deployment, and no changes to GeoPilot.


### Read-only one-click system check (Windows)

After starting `START-PLANEXUS.bat`, double-click
`CHECK-PLANEXUS.bat`. It checks that the local frontend and
FastAPI health, project/report registries, GPP catalog and Copilot capabilities
respond. This is a **read-only connection diagnostic**, not proof of a real
DEM run or planning approval. For full verification, create a project, upload
a documented GeoTIFF or run auto DEM, display both map layers, and reopen the
project. Existing site data are not modified by this diagnostic.


### B3.1 — GIS database backup and safe restore (GitHub-only)

Saved SQLite projects, GIS raster evidence, scenarios and Smart Layout data
can be archived in one verified ZIP and restored **offline into a new data
directory**, without overwriting a live project. Includes a Windows launcher
`BACKUP-PLANEXUS.bat`, SHA-256 integrity checks, and a Python
`app.backup_restore` verify/restore CLI. Follow
[the recovery runbook](docs/PERSISTENT_GIS_BACKEND.md).

This is not a deployed online GIS backend or a multi-user database. Private
single-instance durable storage and authentication are still prerequisites
for any online release. No Vercel deployment.

### B3.2 — Login, project ownership, and backend security (GitHub-only)

The entire GIS workspace is gated behind an invite-only login backed by
SQLite and HttpOnly cookie sessions. Cross-user access to projects, raster
reports, exports, Copilot evidence, scenarios and Smart Layout is rejected
by the API even when a project URL is guessed. The first admin is set up
interactively by `START-PLANEXUS.bat`; other users register with one-time
invites created offline by an admin.

Old projects are preserved but **not assigned automatically** to a new
account. Follow [B3.2 security setup and migration](docs/PERSISTENT_GIS_BACKEND.md).
No default password, no public signup, and no Vercel deployment.


### B3.3 — Independent terrain QA and QGIS-compatible raster comparison

The source-only GIS engine now uses a NoData-aware Horn 3x3 slope kernel
(the default GDAL/QGIS gdal:slope approach) on a metre-based UTM grid.
Each report separates elevation/slope data coverage and records input raster
SHA-256, processing CRS, metadata/quality warnings and exact derived GeoTIFF
grids to download privately. CI validates actual slope pixels against the
GDAL CLI, checks contour elevation levels, and separately attempts three
public Copernicus DSM sample areas in Malaysia. A full QGIS desktop manual
review and ground-truthed survey accuracy check remain outstanding.
See docs/TERRAIN_VALIDATION_B3_3.md for repeatable QA methodology.
No Vercel deployment is part of this work.


### B3.4 — Verified scheduled backup, offline recovery and GIS export

The repository now contains an **opt-in** Windows daily backup scheduler
(INSTALL-PLANEXUS-AUTO-BACKUP.bat), a separate optional Docker backup worker
(profile: backup), cross-process GIS write coordination, retention/mirror
verification, and an offline full-restore drill. Private site GIS export
provides genuine multi-layer GeoPackage, WGS84 GeoJSON, full-resolution UTM
GeoTIFFs when available, and a checksummed manifest. Map-rendered vectors
may be truncated and are NOT represented as full site analysis raster output.

See docs/B3_4_BACKUP_RECOVERY_EXPORT.md for setup, security, test coverage,
off-host requirements and scope limits. Push to GitHub only — no Vercel
deployment or user Task Scheduler installation was done automatically.


### November 2026 — End-to-end functional and data-source audit

See [Functional and Source Audit](docs/FUNCTIONAL_DATA_AUDIT_2026_11_03.md).
There are working GIS computation and project modules, but PLANEXUS must NOT
claim all Malaysian PBT zoning, official flood or legal-road datasets are
integrated. The previously decorative Site Context module now calls real
OpenStreetMap/Overpass with explicit attribution and no invented records,
but public Overpass hosts are unreliable in CI. An optional managed hosted
source can be configured via server-only PLANEXUS_OVERPASS_CH_API_KEY.
The Data Registry now reports the actual maturity of each data source,
including GPP documents with no machine-readable rules. No Vercel deployment.
