"""Offline DEM pipeline regression checks: real GeoTIFF fixtures, no fabricated production data."""
from pathlib import Path
import numpy as np
import pytest
import rasterio
from rasterio.errors import RasterioIOError
from rasterio.transform import from_origin
from fastapi import HTTPException
from tests.client import TestClient
import app.sources as sources
import app.main as main

GEO={"type":"Polygon","coordinates":[[[101.07,4.66],[101.079,4.66],[101.079,4.669],[101.07,4.669],[101.07,4.66]]]}

def sample(path:Path,pixel:float):
    n=1500 if pixel<0.0005 else 500
    rows,cols=np.mgrid[:n,:n]
    data=(17.5+cols*0.6+rows*0.4).astype("float32")
    with rasterio.open(path,"w",driver="GTiff",width=n,height=n,count=1,crs="EPSG:4326",transform=from_origin(101,5,pixel,pixel),dtype="float32",nodata=-9999.0) as out:
        out.write(data,1)
    return path

def mock_cogs(monkeypatch,p30,p90,missing30=False):
    original=rasterio.open
    def open_mock(path,*args,**kwargs):
        if isinstance(path,str) and path.startswith("https://copernicus-dem-"):
            if "30m.s3" in path:
                if missing30:raise RasterioIOError("GLO30 unavailable (test fixture)")
                path=p30
            else:path=p90
        return original(path,*args,**kwargs)
    monkeypatch.setattr(sources.rasterio,"open",open_mock)

def test_auto_dem_and_contours(monkeypatch,tmp_path):
    p30=sample(tmp_path/"g30.tif",1/3600)
    p90=sample(tmp_path/"g90.tif",1/1200)
    mock_cogs(monkeypatch,p30,p90)
    path,meta=sources.acquire_copernicus((101.07,4.66,101.079,4.669),tmp_path/"output")
    assert meta["id"]=="copernicus-glo30-public"
    with rasterio.open(path) as raster:
        assert raster.crs.to_epsg()==4326 and raster.width<100
    report=main.analyze_terrain(GEO,path,meta,"test-auto")
    assert report["metrics"]["valid_slope_pixels"]>9
    assert report["metrics"]["contour_features"]>0
    assert report["contours_geojson"]["features"]
    assert report["elevation_geojson"]["features"]
    assert report["metrics"]["elevation_max_m"]>report["metrics"]["elevation_min_m"]

def test_clearly_labelled_glo90_fallback(monkeypatch,tmp_path):
    p30=sample(tmp_path/"g30.tif",1/3600)
    p90=sample(tmp_path/"g90.tif",1/1200)
    mock_cogs(monkeypatch,p30,p90,True)
    path,meta=sources.acquire_copernicus((101.07,4.66,101.079,4.669),tmp_path/"output")
    assert meta["nominal_resolution_m"]==90 and meta["fallback_used"]
    report=main.analyze_terrain(GEO,path,meta,"test-fallback")
    assert any("GLO-90" in warning for warning in report["warnings"])

def test_auto_api_report_and_copilot(monkeypatch,tmp_path):
    p30=sample(tmp_path/"g30.tif",1/3600)
    p90=sample(tmp_path/"g90.tif",1/1200)
    mock_cogs(monkeypatch,p30,p90)
    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"jobs-root")
    with TestClient(main.app) as client:
        project=client.post("/api/projects",json={"name":"Synthetic auto DSM test","geometry":GEO}).json()
        response=client.post("/api/terrain/auto",json={"geometry":GEO,"project_id":project["id"]})
        assert response.status_code==200,response.text
        result=response.json()
        assert result["contours_geojson"]["features"]
        aid=result["analysis_id"]
        assert client.get("/api/analyses").json()["analyses"][0]["analysis_id"]==aid
        assert client.get(f"/api/analyses/{aid}/report.md").status_code==200
        assert client.post("/api/copilot/assess",json={"analysis_id":aid,"question":"Bagaimana kecerunan tapak?"}).status_code==200

def test_missing_public_tiles_are_not_fabricated(monkeypatch,tmp_path):
    def unavailable(*args,**kwargs):raise RasterioIOError("tile unavailable")
    monkeypatch.setattr(sources.rasterio,"open",unavailable)
    with pytest.raises(HTTPException) as exc:
        sources.acquire_copernicus((101.07,4.66,101.08,4.67),tmp_path/"unavailable")
    assert exc.value.status_code==503
    assert "No elevation values were invented" in exc.value.detail
