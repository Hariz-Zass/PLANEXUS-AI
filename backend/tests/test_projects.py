"""Project workspace persistence/regression tests (real SQLite + GeoTIFF, isolated tmp dir)."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import rasterio
from tests.client import TestClient
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import Polygon, mapping
from shapely.ops import transform

import app.main as main

SITE_A = {"type":"Polygon","coordinates":[[[101.070,4.660],[101.080,4.660],[101.080,4.670],[101.070,4.670],[101.070,4.660]]]}
SITE_B = {"type":"Polygon","coordinates":[[[101.090,4.680],[101.100,4.680],[101.100,4.690],[101.090,4.690],[101.090,4.680]]]}


def test_project_create_open_update_and_persist_across_clients(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    with TestClient(main.app) as first:
        r = first.post("/api/projects", json={"name":" Projek Meru Raya ","description":"Terrain study","geometry":SITE_A})
        assert r.status_code == 201, r.text
        p=r.json()
        assert p["name"]=="Projek Meru Raya"
        assert p["has_site"] and p["site_area_ha"] > 0
        assert p["geometry"]["type"]=="Polygon"
        assert p["revision"]==1
        pid=p["id"]
        assert first.get("/api/projects").json()["projects"][0]["id"]==pid
        update=first.patch(f"/api/projects/{pid}",json={"expected_revision":1,"name":"Meru Raya - Stage 2"})
        assert update.status_code==200,update.text
        assert update.json()["revision"]==2
        assert update.json()["geometry"] is not None
    # A fresh TestClient emulates a backend process restart against the same SQLite file.
    with TestClient(main.app) as second:
        reopened=second.get(f"/api/projects/{pid}")
        assert reopened.status_code==200
        assert reopened.json()["name"]=="Meru Raya - Stage 2"
        assert reopened.json()["revision"]==2
        assert reopened.json()["site_area_ha"] > 0
    assert (tmp_path/"planexus-workspace.sqlite3").is_file()


def test_two_projects_isolated_and_stale_revision_protected(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path)
    c=TestClient(main.app)
    a=c.post("/api/projects",json={"name":"Site A","geometry":SITE_A}).json()
    b=c.post("/api/projects",json={"name":"Site B","geometry":SITE_B}).json()
    assert a["id"]!=b["id"]
    assert a["geometry"]!=b["geometry"]
    updated=c.patch(f"/api/projects/{a['id']}",json={"expected_revision":1,"geometry":SITE_B})
    assert updated.status_code==200
    assert updated.json()["revision"]==2
    stale=c.patch(f"/api/projects/{a['id']}",json={"expected_revision":1,"name":"BAD STALE WRITE"})
    assert stale.status_code==409
    assert c.get(f"/api/projects/{a['id']}").json()["name"]=="Site A"
    assert c.get(f"/api/projects/{b['id']}").json()["geometry"]==b["geometry"]
    invalid=c.patch(f"/api/projects/{b['id']}",json={"expected_revision":1,"geometry":{"type":"Point","coordinates":[101,4]}})
    assert invalid.status_code==422
    assert c.get(f"/api/projects/{b['id']}").json()["revision"]==1
    assert c.get("/api/projects/not-valid-uuid").status_code==422


def make_raster(path:Path) -> dict:
    # Make 10m resolution geo-referenced test surface; no online access required.
    n=120
    field=np.repeat(np.arange(n,dtype="float32")[None,:],n,axis=0)
    w,north=720000,520000
    with rasterio.open(path,"w",driver="GTiff",width=n,height=n,count=1,crs="EPSG:32647",
                       dtype="float32",nodata=-9999,transform=from_origin(w,north,10,10)) as raster:
        raster.write(field,1)
    poly=Polygon([(w+200,north-200),(w+1000,north-200),(w+1000,north-1000),(w+200,north-1000)])
    t=Transformer.from_crs("EPSG:32647","EPSG:4326",always_xy=True)
    return mapping(transform(t.transform,poly))


def test_uploaded_analysis_is_linked_and_restore_full_layers(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"data")
    geometry=make_raster(tmp_path/"site.tif")
    c=TestClient(main.app)
    project=c.post("/api/projects",json={"name":"Site Survey V1","geometry":geometry}).json()
    pid=project["id"]
    with (tmp_path/"site.tif").open("rb") as file:
        upload=c.post("/api/terrain/upload",
            data={"project_id":pid,"geometry":json.dumps(geometry),"source_name":"Local approved DEM fixture",
                  "height_model":"DTM","vertical_unit":"metres","vertical_datum":"fixture"},
            files={"file":("test.tif",file,"image/tiff")})
    assert upload.status_code==200,upload.text
    aid=upload.json()["analysis_id"]
    opened=c.get(f"/api/projects/{pid}").json()
    assert opened["active_analysis_id"]==aid
    assert opened["revision"]==2
    assert len(opened["analyses"])==1
    assert opened["analyses"][0]["analysis_id"]==aid
    full=c.get(f"/api/analyses/{aid}").json()
    assert full["slope_geojson"]["features"]
    assert full["elevation_geojson"]["features"]
    assert full["contours_geojson"]["features"]
    assert c.get(f"/api/analyses/{aid}/report.md").status_code==200
    # Reopen the older snapshot; status and geometry must be consistent.
    current=c.post(f"/api/projects/{pid}/activate-analysis",json={"analysis_id":aid})
    assert current.status_code==200,current.text
    assert current.json()["geometry"]==opened["geometry"]
    assert current.json()["active_analysis_id"]==aid
    # Any site edit invalidates the active result (without deleting the historic raster).
    clearing=c.patch(f"/api/projects/{pid}",json={"expected_revision":3,"geometry":SITE_A})
    assert clearing.status_code==200,clearing.text
    assert clearing.json()["active_analysis_id"] is None
    assert len(clearing.json()["analyses"])==1
    restore=c.post(f"/api/projects/{pid}/activate-analysis",json={"analysis_id":aid})
    assert restore.status_code==200
    assert restore.json()["active_analysis_id"]==aid
    assert restore.json()["geometry"]==opened["geometry"]


def test_prevent_wrong_site_analysis_and_cross_project_activation(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path)
    c=TestClient(main.app)
    a=c.post("/api/projects",json={"name":"Alpha","geometry":SITE_A}).json()
    b=c.post("/api/projects",json={"name":"Bravo","geometry":SITE_B}).json()
    failed=c.post("/api/terrain/auto",json={"project_id":a["id"],"geometry":SITE_B})
    assert failed.status_code==409
    assert c.get(f"/api/projects/{a['id']}").json()["revision"]==1
    assert c.post(f"/api/projects/{b['id']}/activate-analysis",json={"analysis_id":"00000000-0000-4000-8000-000000000000"}).status_code==404


def test_local_project_delete_does_not_delete_report_data(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path)
    c=TestClient(main.app)
    p=c.post("/api/projects",json={"name":"Temporary site","geometry":SITE_A}).json()
    pid=p["id"]
    assert c.delete(f"/api/projects/{pid}").status_code==204
    assert c.get(f"/api/projects/{pid}").status_code==404
    assert not c.get("/api/projects").json()["projects"]
