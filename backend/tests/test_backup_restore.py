"""B3.1 backup/restore: project, raster, scenario, layout, tampering and safety."""
from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
from tests.client import TestClient
from shapely.geometry import Polygon, mapping

import app.main as gis
from app.backup import create_backup
from app.backup_restore import restore_backup, verify_backup
from app.project_store import create_project


SITE={"type":"Polygon","coordinates":[[
    [101.070,4.660],[101.080,4.660],[101.080,4.670],[101.070,4.670],[101.070,4.660]
]]}


def test_restore_all_sqlite_scenarios_layout_and_raster_evidence(monkeypatch, tmp_path):
    data=tmp_path/"source"
    monkeypatch.setattr(gis, "DATA_DIR", data)
    with TestClient(gis.app) as api:
        a=api.post("/api/projects",json={"name":"Site A","geometry":SITE})
        assert a.status_code==201,a.text
        pid=a.json()["id"]
        b=api.post("/api/projects",json={"name":"Site B"})
        assert b.status_code==201,b.text
        other_id=b.json()["id"]

        # Include a report linked to the actual site, plus the source raster
        # it was made from. The test bytes are not a real land DEM.
        import uuid
        from app.project_store import attach_analysis
        aid=str(uuid.uuid4())
        folder=data/"jobs"/aid
        folder.mkdir(parents=True)
        (folder/"source_clipped.tif").write_bytes(b"SYNTHETIC TEST RASTER BYTES")
        report={"analysis_id":aid,"created_at_utc":"2026-11-03T00:00:00Z",
            "geometry":SITE,"source":{"name":"SYNTHETIC TEST - NOT VERIFIED"},
            "metrics":{"site_area_ha":1.0},
            "slope_geojson":{"type":"FeatureCollection","features":[1]},
            "elevation_geojson":{"type":"FeatureCollection","features":[2]}}
        gis.save_report(folder,report)
        attach_analysis(data,pid,report)
        scenario={"name":"Reference terrace development","development_type":"terrace_housing",
            "units":10,"lot_width_m":6.096,"lot_depth_m":21.336,
            "roads_pct":20,"open_space_pct":10,"facilities_pct":5,"other_reserve_pct":5}
        proposal=api.post(f"/api/projects/{pid}/proposals",json=scenario)
        assert proposal.status_code==201,proposal.text
        layout={"name":"Road A","road_centerlines":[],"assumed_road_width_m":15.24,
                "front_road_buffer_m":0,"perimeter_offset_m":0,"policy_profile":"none"}
        saved=api.put(f"/api/projects/{pid}/layout",json={
            "expected_revision":0,"inputs":layout})
        assert saved.status_code==200,saved.text

    archive=create_backup(data,tmp_path/"archives")
    verified=verify_backup(archive)
    assert verified["verified"] and verified["sha256_verified"]
    assert verified["project_count"]==2
    assert verified["analysis_count"]==1
    assert verified["proposal_count"]==1
    assert verified["layout_count"]==1

    destination=tmp_path/"new-volume"
    result=restore_backup(archive,destination)
    assert result["restored"]
    assert (destination/"jobs"/aid/"source_clipped.tif").read_bytes()==b"SYNTHETIC TEST RASTER BYTES"
    monkeypatch.setattr(gis,"DATA_DIR",destination)
    with TestClient(gis.app) as restarted:
        p=restarted.get(f"/api/projects/{pid}")
        assert p.status_code==200,p.text
        assert p.json()["active_analysis_id"]==aid
        assert p.json()["geometry"]==SITE
        assert restarted.get(f"/api/projects/{other_id}").status_code==200
        assert restarted.get(f"/api/analyses/{aid}").json()["elevation_geojson"]["features"]
        assert len(restarted.get(f"/api/projects/{pid}/proposals").json()["proposals"])==1
        assert restarted.get(f"/api/projects/{pid}/layout").json()["exists"] is True
        # An empty second project has no layout canvas until a boundary is saved.
        assert restarted.get(f"/api/projects/{other_id}/layout").status_code == 422


def test_refuse_restore_over_existing_data_even_when_empty(tmp_path):
    data=tmp_path/"data"
    create_project(data,"Project A")
    archive=create_backup(data,tmp_path/"archives")
    destination=tmp_path/"do-not-overwrite"
    destination.mkdir()
    (destination/"important.txt").write_text("KEEP")
    with pytest.raises(RuntimeError,match="must not exist"):
        restore_backup(archive,destination)
    assert (destination/"important.txt").read_text()=="KEEP"


def test_refuse_modified_archive_digest_before_restoring(tmp_path):
    data=tmp_path/"data"
    create_project(data,"Project A")
    original=create_backup(data,tmp_path/"archives")
    altered=tmp_path/"tampered.zip"
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(altered,"w") as dst:
        for name in src.namelist():
            body=src.read(name)
            if name=="planexus-workspace.sqlite3":
                body=b"SQLITE FILE ALTERED"
            dst.writestr(name,body)
    with pytest.raises(RuntimeError,match="SHA-256"):
        verify_backup(altered)
    with pytest.raises(RuntimeError,match="SHA-256"):
        restore_backup(altered,tmp_path/"restore-should-not-appear")
    assert not (tmp_path/"restore-should-not-appear").exists()


def test_refuse_zip_slip_symlink_and_duplicate_names(tmp_path):
    data=tmp_path/"data"
    create_project(data,"Project A")
    original=create_backup(data,tmp_path/"archives")
    for malicious in ("../pwned.txt","jobs/../pwned.json","jobs\\evil.json","/absolute"):
        tampered=tmp_path/("attack-"+str(abs(hash(malicious)))+".zip")
        with zipfile.ZipFile(original) as src, zipfile.ZipFile(tampered,"w") as dst:
            for name in src.namelist():
                dst.writestr(name,src.read(name))
            dst.writestr(malicious,b"evil")
        with pytest.raises(RuntimeError,match="unsafe archive member"):
            verify_backup(tampered)
    duplicate=tmp_path/"dupe.zip"
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(duplicate,"w") as dst:
        for name in src.namelist():
            dst.writestr(name,src.read(name))
        dst.writestr("planexus-workspace.sqlite3",b"duplicate DB")
    with pytest.raises(RuntimeError,match="Duplicate archive"):
        verify_backup(duplicate)


def test_reject_backup_if_project_links_missing_gis_report(tmp_path):
    data=tmp_path/"data"
    project=create_project(data,"Project A",geometry=SITE)
    aid="f0000000-0000-4000-8000-000000000001"
    with sqlite3.connect(data/"planexus-workspace.sqlite3") as conn:
        conn.execute("INSERT INTO project_analyses(project_id,analysis_id,created_at_utc,source_name,site_area_ha) VALUES(?,?,?,?,?)",
                     (project["id"],aid,"2026-11-03T00:00:00Z","MISSING",1.0))
        conn.execute("UPDATE projects SET active_analysis_id=? WHERE id=?",
                     (aid,project["id"]))
    with pytest.raises(RuntimeError,match="Linked GIS report missing"):
        create_backup(data,tmp_path/"archives")
    assert not list((tmp_path/"archives").glob("*.zip"))
