"""Spatial layout preview regression: projected buffers, GIS provenance and SQLite isolation."""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from shapely.geometry import Polygon, shape

import app.main as main
from app.layout_engine import LayoutInput, screen_layout
from app.project_store import attach_analysis

SITE={
    "type":"Polygon",
    "coordinates":[[[101.0700,4.6600],[101.0730,4.6600],
                    [101.0730,4.6630],[101.0700,4.6630],[101.0700,4.6600]]]
}
SECOND={
    "type":"Polygon",
    "coordinates":[[[101.10,4.68],[101.103,4.68],
                    [101.103,4.683],[101.10,4.683],[101.10,4.68]]]
}
ROAD={
    "type":"LineString",
    "coordinates":[[101.0715,4.6604],[101.0715,4.6626]]
}
OTHER_ROAD={
    "type":"LineString",
    "coordinates":[[101.0704,4.6615],[101.0726,4.6615]]
}


def _input(**parts):
    return LayoutInput.model_validate({"name":"Layout A for geometry test",
        "road_centerlines":[ROAD],"assumed_road_width_m":15.24,
        "front_road_buffer_m":6.096,"perimeter_offset_m":3.0,
        **parts})


def _report(site=SITE,quality:dict|None=None,low:dict|None=None):
    return {
        "analysis_id":str(uuid.uuid4()),
        "geometry":site,
        "created_at_utc":"2026-11-02T11:00:00Z",
        "source":{"name":"Synthetic DTM fixture, not real evidence"},
        "metrics":{"site_area_ha":11},
        "suitability":{
            "class_overlay_truncated":False,"coverage_of_site_pct_est":99.5,
            "assessed_pixels":500,"source_resolution_m":10,
            "area_exceeds_site_due_to_pixelization":False,
            **(quality or {}),
        },
        "suitability_geojson":{
            "type":"FeatureCollection",
            "features":[{"type":"Feature","properties":{"class_id":1},
                         "geometry":low or site}],
        },
    }


def test_buffers_use_projected_meters_and_deduplicate_overlaps():
    result=screen_layout(SITE,_input())
    assert result["terrain_status"]=="no_active_suitability"
    assert result["lower_slope_remaining_ha"] is None
    assert result["road_count"]==1
    assert 200<result["road_centerline_length_m"]<300
    assert result["road_corridor_ha"]>0.25
    assert result["road_front_margin_ha"]>0.05
    assert result["perimeter_exclusion_ha"]>0.1
    assert result["gross_unencumbered_ha"]<result["site_area_ha"]
    assert result["gross_unencumbered_ha"]+result["combined_exclusions_ha"]==pytest.approx(
        result["site_area_ha"],abs=2e-5
    )
    # Rounded hectare fields can differ by 0.00001. The true geometry is
    # unioned before calculating its area; do not assert overlap on sketches
    # where road buffers and the site edge band are almost disjoint.
    assert result["combined_exclusions_ha"]<=(
        result["road_corridor_ha"]+result["road_front_margin_ha"]+
        result["perimeter_exclusion_ha"]+0.00002
    )
    assert result["layers"]["road_corridor"]["features"]
    assert result["layers"]["road_front_margin"]["features"]
    for key in ("gross_remaining","road_corridor","road_front_margin","perimeter_exclusion"):
        for feature in result["layers"][key]["features"]:
            assert feature["properties"]["screening_only"] is True
    assert any("not physically" in warning.lower() or "not a surveyed" in warning.lower()
               for warning in result["warnings"])


def test_two_crossing_roads_union_and_zero_buffer_are_not_double_counted():
    baseline=screen_layout(SITE,LayoutInput(name="No site roads"))
    assert baseline["road_corridor_ha"]==0
    assert baseline["road_front_margin_ha"]==0
    assert baseline["gross_unencumbered_ha"]==baseline["site_area_ha"]
    assert baseline["road_count"]==0
    single=screen_layout(SITE,_input(front_road_buffer_m=0,perimeter_offset_m=0))
    crossing=screen_layout(SITE,_input(
        road_centerlines=[ROAD,OTHER_ROAD],front_road_buffer_m=0,
        perimeter_offset_m=0
    ))
    assert crossing["road_corridor_ha"]>single["road_corridor_ha"]
    assert crossing["road_corridor_ha"]<single["road_corridor_ha"]*2.1
    assert crossing["gross_unencumbered_ha"]<single["gross_unencumbered_ha"]
    assert crossing["road_front_margin_ha"]==0
    assert crossing["combined_exclusions_ha"]==crossing["road_corridor_ha"]


def test_valid_low_slope_polygons_are_clipped_and_candidate_is_not_permitted_land():
    report=_report()
    no_roads=screen_layout(SITE,LayoutInput(name="Preliminary zero road"),report)
    with_roads=screen_layout(SITE,_input(),report)
    assert no_roads["terrain_status"]=="low_slope_vector_approximation"
    assert no_roads["quality_status"]=="preliminary_raster"
    assert no_roads["lower_slope_remaining_ha"]==pytest.approx(no_roads["site_area_ha"],abs=.001)
    assert with_roads["lower_slope_remaining_ha"]<no_roads["lower_slope_remaining_ha"]
    assert with_roads["lower_slope_remaining_ha"]<=with_roads["gross_unencumbered_ha"]
    assert with_roads["lower_patch_count"]>=1
    assert with_roads["largest_contiguous_lower_patch_ha"]<=with_roads["lower_slope_remaining_ha"]
    assert with_roads["layers"]["lower_slope_remaining"]["features"]
    assert any("not a contiguous buildable footprint" in w.lower() for w in with_roads["warnings"])


def test_report_from_another_site_or_truncated_gis_cannot_become_buildable_area():
    mismatched=screen_layout(SITE,_input(),_report(site=SECOND))
    assert mismatched["terrain_status"]=="report_site_mismatch"
    assert mismatched["lower_slope_remaining_ha"] is None
    truncated=screen_layout(SITE,_input(),_report(quality={"class_overlay_truncated":True}))
    assert truncated["terrain_status"]=="incomplete_vector_overlay"
    assert truncated["lower_slope_remaining_ha"] is None
    invalid=screen_layout(SITE,_input(),_report(quality={"coverage_of_site_pct_est":80,
        "source_resolution_m":90,"assessed_pixels":40}))
    assert invalid["quality_status"]=="quality_limited"
    assert invalid["lower_slope_remaining_ha"] is not None
    assert any("confidence" in w.lower() for w in invalid["warnings"])
    high_only=_report()
    high_only["suitability_geojson"]["features"][0]["properties"]["class_id"]=3
    result=screen_layout(SITE,_input(),high_only)
    assert result["lower_slope_remaining_ha"]==0
    assert result["lower_patch_count"]==0


@pytest.mark.parametrize("payload",[
    {"road_centerlines":[{"type":"Polygon","coordinates":[]}]},
    {"road_centerlines":[{"type":"LineString","coordinates":[[101,4]]}]},
    {"road_centerlines":[{"type":"LineString","coordinates":[[101,4],[101,float("nan")]]}]},
    {"road_centerlines":[{"type":"LineString","coordinates":[[101,4],[101,4]]}]},
    {"road_centerlines":[{"type":"LineString","coordinates":[[101,4],[101,4.1],[101,4.2]]*70}]},
    {"assumed_road_width_m":1},
    {"front_road_buffer_m":-1},
    {"perimeter_offset_m":1000},
    {"policy_profile":"perak_2023","perak_market_segment":"unknown"},
])
def test_invalid_geometry_widths_and_policy_inputs_rejected(payload):
    with pytest.raises(ValidationError):
        LayoutInput.model_validate({"name":"Invalid input",**payload})


def test_road_outside_polygon_rejected_even_if_valid_wgs84():
    outside={"type":"LineString","coordinates":[[101.079,4.6604],[101.079,4.6626]]}
    with pytest.raises(Exception,match="within the current site boundary"):
        screen_layout(SITE,_input(road_centerlines=[outside]))


def test_perak_checks_are_reference_only_and_unverified_not_road_measurements():
    result=screen_layout(SITE,_input(
        policy_profile="perak_2023",perak_market_segment="perak_middle",
        assumed_road_width_m=14,front_road_buffer_m=5
    ))
    checks={c["key"]:c for c in result["policy_checks"]}
    assert checks["perak_pr1_service_road_width"]["minimum_m"]==pytest.approx(15.24)
    assert checks["perak_pr1_service_road_width"]["result"]=="entered_value_below_minimum"
    assert checks["perak_pr1_front_setback_reference"]["minimum_m"]==pytest.approx(6.096)
    assert checks["perak_pr1_front_setback_reference"]["result"]=="entered_value_below_reference"
    assert all(c["verified_geometry"] is False and c["binding"] is False for c in checks.values())
    result2=screen_layout(SITE,_input(
        policy_profile="perak_2023",perak_market_segment="perak_low_cost",
        assumed_road_width_m=15.24,front_road_buffer_m=4.572
    ))
    checks={c["key"]:c for c in result2["policy_checks"]}
    assert checks["perak_pr1_front_setback_reference"]["minimum_m"]==pytest.approx(4.572)
    assert checks["perak_pr1_front_setback_reference"]["result"]=="entered_value_meets_reference"


def test_layout_api_maintains_project_isolation_and_revisions(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path)
    c=TestClient(main.app)
    a=c.post("/api/projects",json={"name":"Layout A","geometry":SITE}).json()
    b=c.post("/api/projects",json={"name":"Layout B","geometry":SECOND}).json()
    url=lambda pid:f"/api/projects/{pid}/layout"
    empty=c.get(url(a["id"]))
    assert empty.status_code==200,empty.text
    assert empty.json()["revision"]==0 and empty.json()["exists"] is False
    assert empty.json()["preview"]["terrain_status"]=="no_active_suitability"
    payload=_input().model_dump()
    first=c.post(url(a["id"])+"/preview",json=payload)
    assert first.status_code==200,first.text
    assert first.json()["saved"] is False
    assert c.get(url(a["id"])).json()["revision"]==0
    created=c.put(url(a["id"]),json={"expected_revision":0,"inputs":payload})
    assert created.status_code==200,created.text
    saved=created.json()
    assert saved["revision"]==1 and saved["exists"] is True
    assert saved["inputs"]["road_centerlines"]==[ROAD]
    assert saved["preview"]["road_corridor_ha"]>0
    assert c.get(url(b["id"])).json()["inputs"]["road_centerlines"]==[]
    with TestClient(main.app) as reopened:
        assert reopened.get(url(a["id"])).json()["inputs"]["road_centerlines"]==[ROAD]
    assert c.put(url(a["id"]),json={"expected_revision":0,"inputs":payload}).status_code==409
    updated=c.put(url(a["id"]),json={"expected_revision":1,
                                   "inputs":{**payload,"assumed_road_width_m":20}})
    assert updated.status_code==200,updated.text
    assert updated.json()["revision"]==2
    assert updated.json()["preview"]["road_corridor_ha"]>saved["preview"]["road_corridor_ha"]
    assert c.put(url(b["id"]),json={"expected_revision":0,"inputs":payload}).status_code==422
    assert c.put(url(a["id"]),json={"expected_revision":2,"inputs":{
        **payload,"road_centerlines":[{"type":"LineString","coordinates":[[101.08,4.661],[101.081,4.662]]}]
    }}).status_code==422
    assert c.delete(f"/api/projects/{a['id']}").status_code==204
    assert c.get(url(a["id"])).status_code==404


def test_saved_layout_is_not_silently_reused_after_site_or_dem_changes(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path)
    c=TestClient(main.app)
    project=c.post("/api/projects",json={"name":"Stale layout site","geometry":SITE}).json()
    url=f"/api/projects/{project['id']}/layout"
    before=c.put(url,json={"expected_revision":0,"inputs":_input().model_dump()})
    assert before.status_code==200,before.text
    first=_report()
    job=tmp_path/"jobs"/first["analysis_id"]
    job.mkdir(parents=True)
    (job/"result.json").write_text(json.dumps(first))
    attach_analysis(tmp_path,project["id"],first)
    changed=c.get(url).json()
    assert changed["site_changed"] is False
    assert changed["analysis_changed"] is True
    assert changed["preview"]["terrain_status"]=="analysis_changed_review_required"
    assert changed["preview"]["lower_slope_remaining_ha"] is None
    confirmed=c.put(url,json={"expected_revision":1,"inputs":_input().model_dump()})
    assert confirmed.status_code==200
    assert confirmed.json()["analysis_changed"] is False
    assert confirmed.json()["preview"]["lower_slope_remaining_ha"] is not None
    current=c.get("/api/projects/"+project["id"]).json()
    updated=c.patch("/api/projects/"+project["id"],json={
        "expected_revision":current["revision"],"geometry":SECOND
    })
    assert updated.status_code==200,updated.text
    stale=c.get(url).json()
    assert stale["site_changed"] is True
    assert stale["preview"] is None
    assert len(stale["inputs"]["road_centerlines"])==1
    rejected=c.put(url,json={"expected_revision":2,"inputs":_input().model_dump()})
    assert rejected.status_code==422
    fresh=c.put(url,json={"expected_revision":2,"inputs":_input(
        road_centerlines=[],front_road_buffer_m=0).model_dump()})
    assert fresh.status_code==200,fresh.text
    assert fresh.json()["site_changed"] is False


def test_no_project_site_rejected_and_layout_table_included_in_project_backup(monkeypatch,tmp_path):
    from app.backup import create_backup
    import zipfile
    import sqlite3

    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"data")
    c=TestClient(main.app)
    project=c.post("/api/projects",json={"name":"No Boundary"}).json()
    assert c.get(f"/api/projects/{project['id']}/layout").status_code==422
    assert c.post(f"/api/projects/{project['id']}/layout/preview",json=_input().model_dump()).status_code==422
    target=c.patch("/api/projects/"+project["id"],json={
        "expected_revision":1,"geometry":SITE
    }).json()
    assert target["has_site"]
    saved=c.put(f"/api/projects/{project['id']}/layout",json={
        "expected_revision":0,"inputs":_input().model_dump()
    })
    assert saved.status_code==200,saved.text
    zip_path=create_backup(tmp_path/"data",tmp_path/"archives")
    with zipfile.ZipFile(zip_path) as archive:
        database=tmp_path/"snapshot.sqlite3"
        database.write_bytes(archive.read("planexus-workspace.sqlite3"))
    with sqlite3.connect(database) as db:
        row=db.execute("SELECT project_id,revision FROM project_layouts").fetchone()
        assert row==(project["id"],1)
