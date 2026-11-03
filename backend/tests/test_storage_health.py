"""Volume enforcement, truthful health and atomic GIS report persistence."""
from __future__ import annotations

import json
import pathlib
import pytest
from tests.client import TestClient

import app.main as main
from app.storage_health import check_storage


def test_health_probes_local_directory_without_claiming_cloud_persistence(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "development")
    monkeypatch.delenv("PLANEXUS_REQUIRE_PERSISTENT_VOLUME", raising=False)
    with TestClient(main.app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        health = response.json()
        assert health["status"] == "ok"
        assert health["persistent"] is False
        assert health["public_multiuser_ready"] is False
    assert not list((tmp_path / "development").glob(".planexus-write-check-*"))


def test_require_volume_fails_closed_and_never_creates_ephemeral_data(monkeypatch, tmp_path):
    path = tmp_path / "not-mounted"
    monkeypatch.setattr(main, "DATA_DIR", path)
    monkeypatch.setenv("PLANEXUS_REQUIRE_PERSISTENT_VOLUME", "1")
    with TestClient(main.app) as client:
        status = client.get("/api/health")
        assert status.status_code == 503
        assert status.json()["storage"] == "required_volume_missing"
        post = client.post("/api/projects", json={"name": "DO NOT WRITE"})
        assert post.status_code == 503
        assert "mounted" in post.json()["detail"]
    assert not path.exists()


def test_mount_requirement_with_mock_mount_still_checks_real_io(monkeypatch, tmp_path):
    monkeypatch.setenv("PLANEXUS_REQUIRE_PERSISTENT_VOLUME", "1")
    monkeypatch.setattr(pathlib.Path, "is_mount", lambda self: True)
    outcome = check_storage(tmp_path / "durable")
    assert outcome["ready"] is True and outcome["persistent"] is True
    assert outcome["type"] == "mounted_volume"


def test_corrupted_existing_sqlite_blocks_writes(monkeypatch, tmp_path):
    data = tmp_path / "damaged"
    data.mkdir()
    (data / "planexus-workspace.sqlite3").write_bytes(b"not a database")
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.delenv("PLANEXUS_REQUIRE_PERSISTENT_VOLUME", raising=False)
    with TestClient(main.app) as client:
        result = client.get("/api/health")
        assert result.status_code == 503
        assert result.json()["status"] == "error"
        assert client.post("/api/projects", json={"name": "Blocked"}).status_code == 503


def test_report_atomic_replace_retains_previous_good_report(monkeypatch, tmp_path):
    directory = tmp_path / "jobs" / "fixture"
    report = {"analysis_id": "fixture", "slope_geojson": {"type": "FeatureCollection", "features": []}}
    main.save_report(directory, report)
    original = (directory / "result.json").read_bytes()
    def broken_replace(source, target):
        raise OSError("synthetic atomic rename failure")
    monkeypatch.setattr(main.os, "replace", broken_replace)
    with pytest.raises(OSError, match="synthetic"):
        main.save_report(directory, {"analysis_id": "fixture", "changed": True})
    assert (directory / "result.json").read_bytes() == original
    assert not list(directory.glob(".result-*.tmp"))


def test_saved_report_restores_real_field_names_for_both_map_layers(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    analysis_id = "59c1440c-624a-4731-bd88-6d17a6638256"
    feature={"type":"Feature","properties":{"class_id":1},"geometry":{
        "type":"Polygon","coordinates":[[[101,4],[101.001,4],[101.001,4.001],[101,4]]]}}
    report = {"analysis_id": analysis_id,
              "slope_geojson":{"type":"FeatureCollection","features":[feature]},
              "elevation_geojson":{"type":"FeatureCollection","features":[feature]}}
    directory = main.job_dir(analysis_id)
    main.save_report(directory, report)
    with TestClient(main.app) as client:
        actual = client.get(f"/api/analyses/{analysis_id}")
    assert actual.status_code == 200
    assert actual.json()["slope_geojson"]["features"]
    assert actual.json()["elevation_geojson"]["features"]
    assert json.loads((directory/"result.json").read_text()) == report



def test_corrupted_or_swapped_gis_report_is_refused_not_rendered(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    aid = "59c1440c-624a-4731-bd88-6d17a6638256"
    directory = main.job_dir(aid)
    directory.mkdir(parents=True)
    report = directory / "result.json"
    report.write_text('{"analysis_id":"00000000-0000-4000-8000-000000000000"}')
    with TestClient(main.app) as client:
        wrong = client.get(f"/api/analyses/{aid}")
        assert wrong.status_code == 503
        assert "tidak sepadan" in wrong.json()["detail"]
        report.write_text("{BROKEN JSON")
        corrupted = client.get(f"/api/analyses/{aid}")
        assert corrupted.status_code == 503
        assert "integriti storan" in corrupted.json()["detail"]
