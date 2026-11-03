"""Real PostGIS + Fiona GeoPackage integration check (local CI only).

No mocks, real spatial index and DB. Fixture is deliberately synthetic and
must never be shown as a real Malaysian street/facility inventory.
"""
from __future__ import annotations

from pathlib import Path
import os
import tempfile

import fiona
from fiona.crs import CRS
from shapely.geometry import Point, LineString, mapping

from app.osm_import import import_snapshot
from app.postgis_context import fetch_postgis_context, readiness
from app.site_context import fetch_context, geometry_digest

SITE={"type":"Polygon","coordinates":[[
    [101.073,4.663],[101.078,4.663],[101.078,4.668],
    [101.073,4.668],[101.073,4.663]
]]}


def write_fixture(file:Path, *, valid:bool=True)->None:
    with fiona.open(file,"w",driver="GPKG",layer="gis_osm_pois_free_1",
                    crs=CRS.from_epsg(4326),
                    schema={"geometry":"Point","properties":{
                        "osm_id":"str","fclass":"str","name":"str"}}) as dst:
        dst.write({"geometry":mapping(Point(101.075,4.665)),
                   "properties":{"osm_id":"9101",
                     "fclass":"school" if valid else "not_supported",
                     "name":"Synthetic QA school"}})
    if valid:
        with fiona.open(file,"w",driver="GPKG",layer="gis_osm_roads_free_1",
                        crs=CRS.from_epsg(4326),
                        schema={"geometry":"LineString","properties":{
                            "osm_id":"str","fclass":"str","name":"str"}}) as dst:
            dst.write({"geometry":mapping(LineString([
                (101.0735,4.6645),(101.076,4.6655)])),
                "properties":{"osm_id":"9202","fclass":"residential",
                              "name":"Synthetic QA street"}})


def main()->None:
    assert os.getenv("PLANEXUS_OSM_POSTGIS_DSN"),"Need isolated CI PostGIS DSN"
    with tempfile.TemporaryDirectory() as tmp:
        source=Path(tmp)/"regional-qa.gpkg"
        write_fixture(source)
        assert import_snapshot(source,"2026-11-01")==2
        state=readiness()
        assert state["configured"] and state["ready"] and state["imported_feature_count"]==2,state
        result=fetch_context(SITE,radius_m=1500)
        assert result["source_id"]=="geofabrik-osm-postgis-snapshot",result
        assert result["counts"]["education"]==1,result
        assert result["counts"]["roads"]==1,result
        assert len(result["named_places"])==1,result
        assert result["named_places"][0]["name"]=="Synthetic QA school"
        assert result["dataset_timestamp_utc"].startswith("2026-11-01")
        assert result["geometry_sha256"]==geometry_digest(SITE)
        # A second import cannot duplicate features or collide on index names.
        assert import_snapshot(source,"2026-11-02")==2
        newer=fetch_postgis_context(
            SITE,radius_m=1500,geometry_sha256=geometry_digest(SITE))
        assert newer["dataset_timestamp_utc"].startswith("2026-11-02")
        assert newer["returned_feature_count"]==2
        invalid=Path(tmp)/"invalid-qa.gpkg"
        write_fixture(invalid,valid=False)
        try:
            import_snapshot(invalid,"2026-11-03")
        except ValueError as exc:
            assert "Zero valid recognised" in str(exc),exc
        else:
            raise AssertionError("Invalid replacement must fail")
        restored=fetch_context(SITE,radius_m=1500)
        assert restored["dataset_timestamp_utc"].startswith("2026-11-02")
        assert restored["counts"]["education"]==1
        print("PASS: atomic replacement, geodesic site search, source provenance and recovery.")


if __name__=="__main__":
    main()
