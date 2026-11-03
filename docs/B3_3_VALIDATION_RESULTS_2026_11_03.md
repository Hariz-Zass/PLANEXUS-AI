# PLANEXUS AI — B3.3 Validation Results (2026-11-03)

**Result scope:** three public Copernicus GLO-30 DSM sample squares in Malaysia,
plus an independent GDAL Horn slope comparison on the SAME UTM processing grid.
The QGIS desktop interface was **not executed**, and no survey ground-truth
dataset was supplied. These are public reference samples, not the user's site
or a PBT approval report.

## Evidence (GitHub Actions)

- Confirmed passing CI: https://github.com/Hariz-Zass/PLANEXUS-AI/actions/runs/41566262706
- Three-site real DSM + independent GDAL numerical comparison artifact:
  https://github.com/Hariz-Zass/PLANEXUS-AI/actions/runs/41566262706/artifacts/13199785993
- Separate independent GDAL comparison on three synthetic profiles:
  https://github.com/Hariz-Zass/PLANEXUS-AI/actions/runs/41566262706/artifacts/13199496232
- Reproduce the methodology: TERRAIN_VALIDATION_B3_3.md in this docs folder.

## Three real Malaysian sample areas

| Actual public sample area | Minimum / mean / maximum DSM elevation (m) | Mean / max Horn slope (degrees) | Contour features | PLANEXUS vs GDAL slope RMSE (degrees) | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Meru Raya, Perak | 52.50 / 78.52 / 202.50 | 5.45 / 32.73 | 17 | 0.000004 | PASS |
| Klang, Selangor | 0.50 / 7.28 / 33.40 | 2.48 / 14.91 | 83 | 0.000000 | PASS |
| Cameron Highlands, Pahang | 1418.77 / 1481.58 / 1577.83 | 12.99 / 34.38 | 35 | 0.000070 | PASS |

### Geographic and source controls

| Sample | WGS84 west,south,east,north | Source | Input horizontal CRS | Projected CRS |
| --- | --- | --- | --- | --- |
| Meru Raya | 101.066,4.664,101.083,4.679 | GLO-30 Public, no fallback | EPSG:4326 | EPSG:32647 |
| Klang | 101.435,3.040,101.451,3.055 | GLO-30 Public, no fallback | EPSG:4326 | EPSG:32647 |
| Cameron Highlands | 101.375,4.470,101.390,4.485 | GLO-30 Public, no fallback | EPSG:4326 | EPSG:32647 |

All three reported elevation and slope cell-centre coverage **100%** for
their selected processing grids in this run. This does not imply all land
pixels everywhere in Malaysia have coverage.

The actual public Copernicus tiles were retrieved through HTTPS public
COG windows, not simulated or manually fabricated. Full tile URLs, UTC
retrieval metadata, input file SHA-256, grid statistics and individual QA
flags are available in the downloadable GitHub artifact. All three reports
are marked **REVIEW** because GLO-30 DSM can include vegetation and buildings.

The independent comparison used 'gdaldem slope -alg Horn -s 1'
with edge interpolation OFF on the exact saved projected DEM. In all cases
the NoData masks matched exactly (zero mismatches). The reported maximum
absolute differences were respectively 0.000027°, 0.000003°, and 0.000275°,
well within the declared 0.12° acceptance bound. Mean/RMSE figures are
based on raster cells, NOT geotechnical quality.

## What passed, and what is still missing

- PASS: valid input DEM read; source metadata retained; bilinear UTM grid;
  Horn slope pixel computation; elevation and slope classes; contour
  generation; NoData and source SHA; independent GDAL numerical parity.
- PASS: zero nonmatching NoData masks in the three actual raster samples.
- PASS: three separate SYNTHETIC GDAL reference profiles (flat, gentle,
  mixed) in the independent job.
- NEEDS MANUAL REVIEW: open exported UTM elevation and slope in actual QGIS
  desktop and document screenshots of gdal:slope settings/result overlays.
- NEEDS INDEPENDENT REFERENCE DATA: field survey/GNSS/JUPEM DTM or verified
  spot heights in a known vertical datum, to establish actual vertical
  accuracy rather than mere numerical equivalence.
- NOT ASSESSED: planning permissions, statutory RT/RSN/GPP zoning,
  hydrology, geotechnical risk and land-title constraints.
- NOT DEPLOYED: this source change does not connect or update Vercel.

**Interpretation:** B3.3 establishes reproducible GIS processing and
traceability for the tested DEM sources. It does not make the three sample
sites suitable for development, nor does it certify PLANEXUS for regulatory
or engineering decisions.
