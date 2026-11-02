# PLANEXUS AI — Smart Layout Studio (Phase 5, Module 3: Steps 1–2)

**Implementation:** backend layout_engine.py / layout_store.py; frontend LayoutStudio.tsx / LayoutMap.tsx. Local-only project workspace. **NOT** an approved subdivision, road design, housing yield or PBT planning approval.

## What users can do

1. Open/create a project with a real saved site GeoJSON boundary in Project Workspace.
2. Open the new **Smart Layout Studio** sidebar module. Draw LineString road-centreline sketches on MapLibre by clicking vertices and double-clicking to finish, or import road-centreline GeoJSON. Export sketches as GeoJSON for local GIS workflows. Maximum 12 lines, each 2–200 vertices, wholly within the site boundary.
3. Enter **assumed** road reservation width (3–60 m), assumed buffer outside road edge (0–30 m) and optional inward site-perimeter offset (0–30 m). These values do NOT measure real roads, legal reserves or building setbacks.
4. Use Preview layout (unsaved) to calculate a site-based land envelope. Use Save layout to store the draft in the active project's SQLite database with revision control, including in the existing private local backup.
5. Review the colours, area figures, lower-slope overlap and warnings. Reload the project to restore the saved road geometry and parameters.

## GIS methodology and limits

All measurements are computed in the local UTM projected coordinate reference system, in metres, not degrees:

- Modelled road corridor = union of centreline buffers (half the **entered** road width), intersected with the actual site polygon.
- Modelled front-road band = larger centreline buffer (half-road-width plus **entered** additional road-edge distance), minus the road corridor. This is NOT a real front building setback: there are no individual building outlines or measured lot frontages.
- Optional perimeter band = the outer site polygon region excluded by the **entered** inward offset. It is NOT a legal side/rear setback.
- Combined exclusion area = geometric union of road + front-road + perimeter bands; overlaps are counted only once. Gross remaining area = site polygon minus those exclusions.
- If current DEM analysis has complete suitability GeoJSON, class 1 lower-constraint raster polygons are intersected with the remaining site; the engine returns provisional lower-slope overlap, number of disconnected pieces and largest connected polygon. This is not a residential lot-fit calculation.

Boundary pixels are not survey-accurate. DSM can include buildings and vegetation. An incomplete/truncated suitability overlay, mismatched project site, absent DEM or invalid source means **no defensible lower-slope overlap** is output. Coarse ~90 m DSM, under 95% coverage, fewer than 100 valid slope cells or pixel-area uncertainty are explicitly labelled low confidence. The map rendering may be simplified independently of precise backend area calculations. Nothing here establishes contiguous buildable land, slope stability, access, drainage/flood safety, title, zoning or permission to build.

## Manually scoped Perak GPP PR1 reference

If the user explicitly selects Perak 2023 PR1 for terrace housing, the displayed references are:
- Service road **minimum 50 ft = 15.24 m**.
- Low-cost terrace front-setback reference **15 ft = 4.572 m**.
- Other covered terrace front-setback reference **20 ft = 6.096 m**.

Official source: https://lphp.gov.my/index.php/pekeliling-lphp/35-gp-piawaian-perumahan-negeri-perak-2023-1/file (PR1, printed page 5).

Checks compare the **entered assumption** to the numeric reference only. They DO NOT verify a built road's width, actual house setback, statutory adoption, applicable local RT or PBT compliance. No automatic PBT selection from coordinates is made.

## API and persistence

- GET /api/projects/{id}/layout returns saved draft and context-aware screening.
- POST /api/projects/{id}/layout/preview calculates current draft without saving.
- PUT /api/projects/{id}/layout saves with an expected_revision optimistic-concurrency check.
- A single concept draft per project is kept in the project_layouts SQLite table; existing BACKUP-PLANEXUS.bat includes it. No authentication or cloud sync.

When the saved project boundary changes, old road sketches are hidden and cannot be used on the new site; the user must clear and resave. When active DEM changes, the geometry-only envelope is shown but slope overlap is withheld until explicit resave/review. Geometry lines outside the current site are rejected.

## Local acceptance test

1. Pull/download the latest GitHub PLANEXUS-AI main, start locally with START-PLANEXUS.bat.
2. Create a saved project boundary, then draw a road inside it or import one valid LineString.
3. Enter a road width and concept offsets; click Preview. Confirm map layers, gross remaining hectares and class-1 overlap (only with real valid DEM evidence).
4. Save and reload; ensure parameters and road sketch return. Change width and confirm the area numbers change only after preview or saving.
5. Enable Perak PR1 and confirm numeric reference warnings. Change the project polygon and confirm old sketches are withheld; select a different DEM and confirm the GIS comparison must be reviewed.
6. Create a second project to verify project isolation; archive a private local backup before moving computers.

**Not yet implemented:** actual lot layout, residential-unit fitting, lot-front building setback compliance, road junction connectivity/external access, gradient design, geotechnics, flood/drainage, local zoning, title/ownership and automated PBT decision. These are later modules.

No Vercel deployment; existing GeoPilot repo untouched.
