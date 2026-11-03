import math
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi import HTTPException
from tests.client import TestClient
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import Polygon, mapping
from shapely.ops import transform

from app.geometry import area_km2, validate_site
from app.main import app
from app.sources import copernicus_tiles, tile_name
from app.terrain import analyze_terrain

client = TestClient(app)


def synthetic(tmp_path: Path):
    # 120 x 120 pixels, each 10m; z increases 1m per x cell => slope ~5.71 degrees.
    path = tmp_path / "test_surface.tif"
    array = np.repeat(np.arange(120, dtype="float32")[None, :] * 1.0, 120, axis=0)
    west, north = 720000, 520000
    with rasterio.open(path, "w", driver="GTiff", height=120, width=120, count=1, dtype="float32", crs="EPSG:32647", transform=from_origin(west, north, 10, 10), nodata=-9999) as dst:
        dst.write(array, 1)
    # Inner extent avoids nodata at edges and filters the 9px minimum.
    local = Polygon([(west+200, north-200), (west+1000, north-200), (west+1000, north-1000), (west+200, north-1000)])
    to_wgs = Transformer.from_crs("EPSG:32647", "EPSG:4326", always_xy=True)
    geo = mapping(transform(to_wgs.transform, local))
    return path, geo


def test_site_area_and_reject_invalid():
    geo = {"type":"Polygon", "coordinates":[[[101.07,4.66],[101.08,4.66],[101.08,4.67],[101.07,4.67],[101.07,4.66]]]}
    validated = validate_site(geo)
    assert 0.5 < area_km2(validated) < 2.0
    with pytest.raises(HTTPException):
        validate_site({"type":"Point", "coordinates":[101,4]})
    bowtie = {"type":"Polygon", "coordinates":[[[101,4],[101.01,4.01],[101,4.01],[101.01,4],[101,4]]]}
    with pytest.raises(HTTPException):
        validate_site(bowtie)


def test_tile_naming_and_crossing_boundary():
    assert tile_name(4, 101) == "Copernicus_DSM_COG_10_N04_00_E101_00_DEM"
    assert tile_name(-2, -73) == "Copernicus_DSM_COG_10_S02_00_W073_00_DEM"
    assert len(copernicus_tiles((101.07,4.66,101.08,4.67))) == 1
    assert len(copernicus_tiles((100.999,4.999,101.001,5.001))) == 4


def test_synthetic_slope_evidence(tmp_path):
    raster, geometry = synthetic(tmp_path)
    result = analyze_terrain(validate_site(geometry), raster, {"id":"user-upload", "name":"Synthetic test raster", "data_type":"DTM"}, "synthetic-id")
    m = result["metrics"]
    assert m["site_area_ha"] > 60
    assert 5.0 < m["slope_mean_deg"] < 6.3
    assert m["slope_classes"][0]["percent_of_valid_slope"] > 99
    assert m["valid_slope_pixels"] > 100
    assert result["slope_geojson"]["features"]
    assert "NOT" in result["assessment_scope"] or "no planning" in result["assessment_scope"]


def test_api_health_and_inspect():
    assert client.get("/api/health").json()["production_ready"] is False
    assert client.get("/api/sources").status_code == 200
    payload = {"geometry":{"type":"Polygon","coordinates":[[[101.07,4.66],[101.08,4.66],[101.08,4.67],[101.07,4.67],[101.07,4.66]]]}}
    response = client.post("/api/site/inspect", json=payload)
    assert response.status_code == 200
    assert response.json()["area_ha"] > 0


def test_upload_and_save_and_fallback(tmp_path):
    raster, geom = synthetic(tmp_path)
    import json
    project=client.post("/api/projects",json={"name":"Synthetic original raster test","geometry":geom}).json()
    with raster.open("rb") as f:
        response = client.post("/api/terrain/upload", data={"geometry":json.dumps(geom),"project_id":project["id"],"source_name":"Synthetic local validation","vertical_unit":"metres","height_model":"DTM"}, files={"file":("test.tif",f,"image/tiff")})
    assert response.status_code == 200, response.text
    analysis_id = response.json()["analysis_id"]
    assert client.get(f"/api/analyses/{analysis_id}").status_code == 200
    assert client.get("/api/analyses").json()["analyses"]
    assert client.get(f"/api/analyses/{analysis_id}/report.md").status_code == 200
    response = client.post("/api/copilot/assess", json={"analysis_id":analysis_id,"question":"Sesuai bina rumah teres?"})
    assert response.status_code == 200
    assert response.json()["mode"] in ("deterministic_evidence_summary","llm_grounded")
    assert client.get("/api/analyses/not-an-id").status_code == 422
