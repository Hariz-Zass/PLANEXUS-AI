"""B3.3 deterministic terrain QA: ground geometry/NoData, Horn/QGIS default.

Fixtures are deliberately SYNTHETIC. No field-survey accuracy is claimed.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi import HTTPException
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import Polygon, mapping
from shapely.ops import transform as shape_transform

from app.terrain import analyze_terrain
from app.terrain_quality import horn_slope_degrees, validate_raster_metadata
from tests.client import TestClient
import app.main as main


def synthetic_site(path: Path, *, z: np.ndarray, nodata: float=-9999.,
                   declared_unit: str | None = None) -> dict:
    height, width = z.shape
    left, top, cell = 720000., 520000., 10.
    with rasterio.open(path, "w", driver="GTiff", width=width, height=height,
                       count=1, crs="EPSG:32647", dtype="float32",
                       nodata=nodata, transform=from_origin(left,top,cell,cell)) as dst:
        dst.write(z.astype("float32"),1)
        if declared_unit:
            dst.set_band_unit(1,declared_unit)
    site=Polygon([
        (left+200,top-200),(left+(width-20)*cell,top-200),
        (left+(width-20)*cell,top-(height-20)*cell),(left+200,top-(height-20)*cell)
    ])
    wgs=Transformer.from_crs("EPSG:32647","EPSG:4326",always_xy=True)
    return mapping(shape_transform(wgs.transform,site))


def test_horn_3x3_planes_and_exact_nodata_mask():
    n=45
    yy,xx=np.mgrid[:n,:n]
    for dx,dy,expected in [
        (0.,0.,0.),(.1,0.,math.degrees(math.atan(.1))),
        (0.,.45,math.degrees(math.atan(.45))),
        (.22,.15,math.degrees(math.atan(math.hypot(.22,.15)))),
    ]:
        values=(40. + xx*dx*10 + yy*dy*10).astype("float32")
        slope=horn_slope_degrees(values,10,10)
        assert not np.any(np.isfinite(slope[0,:]))
        assert not np.any(np.isfinite(slope[-1,:]))
        assert np.allclose(slope[1:-1,1:-1],expected,atol=.0002)
    values=(40. + xx).astype("float32")
    values[20,20]=np.nan
    slope=horn_slope_degrees(values,10,10)
    assert int(np.count_nonzero(~np.isfinite(slope[19:22,19:22]))) == 9
    assert np.isfinite(slope[18,18])
    with pytest.raises(ValueError):
        horn_slope_degrees(values,0,10)


@pytest.mark.parametrize("name,dx,dy",[
    ("flat",.0,.0),
    ("low_relief",.06,.04),
    ("steep_mixed",.35,.22),
])
def test_source_hash_grid_and_terrain_qa_are_reproducible(tmp_path,name,dx,dy):
    yy,xx=np.mgrid[:110,:110]
    z=(20+xx*dx*10+yy*dy*10).astype("float32")
    file=tmp_path/(name+".tif")
    geom=synthetic_site(file,z=z)
    job=tmp_path/(name+"-job")
    report=analyze_terrain(geom,file,{
        "id":"synthetic-qa", "name":"Synthetic validation (not surveyed)",
        "data_type":"DTM", "nominal_resolution_m":10,
        "vertical_datum":"synthetic", "vertical_unit":"metres",
        "verified":"synthetic analytical plane only"
    },name,artifacts_dir=job)
    assert report["source_file"]["sha256"]==hashlib.sha256(file.read_bytes()).hexdigest()
    assert report["source_file"]["input_crs"]=="EPSG:32647"
    assert report["quality"]["terrain_screening_only"] is True
    assert report["quality"]["field_vertical_accuracy_verified"] is False
    assert report["quality"]["elevation_site_cell_coverage_pct"] > 97
    assert report["quality"]["slope_site_cell_coverage_pct"] > 95
    assert report["metrics"]["coverage_percent_est"] <= 100
    assert report["metrics"]["slope_coverage_percent"] <= 100
    assert report["metrics"]["slope_classes"]
    assert report["elevation_geojson"]["features"]
    assert report["slope_geojson"]["features"]
    assert (job/"elevation_utm.tif").exists()
    assert (job/"slope_degrees_utm.tif").exists()
    with rasterio.open(job/"elevation_utm.tif") as elev, rasterio.open(job/"slope_degrees_utm.tif") as slope:
        assert elev.crs.to_epsg() == 32647
        assert elev.transform == slope.transform
        assert elev.width == slope.width and elev.height == slope.height
        arr=slope.read(1,masked=True)
        assert arr.count()>100
        calculated=float(np.ma.median(arr))
        expected=math.degrees(math.atan(math.hypot(dx,dy)))
        assert calculated==pytest.approx(expected,abs=.07)
        # The saved slope grid must have no invented values where its 3x3
        # elevation support is absent.
        assert not np.any(np.isfinite(arr.filled(np.nan)[0,:]))
    assert report["quality"]["external_gdal_qgis_comparison"].startswith("Not performed")


def test_source_nodata_remains_unassessed_not_low_slope(tmp_path):
    yy,xx=np.mgrid[:110,:110]
    data=(25+xx*.5+yy*.1).astype("float32")
    data[37:47,37:47]=-9999.
    file=tmp_path/"nodata.tif"
    geom=synthetic_site(file,z=data)
    report=analyze_terrain(geom,file,{
        "id":"synthetic-qa","name":"NoData CI fixture",
        "data_type":"DEM-unknown","nominal_resolution_m":10,
    },"synthetic-nodata",artifacts_dir=tmp_path/"job")
    q=report["quality"]
    assert q["slope_site_cell_coverage_pct"] < q["elevation_site_cell_coverage_pct"]
    assert report["metrics"]["valid_slope_pixels"] < report["metrics"]["valid_elevation_pixels"]
    assert report["suitability"]["unassessed_area_ha_est"] > 0
    assert any(f["properties"]["class_id"] == 4 for f in report["suitability_geojson"]["features"])
    assert "NoData" in " ".join(report["warnings"])
    assert report["metrics"]["slope_coverage_percent"] < 100


def test_declared_feet_are_not_misinterpreted_as_metre_heights(tmp_path):
    raster=tmp_path/"feet.tif"
    geom=synthetic_site(raster,z=np.ones((110,110),dtype="float32"),declared_unit="ft")
    with pytest.raises(HTTPException) as exc:
        analyze_terrain(geom,raster,{
            "id":"user-upload","name":"Feet raster","data_type":"DTM"
        },"cannot-pretend-meters")
    assert exc.value.status_code == 422
    assert "unit kaki" in exc.value.detail


def test_qgis_qa_report_is_private_and_persists_with_project(monkeypatch,tmp_path):
    yy,xx=np.mgrid[:110,:110]
    source=tmp_path/"private.tif"
    geom=synthetic_site(source,z=20+xx*.4+yy*.15)
    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"private-gis-store")
    with TestClient(main.app) as client:
        p=client.post("/api/projects",json={
            "name":"QA workspace","geometry":geom
        })
        assert p.status_code==201,p.text
        with source.open("rb") as file:
            result=client.post("/api/terrain/upload",
                data={"project_id":p.json()["id"],"geometry":json.dumps(geom),
                      "source_name":"Synthetic independent QA", "height_model":"DTM",
                      "vertical_unit":"metres","vertical_datum":"synthetic"},
                files={"file":("private.tif",file,"image/tiff")})
        assert result.status_code==200,result.text
        report=result.json()
        qa=report["quality"]
        assert 90<qa["slope_site_cell_coverage_pct"]<=100
        assert (tmp_path/"private-gis-store"/"jobs"/report["analysis_id"]/"elevation_utm.tif").exists()
        markdown=client.get(f"/api/analyses/{report['analysis_id']}/verification.md")
        assert markdown.status_code==200
        assert report["source_file"]["sha256"] in markdown.text
        assert "External QGIS file comparison:" in markdown.text
        assert "NOT performed" in markdown.text
        again=client.get(f"/api/analyses/{report['analysis_id']}")
        assert again.status_code==200
        assert again.json()["quality"]==report["quality"]
        for asset in ("elevation-utm.tif","slope-utm.tif"):
            downloaded=client.get(f"/api/analyses/{report['analysis_id']}/{asset}")
            assert downloaded.status_code==200, downloaded.text[:160]
            assert downloaded.headers["content-type"].startswith("image/tiff")
            assert len(downloaded.content)>500
        missing=client.get("/api/analyses/00000000-0000-4000-8000-000000000000/slope-utm.tif")
        assert missing.status_code==404



def test_contour_lines_match_reported_elevation_levels_on_projected_grid(tmp_path):
    """Check line vertices' elevation against bilinear interpolation of saved UTM DEM."""
    yy,xx=np.mgrid[:130,:130]
    z=(15+xx*.62+yy*.39).astype("float32")
    source=tmp_path/"contour-surface.tif"
    geometry=synthetic_site(source,z=z)
    directory=tmp_path/"contour-output"
    report=analyze_terrain(geometry,source,{
        "id":"synthetic-contour-check","name":"Synthetic smooth plane (not real land)",
        "data_type":"DTM","nominal_resolution_m":10
    },"contour-qa",artifacts_dir=directory)
    features=report["contours_geojson"]["features"]
    assert len(features)>0
    interval=report["metrics"]["contour_interval_m"]
    assert interval is not None and interval>0
    to_utm=Transformer.from_crs("EPSG:4326","EPSG:32647",always_xy=True)
    validated=0
    with rasterio.open(directory/"elevation_utm.tif") as dem:
        grid=dem.read(1,masked=True).filled(np.nan)
        for feature in features[:40]:
            expected=float(feature["properties"]["elevation_m"])
            assert math.isclose(expected/interval,round(expected/interval),abs_tol=0.0001)
            for lon,lat in feature["geometry"]["coordinates"][::max(1,len(feature["geometry"]["coordinates"])//8)]:
                x,y=to_utm.transform(lon,lat)
                # DEM pixel-centre fractional row/column in metre-based CRS.
                c=(x-dem.transform.c)/dem.transform.a-.5
                rr=(dem.transform.f-y)/abs(dem.transform.e)-.5
                c0, r0=math.floor(c),math.floor(rr)
                if r0<0 or c0<0 or r0+1>=dem.height or c0+1>=dem.width:
                    continue
                samples=grid[r0:r0+2,c0:c0+2]
                if not np.isfinite(samples).all():
                    continue
                fx,fy=c-c0,rr-r0
                interpolated=(samples[0,0]*(1-fx)*(1-fy)+
                              samples[0,1]*fx*(1-fy)+
                              samples[1,0]*(1-fx)*fy+
                              samples[1,1]*fx*fy)
                # WGS84 polygon geometry rounds to 6 decimals (~0.11 m):
                # 0.3m vertical allowance covers quantization for steep planar trends.
                assert abs(float(interpolated)-expected)<0.3
                validated+=1
    assert validated>=10
