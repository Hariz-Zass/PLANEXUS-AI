# PLANEXUS — B3.3 Terrain and GIS Verification

Scope: numerical DEM processing, independent GDAL slope comparison, three
public Malaysian Copernicus sample areas, browser map checks and an audit
runbook. This is NOT a field survey, QGIS GUI sign-off, engineering certificate,
zoning validation, PBT approval or production deployment.

## A. Processing and input-data checks

- Public Copernicus GLO-30 DSM and an explicitly labelled GLO-90 fallback.
  Unavailable public tiles are errors; PLANEXUS never fabricates heights.
- User-uploaded GeoTIFF band 1, CRS and metre-height declaration; if the band
  explicitly declares feet, analysis is rejected instead of silently scaling.
- Input raster SHA-256, byte length, original CRS, original pixel dimensions,
  NoData and declared vertical band units are retained in each analysis.
- Bilinear warp to metre-based local UTM, followed by a Horn 3x3 slope kernel
  in degrees. No edge interpolation; 3x3 support with a NoData cell means
  slope is UNKNOWN, never zero degrees.
- Elevation coverage and slope coverage use the same projected grid mask:
  valid site-centre cells / all site-centre cells. Pixel-centre area is also
  compared with geodesic site area to detect coarse boundary approximation.
- Preliminary slope classes: I [0,15), II [15,25), III [25,35), IV [35,90].
  No slope means unassessed, not buildable. Class areas use all valid pixels,
  although MapLibre polygons may be truncated for performance.
- Elevation minimum/mean/maximum, six-band visualization, contour lines and
  contour interval originate from the actual valid raster.
- QA indicators SCREENING / REVIEW / LIMITED grade this computation only.
  DSM is NOT a bare-earth DTM and matching a different GIS tool does not
  establish survey-level vertical accuracy.

## B. Repeat the exact slope computation in QGIS

Each newly analysed project stores two additional protected rasters:
- jobs/<analysis-uuid>/elevation_utm.tif (exact projected height grid)
- jobs/<analysis-uuid>/slope_degrees_utm.tif (exact PLANEXUS Horn output)

Download both from Terrain Intelligence > GIS DATA QUALITY, while logged into
the correct owner account. The server also offers a private GIS QA markdown
report and original planning report. Older reports show LEGACY, not a false
verification status.

Open both in QGIS. Choose Processing Toolbox > GDAL > Raster Analysis > Slope
(algorithm ID gdal:slope) and set:

| Parameter | Value |
| --- | --- |
| Input | elevation_utm.tif |
| Band | 1 |
| Slope unit | Degrees, AS_PERCENT=False |
| Scale | 1.0 (metres/metres) |
| Compute edges | False |
| Zevenbergen & Thorne | False (GDAL default Horn) |
| Output | qgis_gdal_horn_slope.tif |

Compare output to PLANEXUS slope_degrees_utm.tif on the identical pixel grid
and exclude NoData. Automated numerical acceptance thresholds:

- Identical CRS, dimensions and affine UTM transform.
- Zero disagreements in NoData/validity masks.
- Slope RMSE no greater than 0.02 degrees and maximum difference no greater
  than 0.12 degrees.

These thresholds apply to algorithm parity on the SAME projected input grid.
Comparing different input DEM resolutions, sampling grids or slope algorithms
is not a valid numerical accuracy test. QGIS Processing gdal:slope is backed
by GDAL; CI tests gdaldem slope -alg Horn -s 1, not the actual QGIS desktop
application. A manual QGIS screenshot/sign-off is still outstanding.

For elevation, compare min/mean/max using the same valid-cell mask and UTM
grid. For contours, compare interval and elevation levels plus geographic
plausibility: QGIS contour generators may interpolate vertices differently
from PLANEXUS contourpy. The Python QA test bilinearly samples the saved
projected DEM along generated contour vertices, allowing for WGS84 rounding.

Official references:
- https://docs.qgis.org/3.44/en/docs/user_manual/processing_algs/gdal/rasteranalysis.html
- https://gdal.org/en/stable/programs/gdaldem.html
- https://registry.opendata.aws/copernicus-dem/

## C. Automated and real-source test evidence

GitHub Actions runs:
1. Synthetic flat, gentle, steep and mixed Horn raster tests, with a NoData
   patch and exact analytical planar slope comparison.
2. Independent GDAL CLI slope pixel comparisons on three SYNTHETIC profiles.
   Output artifact: b3-3-gdal-reference. This is numerical implementation
   parity only.
3. Actual Next.js + FastAPI browser tests verifying real GeoTIFF upload,
   map overlay feature counts, Slope/Elevation/Contour controls, quality
   report, source SHA-256 and protected downloads.
4. Live Copernicus DSM checks on three distinct public WGS84 sample squares:

| Sample area | WGS84 bounds west,south,east,north |
| --- | --- |
| Meru Raya, Perak | 101.066, 4.664, 101.083, 4.679 |
| Klang, Selangor | 101.435, 3.040, 101.451, 3.055 |
| Cameron Highlands, Pahang | 101.375, 4.470, 101.390, 4.485 |

Their terrain class/steepness is not assumed in advance. Results are measured
only when public COG data can actually be acquired; otherwise the report
records unavailable_or_failed. For successful downloads, the artifact records
source tile URLs, SHA-256, source ID, fallback type, CRS, height statistics,
slope classes, contours, QA flags and independent GDAL RMSE.
Output artifact: b3-3-malaysia-three-site-gis. Because external S3
availability is outside repository control, this CI job is non-blocking.
A green main CI is NOT evidence that these three remote downloads succeeded.

## D. Local commands

From backend/ with the project virtual environment activated and the
independent GDAL CLI program (gdaldem) installed:

~~~bash
python -m pytest -q tests/test_terrain_validation.py
python -m tests.gdal_horn_reference
python -m tests.three_site_live_validation
~~~

The third command needs external internet and public AWS S3/Copernicus tile
coverage; it must never substitute synthetic values when access fails.
Keep user projects, source rasters and ZIP backups private.

These tests do not independently establish the DEM's actual vertical
accuracy against ground-truthed reference points, geotechnical suitability,
drainage risk, RT/RSN/GPP applicability or PBT approval. Cloud backend and
Vercel deployment are OUT OF SCOPE for B3.3.
