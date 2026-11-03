"""One REAL local API round-trip across planner modules, with synthetic raster.

This test is intentionally not evidence about any real Malaysian site.
It verifies the chain Project -> Boundary -> DTM -> Slope/Elevation -> GPP
catalog -> Proposal -> Layout -> persisted restore. No external internet.
"""
from __future__ import annotations

import json

import numpy as np
import rasterio
from tests.client import TestClient
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import transform

import app.main as main


def test_complete_single_project_gis_workflow_survives_restart(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "gis-store")
    monkeypatch.delenv("PLANEXUS_REQUIRE_PERSISTENT_VOLUME", raising=False)
    source = tmp_path / "synthetic-dtm.tif"
    n = 120
    raster = np.repeat(np.arange(n, dtype="float32")[None, :], n, axis=0)
    left, top = 720000.0, 520000.0
    with rasterio.open(
        source, "w", driver="GTiff", width=n, height=n, count=1,
        crs="EPSG:32647", dtype="float32", nodata=-9999.0,
        transform=from_origin(left, top, 10, 10)
    ) as dst:
        dst.write(raster, 1)
    utm_polygon = Polygon([
        (left+200, top-200), (left+1000, top-200),
        (left+1000, top-1000), (left+200, top-1000)
    ])
    transform_back = Transformer.from_crs("EPSG:32647", "EPSG:4326", always_xy=True)
    geometry = mapping(transform(transform_back.transform, utm_polygon))
    with TestClient(main.app) as client:
        assert client.get("/api/health").status_code == 200
        created = client.post("/api/projects", json={"name": "CI SITE - synthetic not real"})
        assert created.status_code == 201, created.text
        pid = created.json()["id"]
        assert created.json()["geometry"] is None
        saved_boundary = client.patch(
            f"/api/projects/{pid}",
            json={"expected_revision": 1, "geometry": geometry}
        )
        assert saved_boundary.status_code == 200, saved_boundary.text
        assert saved_boundary.json()["has_site"]
        assert saved_boundary.json()["revision"] == 2

        with source.open("rb") as handle:
            upload = client.post(
                "/api/terrain/upload",
                data={
                    "project_id": pid, "geometry": json.dumps(geometry),
                    "source_name": "Synthetic elevation fixture NOT field verified",
                    "height_model": "DTM", "vertical_unit": "metres",
                    "vertical_datum": "synthetic CI test"
                },
                files={"file": ("synthetic.tif", handle, "image/tiff")}
            )
        assert upload.status_code == 200, upload.text
        report = upload.json()
        aid = report["analysis_id"]
        assert report["slope_geojson"]["features"], "Raster should render true slope shapes"
        assert report["elevation_geojson"]["features"], "Raster should render true elevation shapes"
        assert report["metrics"]["valid_slope_pixels"] > 0
        assert report["metrics"]["valid_elevation_pixels"] > 0

        gpp = client.get("/api/policy/catalog")
        assert gpp.status_code == 200, gpp.text
        assert gpp.json()["sources"], "GPP registry must be obtainable via live API"

        scenario = {
            "name": "Synthetic layout quantity only", "development_type": "terrace_housing",
            "units": 15, "lot_width_m": 6.096, "lot_depth_m": 21.336,
            "roads_pct": 20, "open_space_pct": 10, "facilities_pct": 5,
            "other_reserve_pct": 5
        }
        proposal = client.post(f"/api/projects/{pid}/proposals", json=scenario)
        assert proposal.status_code == 201, proposal.text
        proposal_id = proposal.json()["id"]
        assert proposal.json()["result"]["gross_site_density_units_per_ha"] > 0
        assert proposal.json()["result"]["not_approval"] is True

        xmin, ymin, xmax, ymax = shape(geometry).bounds
        # One simple road strictly inside the project polygon.
        centre_x = (xmin + xmax) / 2
        road = {"type": "LineString", "coordinates": [
            [centre_x, ymin + (ymax-ymin)*0.20],
            [centre_x, ymin + (ymax-ymin)*0.80]
        ]}
        layout_input = {
            "name": "Real spatial projection on synthetic plot",
            "road_centerlines": [road],
            "assumed_road_width_m": 15.24,
            "front_road_buffer_m": 0,
            "perimeter_offset_m": 0,
            "policy_profile": "none"
        }
        preview = client.post(f"/api/projects/{pid}/layout/preview", json=layout_input)
        assert preview.status_code == 200, preview.text
        assert preview.json()["preview"]["road_corridor_ha"] > 0
        assert "network" in preview.json()["preview"]
        saved_layout = client.put(f"/api/projects/{pid}/layout", json={
            "expected_revision": 0, "inputs": layout_input
        })
        assert saved_layout.status_code == 200, saved_layout.text
        assert saved_layout.json()["revision"] == 1

    # Fresh client reflects a process restart using the same durable directory.
    with TestClient(main.app) as reopened:
        project = reopened.get(f"/api/projects/{pid}")
        assert project.status_code == 200
        details = project.json()
        assert details["active_analysis_id"] == aid
        assert details["has_site"]
        assert len(details["analyses"]) == 1
        saved_report = reopened.get(f"/api/analyses/{aid}")
        assert saved_report.status_code == 200
        assert saved_report.json()["slope_geojson"]["features"]
        assert saved_report.json()["elevation_geojson"]["features"]
        prior_layout = reopened.get(f"/api/projects/{pid}/layout").json()
        assert prior_layout["exists"] is True
        assert prior_layout["inputs"]["road_centerlines"] == [road]
        assert prior_layout["preview"]["road_corridor_ha"] > 0
        scenarios = reopened.get(f"/api/projects/{pid}/proposals").json()["proposals"]
        assert any(item["id"] == proposal_id for item in scenarios)


    # BACKUP/RESTORE REHEARSAL: snapshot an actual GeoTIFF and ALL project
    # modules from SQLite; restore into a new directory, then reopen with API.
    # This simulates replacing the data volume rather than merely restarting
    # TestClient on its original filesystem.
    from app.backup import create_backup
    from app.backup_restore import verify_backup, restore_backup

    backup = create_backup(tmp_path / "gis-store", tmp_path / "safe-archives")
    proof = verify_backup(backup)
    assert proof["analysis_count"] == 1
    assert proof["layout_count"] == 1
    assert proof["proposal_count"] == 1
    destination = tmp_path / "restored-new-volume"
    restore_backup(backup, destination)
    restored_tif = destination / "jobs" / aid / "uploaded_source.tif"
    assert restored_tif.is_file()
    with rasterio.open(restored_tif) as raster:
        assert raster.crs.to_epsg() == 32647
        assert raster.width == n and raster.count == 1

    monkeypatch.setattr(main, "DATA_DIR", destination)
    with TestClient(main.app) as restored:
        reproject = restored.get(f"/api/projects/{pid}")
        assert reproject.status_code == 200
        assert reproject.json()["active_analysis_id"] == aid
        assert shape(reproject.json()["geometry"]).equals(shape(geometry))
        reanalysis = restored.get(f"/api/analyses/{aid}").json()
        assert reanalysis["slope_geojson"]["features"]
        assert reanalysis["elevation_geojson"]["features"]
        assert reanalysis["contours_geojson"]["features"]
        saved_scenarios = restored.get(f"/api/projects/{pid}/proposals").json()
        assert any(item["id"] == proposal_id for item in saved_scenarios["proposals"])
        persisted_layout = restored.get(f"/api/projects/{pid}/layout").json()
        assert persisted_layout["exists"] is True
        assert persisted_layout["inputs"]["road_centerlines"] == [road]
