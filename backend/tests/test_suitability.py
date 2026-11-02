"""Deterministic terrain suitability screening: slope pixel thresholds and honest unknowns."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import transform as geom_transform

from app.suitability import build_suitability
from app.terrain import analyze_terrain
import app.main as main


def sample_screening(*, slope, mask, inside=None, pixel_area_m2=100.0, site_area_ha=0.1, resolution=30, feature_limit=100):
    if inside is None:
        inside=np.ones_like(mask,dtype=bool)
    return build_suitability(
        slope_degrees=np.asarray(slope,dtype=float),
        valid_slope=np.asarray(mask,dtype=bool),
        inside_site=np.asarray(inside,dtype=bool),
        pixel_area_m2=pixel_area_m2,
        site_area_ha=site_area_ha,
        transform=from_origin(500000,520000,10,10),
        crs="EPSG:32647",
        source={"data_type":"DSM","nominal_resolution_m":resolution},
        max_features=feature_limit,
    )


def test_exact_thresholds_and_unknown_cells_never_count_as_gentle():
    slope=np.array([[0.0,14.99,15.0,24.99,25.0],
                    [34.99,35.0,float("nan"),float("inf"),10.0]])
    valid=np.isfinite(slope)
    report=sample_screening(slope=slope,mask=valid)
    summary=report["summary"]
    bands=summary["bands"]
    assert [b["pixels"] for b in bands]==[3,2,3,2]
    assert [b["share_of_assessed_pct"] for b in bands]==[37.5,25.0,37.5,None]
    assert summary["assessed_pixels"]==8
    assert summary["site_mask_pixels"]==10
    assert summary["assessed_area_ha_est"]==pytest.approx(0.08)
    assert summary["unassessed_area_ha_est"]==pytest.approx(0.02)
    assert summary["coverage_of_site_pct_est"]==80
    assert sum(b["pixels"] for b in bands)==10
    features=report["geojson"]["features"]
    assert {f["properties"]["class_id"] for f in features}=={1,2,3,4}
    assert all(f["properties"]["screening_only"] for f in features)
    assert "not a planning approval" in summary["warnings"][0].lower()
    assert "not RT" in summary["disclaimer"]
    assert any("DSM" in msg for msg in summary["warnings"])


def test_only_inside_site_samples_count_and_truncation_does_not_change_statistics():
    slope=np.array([[3,18,40],[2,19,36],[30,7,11]],dtype=float)
    mask=np.ones((3,3),dtype=bool)
    inside=np.array([[1,1,0],[1,1,0],[0,0,1]],dtype=bool)
    full=sample_screening(slope=slope,mask=mask,inside=inside,site_area_ha=.06)
    limited=sample_screening(slope=slope,mask=mask,inside=inside,site_area_ha=.06,feature_limit=1)
    assert [b["pixels"] for b in full["summary"]["bands"]]==[3,2,0,0]
    assert full["summary"]["assessed_pixels"]==5
    assert full["summary"]["site_mask_pixels"]==5
    assert limited["summary"]["bands"]==full["summary"]["bands"]
    assert limited["summary"]["class_overlay_truncated"] is True
    assert len(limited["geojson"]["features"])==1
    assert len(full["geojson"]["features"])>=2


def test_coarse_pixel_area_warning_and_low_coverage_no_fake_buildability():
    slope=np.array([[10,10],[10,30]],dtype=float)
    result=sample_screening(slope=slope,mask=np.ones((2,2),dtype=bool),pixel_area_m2=900,site_area_ha=.01,resolution=90)
    summary=result["summary"]
    assert summary["area_exceeds_site_due_to_pixelization"] is True
    assert summary["coverage_of_site_pct_est"]==100
    assert any("exceeds" in warning for warning in summary["warnings"])
    assert any("90 m" in warning for warning in summary["warnings"])
    assert "zoning" in summary["disclaimer"].lower()


def test_no_valid_samples_is_rejected():
    slope=np.full((3,3),np.nan)
    with pytest.raises(ValueError,match="No verified slope pixels"):
        sample_screening(slope=slope,mask=np.zeros((3,3),dtype=bool))


def make_synthetic_raster(path:Path):
    n=120
    yy,xx=np.mgrid[:n,:n]
    # Two terrain gradient regimes, both real computed values in a synthetic fixture.
    z=(xx*0.8 + np.where(xx<60,0,(xx-60)*2.2)+yy*0.05).astype("float32")
    west,north=720000,520000
    with rasterio.open(path,"w",driver="GTiff",height=n,width=n,count=1,crs="EPSG:32647",
        transform=from_origin(west,north,10,10),nodata=-9999.0,dtype="float32") as raster:
        raster.write(z,1)
    poly=Polygon([(west+200,north-200),(west+1000,north-200),(west+1000,north-1000),(west+200,north-1000)])
    transform_wgs=Transformer.from_crs("EPSG:32647","EPSG:4326",always_xy=True)
    geom=mapping(geom_transform(transform_wgs.transform,poly))
    return geom


def test_integration_report_persists_suitability_and_markdown(monkeypatch,tmp_path):
    path=tmp_path/"raster.tif"
    geometry=make_synthetic_raster(path)
    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"data")
    c=TestClient(main.app)
    with path.open("rb") as file:
        result=c.post("/api/terrain/upload",
            data={"geometry":json.dumps(geometry),"source_name":"Synth terrain suitability fixture",
                  "height_model":"DTM","vertical_unit":"metres","vertical_datum":"test"},
            files={"file":("synthetic.tif",file,"image/tiff")})
    assert result.status_code==200,result.text
    report=result.json()
    bands=report["suitability"]["bands"]
    assert len(bands)==4
    assert sum(b["pixels"] for b in bands[:3])==report["metrics"]["valid_slope_pixels"]
    assert any(f["properties"]["class_id"] in (1,2,3) for f in report["suitability_geojson"]["features"])
    reopened=c.get("/api/analyses/"+report["analysis_id"])
    assert reopened.status_code==200
    assert reopened.json()["suitability"]==report["suitability"]
    md=c.get("/api/analyses/"+report["analysis_id"]+"/report.md")
    assert md.status_code==200
    assert "Preliminary terrain constraint screening" in md.text
    assert "NOT development approval" in md.text
    assert "Lower terrain constraint" in md.text
    # No planning law or building unit count appears as a measured result.
    assert "300 units allowed" not in md.text
    stored=tmp_path/"data"/"jobs"/report["analysis_id"]/"result.json"
    assert stored.is_file()
