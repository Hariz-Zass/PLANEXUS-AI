"""Safety checks for regional open-data updater (never download 500MB in CI)."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
import io
from pathlib import Path
import zipfile

import pytest

from app import osm_update


def make_zip(name="region/gis_osm_pois_free_1.gpkg",payload=b"synthetic-gpkg-bytes"):
    output=io.BytesIO()
    with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED) as target:
        target.writestr(name,payload)
    return output.getvalue()


def test_reject_zip_slip_and_missing_geopackage(tmp_path):
    for name in ("../escape.gpkg","/tmp/escape.gpkg","notes-only.txt"):
        file=tmp_path/(name.replace("/","-")+".zip")
        file.write_bytes(make_zip(name))
        with pytest.raises(ValueError):
            osm_update.extract_verified(file,tmp_path/"out")
    assert not (tmp_path/"escape.gpkg").exists()


def test_unpack_known_geofabrik_layer_only(tmp_path):
    data=tmp_path/"source.zip"
    data.write_bytes(make_zip())
    result=osm_update.extract_verified(data,tmp_path/"staging")
    assert len(result)==1
    assert result[0].name=="gis_osm_pois_free_1.gpkg"
    assert result[0].read_bytes()==b"synthetic-gpkg-bytes"


def test_operator_update_tracks_source_date_without_external_network(monkeypatch,tmp_path):
    published=datetime(2026,11,2,tzinfo=timezone.utc)
    data=make_zip(payload=b"synthetic-data"*10)
    class FakeStream:
        headers={"content-length":str(len(data)),
                 "last-modified":format_datetime(published,usegmt=True)}
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def raise_for_status(self):pass
        def iter_bytes(self,chunk_size):yield data
    def stream(method,url,**kwargs):
        assert method=="GET"
        assert url==osm_update.GEOFABRIK_ZIP
        return FakeStream()
    imports=[]
    monkeypatch.setattr(osm_update.httpx,"stream",stream)
    monkeypatch.setattr(osm_update,"readiness",lambda:{"ready":False})
    def fake_import(source,date):
        imports.append((Path(source),date))
        assert list(Path(source).glob("*.gpkg"))
        return 987
    monkeypatch.setattr(osm_update,"import_snapshot",fake_import)
    result=osm_update.update_from_geofabrik(workdir=tmp_path)
    assert result["status"]=="updated"
    assert result["imported_feature_count"]==987
    assert imports[0][1].startswith("2026-11-02")
    assert list(tmp_path.iterdir())==[]


def test_updater_skips_unchanged_source_without_unzipping(monkeypatch,tmp_path):
    published=datetime(2026,11,2,tzinfo=timezone.utc)
    class FakeStream:
        headers={"content-length":"500",
                 "last-modified":format_datetime(published,usegmt=True)}
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def raise_for_status(self):pass
        def iter_bytes(self,chunk_size):
            raise AssertionError("Unchanged source must not be downloaded")
    monkeypatch.setattr(osm_update.httpx,"stream",lambda *a,**k:FakeStream())
    monkeypatch.setattr(osm_update,"readiness",lambda:{
        "ready":True,"dataset_timestamp_utc":"2026-11-02T01:00:00+00:00"})
    result=osm_update.update_from_geofabrik(workdir=tmp_path)
    assert result["status"]=="already_current"
