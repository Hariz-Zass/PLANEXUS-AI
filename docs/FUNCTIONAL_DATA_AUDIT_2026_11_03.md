# PLANEXUS AI — Functional & Data Source Audit

Audit date: 3 November 2026. Repository: Hariz-Zass/PLANEXUS-AI, main.
Scope: code-to-backend inspection, automated browser/FastAPI/SQLite/GDAL,
genuine Copernicus and third-party URL diagnostics.
**Verdict: NOT READY to promise comprehensive, authoritative planning data.**

A passing build is NOT proof that every remote source is available or a
statutory reference is current. Full local Windows and independent surveyed
height validation have not yet been witnessed.

## Function-by-function truth table

| Feature | Back-end outcome | Evidence classification | Gap to real town-planning use |
| --- | --- | --- | --- |
| Account registration/login/logout | Invite-only cookie + CSRF and ownership enforcement | Automated tested | No production MFA, HTTPS host or identity provider |
| Project create/rename/reopen/delete | SQLite and revisioned GeoJSON project records | Automated tested | Needs real PC verification and durable hosted database |
| Draw/import/save site | Validated EPSG:4326 polygon and backend save | Automated tested | Boundary is NOT a surveyed cadastral parcel |
| Auto DEM | Real Copernicus GLO-30 public DSM/GLO-90 fallback COG | Live tested 3 Malaysia samples | Some tiles absent; 30m DSM is not detailed DTM |
| Upload GeoTIFF | CRS, units, NoData and source format checks | Automated tested | Uploaded provenance/vertical datum not independently certified |
| Slope, Elevation, Contours | Real Horn/GDAL-compatible calculations and MapLibre layers | Automated tested | QGIS GUI/field measurements still outstanding |
| Suitability | Slope screening and unassessed NoData handling | Tested screening | Does NOT calculate statutory developability |
| Data Quality | Source SHA, CRS, UTM-derived rasters, quality flags | Tested | File hash does not prove source authenticity |
| Saved Analyses and GIS Export | Owner-protected JSON, .gpkg, .tif, ZIP with manifest | Tested | Historical vector preview may be truncated |
| GPP Knowledge Registry | TWO housing docs with curated numerical clauses | Partially indexed | FOUR other documents catalogue-only; local adoption not verified |
| Semak GPP | Real numeric comparison for indexed categories | Limited | No automatic RT/PBT applicability by site |
| Development Studio | Saved user-assumption scenario/yield estimator | Tested screening | Not statutory permissible density or final design |
| Smart Layout Studio | Drawn road topology and parcel screening | Tested screening | No verified public-road ownership or PBT design approval |
| Copilot | Measured GIS summary; LLM optional if configured | Tested | No connected official by-lot RT, flood, road access |
| Backups and restore | SQLite/raster ZIP, lock, scheduler, restore into clean volume | CI/Docker tested | Operator must configure protected off-host backup |
| Data Registry | Real API reports per-source status, NOT an all-ready claim | Tested | No automatic official zone/RT upload or licences |
| Site Context | One-click OSM features by categories, source IDs, timestamps and cache | Logic tested, external provider unreliable | Public Overpass timed out/failed; community data not official |
| RTD/RKK/RSN/RFN zoning by site | Viewer links only | **NOT INTEGRATED** | Licensing, exact geometry, gazette date and PBT matching |
| Hydrology, flood/runoff | No full JPS geospatial overlay/design runoff | **NOT INTEGRATED** | Appropriate JPS source, rainfall, catchment and drainage survey |
| External roads/legal access and title | Only sketches and OSM proximity | **NOT VERIFIED** | Road reserve, title/cadastral and legal access from agencies |

## Verified external-data situation — 3 November 2026

- Copernicus GLO-30 Public COG was retrieved for real sample areas in Meru
  Raya, Klang and Cameron Highlands. Independent GDAL Horn numerical comparisons
  passed. This is algorithmic agreement, NOT observed land height truth.
- OpenStreetMap public Overpass tests encountered connection/read timeouts
  on independent instances; a browser button and unit tests cannot erase this
  fact. The adapter now tries documented alternatives. An operator may
  provision a hosted Overpass.ch API key in the backend environment variable
  PLANEXUS_OVERPASS_CH_API_KEY. Key remains server-side; no key or fake data
  is shipped. Without a reliable provider this feature is NOT production ready.
- An official GPP URL reachability probe returned five responding links out
  of six; the primary GP001-A document link timed out. An alternative official
  link is exposed when present. HTTP 200 alone DOES NOT verify numeric
  regulations or edition/implementation.
- GP001-A housing 2016 and Perak housing 2023 are the only curated numeric
  policy documents in the code. Parking, hill-development, trade and community
  facilities have catalogue links, not machine-readable regulatory rules.
- PLANMalaysia I-Plan is an official viewer, but displayed content must not
  be copied/republished without appropriate rights. Gazetted RT/PBT versions
  govern the local parcel. MyGDI metadata links do not confer redistribution
  rights for restricted agency-controlled datasets.
- JPS InfoBanjir station information is not a land-parcel flood hazard layer.
- OpenStreetMap ODbL road, education and transport features are useful for
  early context but do not certify public road access, institution presence,
  transport schedules or current local services.

## Real fixes in this audit

1. Backend API now serves truthful source integration maturity per module.
   Frontend Data Registry displays actual status, official links and a second
   official document link when provided.
2. Decorative locked Site Context SOON has been replaced with an actual
   authenticated Site Context tab. Opt-in scan retrieves actual community
   Overpass objects, counts, names, OSM feature URLs and source timestamp.
   There are NO invented points when the source fails.
3. Added public-provider availability diagnostics, permission/coverage labels,
   fail-closed tests, per-user context isolation and boundary change
   invalidation. Cached context now survives verified backup/restore.
4. Updated misleading wording: project account security exists; raster
   values are raster-calculated, not certified survey measurements.
5. Official GPP source probe now tests an alternative official document URL,
   not just the primary link, and explicitly does NOT reverify legal rules.

## Required gates before this can be marketed as one-stop planner

| Priority | Missing function | Proof needed |
| --- | --- | --- |
| P0 | Statutory site zoning and allowed uses | Licensed official geospatial RT/PBT source; verified boundary, effective gazette, source URL and clause |
| P0 | Complete local GPP assessment | Current PBT version, licensed full numeric tables, regulator relevance and tests |
| P0 | Reliable automated surrounding data | Hosted/own Overpass or permitted regional extract with uptime, timestamp and ODbL data-source attribution |
| P1 | Official flood/drainage/rainfall | Agency-authorized JPS datasets, scale/coverage/datum, hydrology design model, no invented flood-safe claims |
| P1 | Legal access and cadastral parcels | Authorized survey, land title, reserved/public road layers from agency and exact site overlay |
| P1 | Quality acceptance | Actual planner test on Windows/mobile; same-lot QGIS GUI, surveyed DTM, restart/restore and API failure scenarios |
| P2 | Source monitor and cache policy | Recurring availability/latency tests, versioned cache with freshness and failover alerts |
| P2 | Hardened online release | Protected host, encryption, off-host backup, rate limits, MFA and independent authorization audit |

### Release decision

**Terrain computational screening**: suitable for a carefully labelled
private pilot and manual professional review.
**PLANEXUS AI complete authoritative planning assistant**: NOT YET COMPLETE.

Do not claim a dataset is integrated because an official hyperlink exists.
For an authoritative answer, the licensed dataset must actually be acquired,
spatially matched to the saved site, checked for current legal effect,
and cited with source/edition/retrieval date. If a source is unavailable,
show its genuine retrieval failure without fabricating the missing fact.

## Supporting references

- docs/B3_3_VALIDATION_RESULTS_2026_11_03.md
- docs/TERRAIN_VALIDATION_B3_3.md
- docs/B3_4_BACKUP_RECOVERY_EXPORT.md
- docs/GPP_COVERAGE.md
- https://iplan.planmalaysia.gov.my/public/geoportal
- https://www.openstreetmap.org/copyright
- https://wiki.openstreetmap.org/wiki/Overpass_API
- https://www.planmalaysia.gov.my/main/garis-panduan-perancangan

All work is GitHub source only. Vercel has not been deployed.
