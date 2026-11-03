"""B3.4 GIS package checks: actual Fiona GeoPackage, EPSG:4326 vectors and UTM rasters."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import fiona
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import transform
from tests.client import TestClient

import app.main as main
from app import auth


def site_fixture(tmp_path: Path) -> tuple[Path, dict]:
    raster=tmp_path/"synthetic-dtm.tif"
    yy,xx=np.indices((120,120))
    z=(28+xx*.28+yy*.21).astype("float32")
    with rasterio.open(raster,"w",driver="GTiff",width=120,height=120,
                       count=1,dtype="float32",crs="EPSG:32647",
                       nodata=-9999.,transform=from_origin(720000,520000,10,10)) as dst:
        dst.write(z,1)
    poly=Polygon([(720200,519800),(721000,519800),
                  (721000,519000),(720200,519000)])
    converter=Transformer.from_crs("EPSG:32647","EPSG:4326",always_xy=True)
    return raster,mapping(transform(converter.transform,poly))


def test_real_gis_zip_and_gpkg_preserve_crs_layers_and_provenance(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"gis")
    raster,geometry=site_fixture(tmp_path)
    with TestClient(main.app) as api:
        created=api.post("/api/projects",json={
            "name":"Synthetic GIS Export Project","geometry":geometry
        })
        assert created.status_code==201,created.text
        pid=created.json()["id"]
        with raster.open("rb") as file:
            analysed=api.post("/api/terrain/upload",data={
                "project_id":pid,"geometry":json.dumps(geometry),
                "source_name":"SYNTHETIC GIS EXPORT - not a survey",
                "height_model":"DTM","vertical_unit":"metres",
                "vertical_datum":"synthetic CI height"
            },files={"file":("heights.tif",file,"image/tiff")})
        assert analysed.status_code==200,analysed.text
        report=analysed.json()
        assert report["contours_geojson"]["features"]
        assert report["quality"]["slope_site_cell_coverage_pct"]>80

        # Direct GeoJSON with proper response type and owner authentication.
        site=api.get(f"/api/projects/{pid}/exports/site_boundary.geojson")
        assert site.status_code==200,site.text
        assert site.headers["content-type"].startswith("application/geo+json")
        assert shape(site.json()["features"][0]["geometry"]).equals(shape(geometry))
        contours=api.get(f"/api/projects/{pid}/exports/contours.geojson")
        assert contours.status_code==200
        assert all("elevation_m" in f["properties"]
                   for f in contours.json()["features"])
        missing=api.get(f"/api/projects/{pid}/exports/unknown.geojson")
        assert missing.status_code==404

        gpkg=api.get(f"/api/projects/{pid}/exports/layers.gpkg")
        assert gpkg.status_code==200,gpkg.text[:150] if gpkg.status_code!=200 else ""
        assert gpkg.content[:16]==b"SQLite format 3\x00"
        target=tmp_path/"direct-layers.gpkg"
        target.write_bytes(gpkg.content)
        layers=set(fiona.listlayers(target))
        assert layers=={"site_boundary","slope_classes","elevation_bands",
                        "contours","suitability"}
        for layer in layers:
            with fiona.open(target,layer=layer) as dataset:
                assert dataset.crs.to_epsg()==4326
                assert len(dataset)>0

        bundle=api.get(f"/api/projects/{pid}/exports/gis-package.zip")
        assert bundle.status_code==200,bundle.text[:150] if bundle.status_code!=200 else ""
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            names=set(archive.namelist())
            assert "vector/planexus_layers.gpkg" in names
            assert "vector/site_boundary.geojson" in names
            assert "vector/contours.geojson" in names
            assert "raster/elevation_utm.tif" in names
            assert "raster/slope_degrees_utm.tif" in names
            assert "raster/uploaded_source.tif" in names
            manifest=json.loads(archive.read("export-manifest.json"))
            assert manifest["analysis_id"]==report["analysis_id"]
            assert manifest["project"]["id"]==pid
            assert manifest["vector_crs"]=="EPSG:4326"
            assert manifest["analysis_crs"]=="EPSG:32647"
            assert manifest["source_file"]["sha256"]==report["source_file"]["sha256"]
            assert manifest["vector_layers"]["contours"]["feature_count"]>0
            assert manifest["vector_layers"]["slope_classes"]["preview_only"] is True
            assert manifest["vector_layers"]["site_boundary"]["preview_only"] is False
            for name,meta in manifest["files"].items():
                body=archive.read(name)
                assert len(body)==meta["size_bytes"]
                assert hashlib.sha256(body).hexdigest()==meta["sha256"]
            # Actual compressed GeoTIFFs retain UTM CRS and pixel values.
            from rasterio.io import MemoryFile
            with MemoryFile(archive.read("raster/slope_degrees_utm.tif")) as mem:
                with mem.open() as tif:
                    assert tif.crs.to_epsg()==32647
                    assert tif.count==1
                    assert tif.read(1,masked=True).count()>100


def test_boundary_only_export_is_explicit_not_fake_terrain(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"single-site")
    _,geometry=site_fixture(tmp_path)
    with TestClient(main.app) as api:
        created=api.post("/api/projects",json={
            "name":"Empty terrain project","geometry":geometry
        })
        assert created.status_code==201
        pid=created.json()["id"]
        result=api.get(f"/api/projects/{pid}/exports/gis-package.zip")
        assert result.status_code==200
        with zipfile.ZipFile(io.BytesIO(result.content)) as package:
            names=set(package.namelist())
            assert names=={"vector/site_boundary.geojson",
                           "vector/planexus_layers.gpkg","export-manifest.json"}
            manifest=json.loads(package.read("export-manifest.json"))
            assert manifest["analysis_id"] is None
            assert list(manifest["vector_layers"])==["site_boundary"]


def test_other_user_cannot_export_gis_bundle_or_any_vector(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"private")
    _,geometry=site_fixture(tmp_path)
    with TestClient(main.app) as owner:
        pid=owner.post("/api/projects",json={
            "name":"Private protected export","geometry":geometry
        }).json()["id"]
        auth.create_user(main.DATA_DIR,"foreign@example.test","Foreign Planner",
                         "Foreign-Private-GIS-2026!",role="planner")
        from fastapi.testclient import TestClient as RawClient
        with RawClient(main.app,base_url="https://testserver") as other:
            logged=other.post("/api/auth/login",json={
                "email":"foreign@example.test","password":"Foreign-Private-GIS-2026!"
            })
            assert logged.status_code==200
            for filename in ("gis-package.zip","layers.gpkg","site_boundary.geojson"):
                forbidden=other.get(f"/api/projects/{pid}/exports/{filename}")
                assert forbidden.status_code==404, (filename,forbidden.text)


def test_tampered_source_raster_blocks_export(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"gis")
    raster,geometry=site_fixture(tmp_path)
    with TestClient(main.app) as api:
        pid=api.post("/api/projects",json={"name":"Source audit","geometry":geometry}).json()["id"]
        with raster.open("rb") as f:
            result=api.post("/api/terrain/upload",data={
                "project_id":pid,"geometry":json.dumps(geometry),
                "source_name":"Synthetic input", "height_model":"DTM",
                "vertical_unit":"metres"
            },files={"file":("input.tif",f,"image/tiff")})
        assert result.status_code==200,result.text
        job=main.DATA_DIR/"jobs"/result.json()["analysis_id"]
        (job/"uploaded_source.tif").write_bytes(b"BAD TIF")
        exported=api.get(f"/api/projects/{pid}/exports/gis-package.zip")
        assert exported.status_code==503,exported.text
