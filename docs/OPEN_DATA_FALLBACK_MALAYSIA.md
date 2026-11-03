# PLANEXUS — Open-data fallback for Malaysia (operator guide)

## Why

Overpass public mirrors occasionally return 502/504 or time out. Those
outages must not cause PLANEXUS to invent a facility inventory, or require
every planner to find and upload GIS files manually.

## Implemented hierarchy

1. The configured managed Overpass-compatible service (if an operator has
   supplied PLANEXUS_OVERPASS_CH_API_KEY), followed by documented public
   Overpass instances, with error and metadata checks.
2. When all online attempts fail, an **optional server-installed** Geofabrik
   OpenStreetMap GeoPackage for Malaysia/Singapore/Brunei is queried locally
   using Fiona's bounding-box filtering and WGS84 distance checks.
3. If neither source works, a real HTTP 503 error is returned. Zero features
   are NEVER fabricated to hide an outage.

This is for background facilities/roads/waterways **only**. It is **not**
gazetted zoning, a legal-access determination, a cadastral layer, or flood risk.

## One-time setup by backend operator

Geofabrik publishes region extracts in OSM PBF, Shapefile and GeoPackage.
See https://download.geofabrik.de/asia/malaysia-singapore-brunei.html .
Use the `malaysia-singapore-brunei-latest-free.gpkg.zip` distribution.

1. Download the GeoPackage ZIP via the operator's infrastructure (the file
   is hundreds of MB). Verify its origin and, where available, checksum.
2. Unzip onto **persistent backend storage**, e.g. `/data/osm/`. Do not
   commit the dataset into this GitHub source repo.
3. Identify the `.gpkg` file(s) containing Geofabrik's free layer names:
   `gis_osm_pois_free_1`, `gis_osm_roads_free_1`, etc. The configured path
   may be a **single multi-layer GeoPackage or a folder containing GeoPackage
   files**. Keep the regional dataset, not a cadastral export.
4. Set backend-only environment variables:

       PLANEXUS_OSM_GEOFABRIK_GPKG=/data/osm
       PLANEXUS_OSM_EXTRACT_DATE=2026-11-02T00:00:00Z

   Set the date to the **actual extract snapshot date**, not the date the
   backend first used the file. If not known, leave the variable unset.
5. Restart the backend. The fallback is queried **automatically for every
   authenticated site-context scan** when live Overpass providers fail.
   Planners should not upload a copy for each site.

The server operator should schedule an out-of-band refresh; use atomic file
replacement only after a new GeoPackage has been verified. No automatic
500 MB download is triggered by user requests. Source data must remain
attributed as OpenStreetMap contributors and comply with ODbL.

## Runtime evidence

The site-context JSON identifies `source_id` as
`geofabrik-osm-gpkg-snapshot`, carries
`dataset_timestamp_utc` if available, and marks
`source_quality=community_unverified_not_official`. It also includes
prior live-provider failures so operators can diagnose API availability.
The Data Registry has a `geofabrik_osm_gpkg` configured flag.

The selection and validation logic has a synthetic **local GeoPackage** test
fixture which exercises the real Fiona file driver, polygon proximity and
category parser; this is not proof of a production-sized Malaysian extract
until a real file is provisioned and checked.

## Limits and next engineering gate

The Geofabrik free GIS layers contain a selected set of OSM feature types:
counts/categories will not necessarily match Overpass. Points for lines and
polygons use geometry representative locations; this is approximate context
screening, not network routing or confirmed road accessibility. The adapter
limits the number of scanned features; dense sites may need an indexed
PostGIS extract or dedicated hosted Overpass service.

Overture Maps GeoParquet is another open-data candidate, **not integrated**
in this release. Avoid claiming it is operational without a real adapter
and a site-level acceptance test.

Official RT/PBT zoning, RSN/RFN, lawful road reserves and JPS flood layers
still require data permission, authoritative legal versions and spatial
verification.

## Source and legal references

- Geofabrik Malaysia/Singapore/Brunei: https://download.geofabrik.de/asia/malaysia-singapore-brunei.html
- Geofabrik free OSM extracts: https://www.geofabrik.de/en/data/shapefiles.html
- OSM copyright and ODbL: https://www.openstreetmap.org/copyright
- Overpass reliability guidance: https://overpass.ch/guides/overpass-api-alternatives
- Overture open data: https://registry.opendata.aws/overture/
