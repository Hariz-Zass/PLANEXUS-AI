"""Functional/data-source audit, not a claim that all planning data are online."""
from __future__ import annotations
import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient as RawTestClient
from fastapi import HTTPException

import app.main as main
from app import auth, site_context
from tests.client import TestClient

SITE={"type":"Polygon","coordinates":[[
 [101.070,4.660],[101.080,4.660],[101.080,4.670],[101.070,4.670],[101.070,4.660]
]]}
SITE2={"type":"Polygon","coordinates":[[
 [101.071,4.660],[101.079,4.660],[101.079,4.668],[101.071,4.668],[101.071,4.660]
]]}


def test_source_registry_matches_actual_backend_capabilities(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"data")
    with TestClient(main.app) as api:
        res=api.get("/api/capabilities/data")
        assert res.status_code==200,res.text
        register=res.json()
        by_id={m["id"]:m for m in register["modules"]}
        assert "terrain_auto" in by_id and "zoning_rt" in by_id
        assert by_id["zoning_rt"]["implementation"]=="NOT_INTEGRATED"
        assert by_id["hydrology"]["implementation"]=="NOT_INTEGRATED"
        assert by_id["nearby"]["data_status"]=="osm_community_unverified"
        assert by_id["external_roads"]["implementation"]=="manual_road_sketch_only"
        assert by_id["copilot"]["data_status"]=="saved_terrain_evidence_only"
        assert register["numeric_policy_documents"]==2
        assert register["catalogue_only_policy_documents"]>=4
        assert any("I-Plan" in x["name"] for x in register["official_portals"])
        assert api.get("/api/sources").status_code==200
        assert api.get("/api/policy/catalog").status_code==200


def test_real_osm_parser_classifies_and_attributes_without_inventing_features(monkeypatch):
    elements=[
      {"type":"node","id":11,"lat":4.665,"lon":101.075,
       "tags":{"name":"Sekolah Ujian","amenity":"school"}},
      {"type":"node","id":12,"lat":4.6652,"lon":101.075,
       "tags":{"name":"Klinik Ujian","amenity":"clinic"}},
      {"type":"way","id":22,"center":{"lat":4.6651,"lon":101.074},
       "tags":{"name":"Jalan Ujian","highway":"residential"}},
      {"type":"way","id":23,"center":{"lat":4.6651,"lon":101.074},
       "tags":{"waterway":"stream"}},
      {"type":"node","id":99,"lat":4.665,"lon":101.075,
       "tags":{"name":"Fake Official Zone","landuse":"residential"}},
    ]
    captured={}
    class Response:
      content=json.dumps({"elements":elements}).encode()
      def raise_for_status(self):pass
      def json(self):return {"elements":elements}
    class Stub:
      def __init__(self,**kwargs):pass
      def __enter__(self):return self
      def __exit__(self,*args):return False
      def post(self,url,**kwargs):
        captured["url"]=url
        captured["query"]=kwargs["data"]["data"]
        return Response()
    monkeypatch.setattr(site_context.httpx,"Client",Stub)
    result=site_context.fetch_context(SITE,radius_m=1500)
    assert captured["url"]==site_context.OVERPASS_ENDPOINT
    assert result["api_endpoint"]==site_context.OVERPASS_ENDPOINT
    assert "around:1500" in captured["query"]
    assert result["status"]=="retrieved"
    assert result["counts"]["roads"]==1
    assert result["counts"]["waterways"]==1
    assert result["counts"]["education"]==1
    assert result["counts"]["healthcare"]==1
    assert "Fake Official Zone" not in str(result)
    assert len(result["named_places"])==2
    assert result["licence"].startswith("ODbL")
    assert result["source_quality"]=="community_unverified_not_official"
    assert result["geometry_sha256"]==site_context.geometry_digest(SITE)
    assert all(x["osm_url"].startswith("https://www.openstreetmap.org/")
               for x in result["named_places"])


def test_osm_network_failure_must_not_become_zero_nearby_features(monkeypatch):
    class Failure:
      def __init__(self,**kwargs):pass
      def __enter__(self):return self
      def __exit__(self,*args):return False
      def post(self,*args,**kwargs):
        import httpx
        raise httpx.ConnectError("synthetic Overpass connection failure")
    monkeypatch.setattr(site_context.httpx,"Client",Failure)
    with pytest.raises(HTTPException) as err:
        site_context.fetch_context(SITE)
    assert err.value.status_code==503
    assert "tiada jalan atau kemudahan direka" in err.value.detail


def test_context_is_real_project_scoped_persistent_and_invalidated(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"gis")
    called=[]
    def stub_fetch(geom,radius_m=1500):
        called.append(radius_m)
        return {"status":"retrieved","geometry_sha256":site_context.geometry_digest(geom),
                "source_id":"openstreetmap-overpass-community","counts":{"roads":2},
                "named_places":[],"retrieved_at_utc":"2026-11-03T00:00:00+00:00"}
    monkeypatch.setattr(main,"fetch_context",stub_fetch)
    with TestClient(main.app) as api:
        no_site=api.post("/api/projects",json={"name":"No boundary"}).json()
        assert api.post(f"/api/projects/{no_site['id']}/context/refresh").status_code==422
        project=api.post("/api/projects",json={"name":"Context A","geometry":SITE}).json()
        pid=project["id"]
        assert api.get(f"/api/projects/{pid}/context").json()["exists"] is False
        result=api.post(f"/api/projects/{pid}/context/refresh")
        assert result.status_code==200,result.text
        assert result.json()["context"]["counts"]["roads"]==2
        assert called==[1500]
        assert api.get(f"/api/projects/{pid}/context").json()["exists"] is True
        assert (main.DATA_DIR/"site_context"/(pid+".json")).is_file()
        updated=api.patch(f"/api/projects/{pid}",json={
          "expected_revision":project["revision"],"geometry":SITE2
        })
        assert updated.status_code==200,updated.text
        changed=api.get(f"/api/projects/{pid}/context").json()
        assert changed["exists"] is False
        assert changed["reason"]=="boundary_changed_rescan_required"


def test_context_cross_account_never_exposes_cached_project_result(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path/"gis")
    monkeypatch.setattr(main,"fetch_context",lambda geom,radius_m=1500:{
      "status":"retrieved","geometry_sha256":site_context.geometry_digest(geom),
      "source_id":"openstreetmap-overpass-community","counts":{"roads":2},"named_places":[]
    })
    with TestClient(main.app) as owner:
        p=owner.post("/api/projects",json={"name":"Private","geometry":SITE}).json()
        assert owner.post(f"/api/projects/{p['id']}/context/refresh").status_code==200
        auth.create_user(main.DATA_DIR,"other-context@example.test","Other Planner",
                         "Synthetic-CI-Another-Private-2026",role="planner")
        with RawTestClient(main.app,base_url="https://testserver") as outsider:
            login=outsider.post("/api/auth/login",json={
                "email":"other-context@example.test",
                "password":"Synthetic-CI-Another-Private-2026"})
            assert login.status_code==200
            outsider.headers.update({"X-CSRF-Token":login.json()["csrf_token"]})
            assert outsider.get(f"/api/projects/{p['id']}/context").status_code==404
            assert outsider.post(f"/api/projects/{p['id']}/context/refresh").status_code==404


def test_api_routes_real_no_placeholder_for_data_module(monkeypatch,tmp_path):
    """Ensure all documented interfaces resolve to implemented FastAPI routes."""
    paths={route.path for route in main.app.routes if hasattr(route,"path")}
    expected={
      "/api/health","/api/auth/login","/api/auth/me",
      "/api/projects","/api/projects/{project_id}",
      "/api/projects/{project_id}/context","/api/projects/{project_id}/context/refresh",
      "/api/terrain/auto","/api/terrain/upload","/api/analyses/{analysis_id}",
      "/api/projects/{project_id}/layout/preview",
      "/api/projects/{project_id}/layout","/api/projects/{project_id}/proposals",
      "/api/policy/catalog","/api/policy/assess",
      "/api/copilot/assess","/api/analyses/{analysis_id}/report.md",
      "/api/projects/{project_id}/exports/gis-package.zip",
      "/api/capabilities/data"
    }
    assert expected.issubset(paths), expected-paths



def test_context_survives_verified_backup_and_private_restore(tmp_path):
    from app.backup import create_backup
    from app.backup_restore import restore_backup
    from app.project_store import create_project
    data=tmp_path/"data"
    project=create_project(data,"Persist live community metadata",geometry=SITE)
    result={
      "status":"retrieved","source_id":"openstreetmap-overpass-community",
      "geometry_sha256":site_context.geometry_digest(SITE),
      "source_quality":"community_unverified_not_official",
      "retrieved_at_utc":"2026-11-03T00:00:00+00:00",
      "counts":{"roads":3},"named_places":[]
    }
    site_context.save_context(data,project["id"],result)
    assert site_context.get_cached_context(data,project["id"],SITE)["exists"] is True
    archive=create_backup(data,tmp_path/"snapshots")
    target=tmp_path/"new-recovered-volume"
    restore_backup(archive,target)
    recovered=site_context.get_cached_context(target,project["id"],SITE)
    assert recovered["exists"] is True
    assert recovered["context"]["counts"]["roads"]==3
    assert recovered["context"]["source_quality"]=="community_unverified_not_official"
    assert site_context.get_cached_context(target,project["id"],SITE2)["exists"] is False


def test_osm_provider_key_is_only_sent_as_header_not_placed_in_url(monkeypatch):
    monkeypatch.setenv("PLANEXUS_OVERPASS_CH_API_KEY","SYNTHETIC-NOT-A-REAL-KEY")
    providers=site_context._providers()
    assert providers[0][0]=="https://api.overpass.ch/v1/interpreter"
    assert providers[0][1]=={"X-API-Key":"SYNTHETIC-NOT-A-REAL-KEY"}
    assert all("SYNTHETIC-NOT-A-REAL-KEY" not in url for url,_ in providers)
    assert len(providers)>=3
