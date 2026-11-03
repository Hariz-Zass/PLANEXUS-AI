"""Operator-only atomic import of licensed Geofabrik GeoPackage layers to PostGIS.

Run only from an authenticated server/CLI, not from a public API endpoint.
Import runs in a single PostgreSQL transaction, keeping the last complete
snapshot available if an update crashes or the extract is malformed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path

import fiona
import psycopg
from pyproj import CRS, Transformer
from shapely.geometry import shape
from shapely.ops import transform as transform_geom

from .geofabrik_context import _category, _layer_relevant


def _sources(path: Path) -> list[Path]:
    path=path.expanduser().resolve()
    result=([path] if path.is_file() and path.suffix.lower()==".gpkg"
            else sorted(path.glob("*.gpkg")) if path.is_dir() else [])
    if not result or len(result)>40:
        raise ValueError("Specify a Geofabrik GeoPackage or a folder of up to 40 GPKG files.")
    return result


def import_snapshot(source: Path, snapshot_date: str, *, dsn: str | None=None) -> int:
    raw=snapshot_date.replace("Z","+00:00")
    try:
        date=datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("Provide an actual ISO-8601 Geofabrik extract date.") from exc
    if date.tzinfo is None:
        date=date.replace(tzinfo=timezone.utc)
    date=date.astimezone(timezone.utc)
    if date > datetime.now(timezone.utc):
        raise ValueError("Extract date cannot lie in the future.")
    dsn=(dsn if dsn is not None else os.getenv("PLANEXUS_OSM_POSTGIS_DSN","")).strip()
    if not dsn:
        raise ValueError("Missing backend-only PLANEXUS_OSM_POSTGIS_DSN.")
    sources=_sources(source)
    candidates=[(file,layer) for file in sources
                for layer in fiona.listlayers(str(file)) if _layer_relevant(layer)]
    if not candidates:
        raise ValueError("No recognised Geofabrik free OSM layers found.")
    total=0
    with psycopg.connect(dsn, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            cur.execute("CREATE SCHEMA IF NOT EXISTS planexus_osm")
            # Only one operator import at a time.
            cur.execute("SELECT pg_advisory_xact_lock(72521063)")
            cur.execute("DROP TABLE IF EXISTS planexus_osm.features_next")
            cur.execute(
                "CREATE TABLE planexus_osm.features_next ("
                "category TEXT NOT NULL, osm_ref TEXT NOT NULL, "
                "name TEXT, geom geometry(Geometry,4326) NOT NULL)")
            for file,layer in candidates:
                with fiona.open(str(file),layer=layer) as src:
                    if not src.crs:
                        raise ValueError("Layer "+layer+" has no coordinate reference system.")
                    crs=CRS.from_user_input(src.crs)
                    reproj=(None if crs==CRS.from_epsg(4326) else
                            Transformer.from_crs(crs,"EPSG:4326",always_xy=True).transform)
                    records=[]
                    for feature in src:
                        props=dict(feature.get("properties") or {})
                        category=_category(layer,str(props.get("fclass") or ""))
                        if category is None or not feature.get("geometry"):
                            continue
                        geom=shape(feature["geometry"])
                        if reproj is not None:
                            geom=transform_geom(reproj,geom)
                        if geom.is_empty or not geom.is_valid or not geom.bounds:
                            continue
                        minx,miny,maxx,maxy=geom.bounds
                        if not (-180<=minx<=180 and -180<=maxx<=180 and
                                -90<=miny<=90 and -90<=maxy<=90):
                            continue
                        fid=props.get("osm_id") or feature.get("id")
                        name=props.get("name")
                        records.append((category,f"{layer}:{fid}",
                                        (name.strip()[:120] if isinstance(name,str) and name.strip() else None),
                                        geom.wkb))
                        if len(records)>=1000:
                            cur.executemany(
                                "INSERT INTO planexus_osm.features_next "
                                "(category,osm_ref,name,geom) "
                                "VALUES (%s,%s,%s,ST_GeomFromWKB(%s,4326))",records)
                            total+=len(records)
                            records.clear()
                    if records:
                        cur.executemany(
                            "INSERT INTO planexus_osm.features_next "
                            "(category,osm_ref,name,geom) "
                            "VALUES (%s,%s,%s,ST_GeomFromWKB(%s,4326))",records)
                        total+=len(records)
            if not total:
                raise ValueError("Zero valid recognised OSM features; prior snapshot retained.")
            cur.execute(
                "CREATE TABLE IF NOT EXISTS planexus_osm.snapshot ("
                "snapshot_id INTEGER PRIMARY KEY, "
                "snapshot_at_utc TIMESTAMPTZ NOT NULL, "
                "imported_at_utc TIMESTAMPTZ NOT NULL, "
                "row_count BIGINT NOT NULL, completed BOOLEAN NOT NULL, "
                "bounds geometry(Polygon,4326) NOT NULL)")
            # Swap tables inside the SAME transaction: existing readers either
            # see the complete previous version or the complete replacement.
            cur.execute("DROP TABLE IF EXISTS planexus_osm.features_previous")
            cur.execute("ALTER TABLE IF EXISTS planexus_osm.features RENAME TO features_previous")
            cur.execute("ALTER TABLE planexus_osm.features_next RENAME TO features")
            cur.execute("DROP TABLE IF EXISTS planexus_osm.features_previous")
            cur.execute(
                "CREATE INDEX planexus_osm_geom_idx "
                "ON planexus_osm.features USING gist (geom)")
            cur.execute(
                "CREATE INDEX planexus_osm_geog_idx "
                "ON planexus_osm.features USING gist ((geom::geography))")
            cur.execute(
                "CREATE INDEX planexus_osm_category_idx "
                "ON planexus_osm.features (category)")
            cur.execute("ANALYZE planexus_osm.features")
            cur.execute(
                "INSERT INTO planexus_osm.snapshot "
                "(snapshot_id,snapshot_at_utc,imported_at_utc,row_count,completed,bounds) "
                "SELECT 1,%s,now(),%s,TRUE,ST_Envelope(ST_Extent(geom)) "
                "FROM planexus_osm.features "
                "ON CONFLICT (snapshot_id) DO UPDATE SET "
                "snapshot_at_utc=EXCLUDED.snapshot_at_utc, "
                "imported_at_utc=EXCLUDED.imported_at_utc, "
                "row_count=EXCLUDED.row_count, completed=TRUE, "
                "bounds=EXCLUDED.bounds",
                (date,total))
    return total


def main() -> None:
    cli=argparse.ArgumentParser(description="Atomically refresh private OSM PostGIS snapshot.")
    cli.add_argument("--source",required=True,help="GPKG file or folder with Geofabrik free GIS layers")
    cli.add_argument("--snapshot-date",required=True,help="Real extract date (YYYY-MM-DD or ISO8601)")
    args=cli.parse_args()
    count=import_snapshot(Path(args.source),args.snapshot_date)
    print(f"Imported {count} real open-data features; snapshot completed and indexed.")


if __name__=="__main__":
    main()
