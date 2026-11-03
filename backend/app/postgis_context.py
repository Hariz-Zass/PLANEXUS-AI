"""Optional PostGIS-first OpenStreetMap site-context reader.

Uses a *locally imported* Geofabrik OSM snapshot rather than calling an
Overpass instance for every user query. This does NOT confer official PBT
facility, road-access, flooding or zoning status. Credentials are never
returned to a browser. See scripts/import_osm_postgis.py.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import psycopg
from shapely.geometry import shape

from .geofabrik_context import GEOFABRIK_REFERENCE, OSM_LICENCE, _CATEGORIES

# Slow or unresponsive database servers must not block planners indefinitely.
CONNECT_TIMEOUT_SECONDS = 3
QUERY_TIMEOUT_MS = 7000


def configured() -> bool:
    return bool(os.getenv("PLANEXUS_OSM_POSTGIS_DSN", "").strip())


def connect():
    dsn = os.getenv("PLANEXUS_OSM_POSTGIS_DSN", "").strip()
    if not dsn:
        raise ValueError("PLANEXUS_OSM_POSTGIS_DSN is not configured.")
    return psycopg.connect(dsn, connect_timeout=CONNECT_TIMEOUT_SECONDS)


def fetch_postgis_context(geometry: dict[str, Any], *, radius_m: int,
                          geometry_sha256: str) -> dict[str, Any]:
    if not 250 <= radius_m <= 2000:
        raise ValueError("Site-context search radius must be 250 to 2000 metres.")
    centre = shape(geometry).representative_point()
    lon, lat = round(centre.x, 5), round(centre.y, 5)
    # Reference WGS84 point is not a precise access location or legal boundary.
    point_sql = "ST_SetSRID(ST_MakePoint(%s,%s),4326)"
    within_sql = ("ST_DWithin(f.geom::geography, " + point_sql +
                  "::geography, %s)")
    params = (lon, lat, radius_m)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('statement_timeout', %s, TRUE)", (str(QUERY_TIMEOUT_MS),))
            cur.execute(
                "SELECT snapshot_at_utc, row_count FROM planexus_osm.snapshot "
                "WHERE snapshot_id=1 AND completed=TRUE")
            snapshot = cur.fetchone()
            if not snapshot or int(snapshot[1]) <= 0:
                raise ValueError("No completed, non-empty OSM PostGIS snapshot installed.")
            snapshot_date, imported_rows = snapshot
            # A coarse coverage guard: an unrepresented region must not be
            # reported as zero facilities. Zero hits inside a valid snapshot
            # can still be legitimate, especially in remote locations.
            cur.execute(
                "SELECT ST_Within(" + point_sql + ", "
                "ST_Expand(bounds, 0.03)) FROM planexus_osm.snapshot "
                "WHERE snapshot_id=1", (lon, lat))
            inside = cur.fetchone()
            if not inside or inside[0] is not True:
                raise ValueError("Requested location lies outside the imported OSM extract.")
            cur.execute(
                "SELECT category, COUNT(*) FROM planexus_osm.features f WHERE "
                + within_sql + " GROUP BY category", params)
            counts = {key: 0 for key in _CATEGORIES}
            for category, count in cur.fetchall():
                if category in counts:
                    counts[category] = int(count)
            # Use exact closest-on-geometry distance, not the midpoint of a
            # long street crossing the circle. Skip names on road/waterway.
            cur.execute(
                "SELECT f.category, f.name, f.osm_ref, "
                "ST_Distance(f.geom::geography, " + point_sql + "::geography), "
                "ST_X(ST_ClosestPoint(f.geom," + point_sql + ")), "
                "ST_Y(ST_ClosestPoint(f.geom," + point_sql + ")) "
                "FROM planexus_osm.features f WHERE " + within_sql +
                " AND f.category NOT IN ('roads','waterways') "
                "AND f.name IS NOT NULL AND f.name <> '' "
                "ORDER BY 4 ASC, f.name ASC LIMIT 31",
                (lon, lat, lon, lat, lon, lat, *params))
            rows = cur.fetchall()
    places = []
    for category, name, osm_ref, metres, x, y in rows[:30]:
        if not name or not all(v is not None for v in (metres, x, y)):
            continue
        places.append({
            "name": str(name)[:120],
            "category": category,
            "distance_from_reference_point_m": round(float(metres)),
            "coordinates_wgs84": [round(float(x),6), round(float(y),6)],
            # Geofabrik free GIS layers do not reliably preserve object
            # node/way/relation type, so never manufacture individual OSM URLs.
            "osm_url": OSM_LICENCE,
            "osm_feature_id": "postgis:" + str(osm_ref),
        })
    date = snapshot_date.isoformat() if hasattr(snapshot_date,"isoformat") else str(snapshot_date)
    return {
        "status": "retrieved",
        "source_id": "geofabrik-osm-postgis-snapshot",
        "source_name": "OpenStreetMap contributors / Geofabrik PostGIS snapshot",
        "source_url": GEOFABRIK_REFERENCE,
        "api_endpoint": None,
        "licence": "ODbL; " + OSM_LICENCE,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_timestamp_utc": date,
        "source_quality": "community_unverified_not_official",
        "retrieval_service_reliability": "self_hosted_postgis_snapshot",
        "reference_point_wgs84": {"latitude": lat, "longitude": lon},
        "radius_m": radius_m,
        "counts": counts,
        "named_places": places,
        "named_places_truncated": len(rows) > 30,
        "returned_feature_count": sum(counts.values()),
        "geometry_sha256": geometry_sha256,
        "warnings": [
            "Regional OpenStreetMap snapshot, NOT an official PBT facility inventory.",
            "Snapshot date identifies source-data age, not the time of this scan.",
            "Geofabrik filtered features may differ from online Overpass counts.",
            "Distance is WGS84 nearest-geometry distance from an internal site point, not driving distance.",
            "Road features do not certify lawful site access; water features are not JPS flood hazard.",
            "Data covered only by the installed regional extract; missing OSM data does not prove absence.",
        ],
    }


def readiness() -> dict[str, Any]:
    if not configured():
        return {"configured": False, "ready": False, "reason": "not_configured"}
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('statement_timeout', %s, TRUE)", (str(QUERY_TIMEOUT_MS),))
            cur.execute(
                "SELECT snapshot_at_utc, row_count FROM planexus_osm.snapshot "
                "WHERE snapshot_id=1 AND completed=TRUE")
            row = cur.fetchone()
            if not row or int(row[1]) <= 0:
                return {"configured": True, "ready": False, "reason": "no_verified_snapshot"}
            return {"configured": True, "ready": True,
                    "dataset_timestamp_utc": row[0].isoformat(),
                    "imported_feature_count": int(row[1])}
    except (psycopg.Error, ValueError, OSError):
        return {"configured": True, "ready": False, "reason": "database_unavailable"}
