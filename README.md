# PLANEXUS AI — Terrain Intelligence V1

**Your Geospatial Planning Copilot for Urban & Regional Planning.**

> **Status:** Local-development prototype. The Python terrain engine has automated tests; the Next.js UI is implemented but must be installed and built in an environment with npm registry access. **Not deployed and not production-ready.**
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

