"""B3.2 tests: real HTTP auth, CSRF, ownership, invites and legacy migration.

No fixture session shortcuts. TestClient here is FastAPI's raw client.
"""
from __future__ import annotations

import json
import sqlite3
import uuid

from fastapi.testclient import TestClient
from shapely.geometry import shape

import app.main as main
from app import auth
from app.project_store import attach_analysis, create_project

SITE = {"type":"Polygon","coordinates":[[
    [101.070,4.660],[101.079,4.660],[101.079,4.669],
    [101.070,4.669],[101.070,4.660]
]]}
ADMIN_PASSWORD = "PilotAdmin2026-Long-Secret!"
PLANNER_PASSWORD = "Planning2026-Strong-Secret!"


def bootstrap(monkeypatch, tmp_path):
    storage = tmp_path/"private-gis"
    monkeypatch.setattr(main,"DATA_DIR",storage)
    a = auth.create_user(storage,"admin@example.test","Planner Admin",
                         ADMIN_PASSWORD,role="admin")
    return storage, a


def sign_in(client, email, password):
    login = client.post("/api/auth/login",json={"email":email,"password":password})
    assert login.status_code == 200,login.text
    data = login.json()
    client.headers.update({"X-CSRF-Token":data["csrf_token"]})
    return data


def test_all_private_routes_require_real_session(monkeypatch,tmp_path):
    bootstrap(monkeypatch,tmp_path)
    with TestClient(main.app,base_url="https://testserver") as client:
        assert client.get("/api/health").status_code == 200
        for route in ("/api/projects","/api/analyses","/api/policy/catalog",
                      "/api/sources","/api/copilot/capabilities",
                      "/api/projects/00000000-0000-4000-8000-000000000000",
                      "/api/analyses/00000000-0000-4000-8000-000000000000",
                      "/api/analyses/00000000-0000-4000-8000-000000000000/report.md"):
            response=client.get(route)
            assert response.status_code == 401,(route,response.text)
        for route,data in (
            ("/api/projects",{"name":"Must be protected"}),
            ("/api/site/inspect",{"geometry":SITE}),
            ("/api/terrain/auto",{"geometry":SITE}),
            ("/api/copilot/assess",{"question":"Bagaimana akses?"}),
        ):
            assert client.post(route,json=data).status_code == 401,route


def test_cookie_csrf_session_expiry_logout_origin_and_password_hash(monkeypatch,tmp_path):
    data,_=bootstrap(monkeypatch,tmp_path)
    with TestClient(main.app,base_url="https://testserver") as client:
        assert client.post("/api/projects",json={"name":"No session"}).status_code==401
        bad=client.post("/api/auth/login",json={"email":"admin@example.test","password":"incorrect"})
        assert bad.status_code==401
        logged=sign_in(client,"admin@example.test",ADMIN_PASSWORD)
        assert logged["user"]["role"]=="admin"
        assert logged["user"]["email"]=="admin@example.test"
        assert "planexus_session" in client.cookies
        assert "httponly" in client.post("/api/auth/login",
                      json={"email":"admin@example.test","password":ADMIN_PASSWORD}).headers["set-cookie"].lower()
        # Re-login rotates session; latest login's CSRF value replaces the old one.
        csrf=client.get("/api/auth/me").json()["csrf_token"]
        client.headers["X-CSRF-Token"]=csrf
        with sqlite3.connect(data/"planexus-workspace.sqlite3") as conn:
            ph=conn.execute("SELECT password_hash FROM users WHERE email=?",
                            ("admin@example.test",)).fetchone()[0]
        assert ph.startswith("scrypt:")
        assert ADMIN_PASSWORD not in ph
        client.headers.pop("X-CSRF-Token")
        assert client.post("/api/projects",json={"name":"No csrf"}).status_code==403
        client.headers["X-CSRF-Token"]="forged-csrf"
        assert client.post("/api/projects",json={"name":"Forged csrf"}).status_code==403
        client.headers["X-CSRF-Token"]=csrf
        assert client.post("/api/projects",json={"name":"Bad Origin"},
                           headers={"Origin":"https://evil.example"}).status_code==403
        ok=client.post("/api/projects",json={"name":"Secured private site"})
        assert ok.status_code==201,ok.text
        assert client.post("/api/auth/logout").status_code==204
        assert client.get("/api/projects").status_code==401
        assert client.get("/api/auth/me").status_code==401

    with TestClient(main.app,base_url="https://testserver") as later:
        sign_in(later,"admin@example.test",ADMIN_PASSWORD)
        with sqlite3.connect(data/"planexus-workspace.sqlite3") as conn:
            conn.execute("UPDATE auth_sessions SET expires_at_utc='2000-01-01T00:00:00+00:00'")
        assert later.get("/api/projects").status_code==401


def test_invite_only_registration_single_use_and_account_isolation(monkeypatch,tmp_path):
    data,admin=bootstrap(monkeypatch,tmp_path)
    with TestClient(main.app,base_url="https://testserver") as admin_client, TestClient(main.app,base_url="https://testserver") as other:
        sign_in(admin_client,"admin@example.test",ADMIN_PASSWORD)
        site=admin_client.post("/api/projects",json={"name":"Private Alpha","geometry":SITE})
        assert site.status_code==201,site.text
        project_a=site.json()["id"]
        assert other.post("/api/auth/register",json={
            "email":"bravo@example.test","display_name":"Other Planner",
            "password":PLANNER_PASSWORD,"invite_token":"invalid"}).status_code==403
        invite=auth.create_invite(data,"admin@example.test")
        reg=other.post("/api/auth/register",json={
            "email":"bravo@example.test","display_name":"Other Planner",
            "password":PLANNER_PASSWORD,"invite_token":invite})
        assert reg.status_code==201,reg.text
        assert reg.json()["user"]["role"]=="planner"
        replay=other.post("/api/auth/register",json={
            "email":"third@example.test","display_name":"Third User",
            "password":PLANNER_PASSWORD,"invite_token":invite})
        assert replay.status_code==403
        sign_in(other,"bravo@example.test",PLANNER_PASSWORD)
        created=other.post("/api/projects",json={"name":"Private Bravo","geometry":SITE})
        assert created.status_code==201,created.text
        project_b=created.json()["id"]

        def scoped_urls(pid):
            base=f"/api/projects/{pid}"
            return [base,base+"/layout",base+"/proposals",base+"/proposals/"+str(uuid.uuid4())]
        assert [p["id"] for p in admin_client.get("/api/projects").json()["projects"]]==[project_a]
        assert [p["id"] for p in other.get("/api/projects").json()["projects"]]==[project_b]
        for url in scoped_urls(project_a):
            assert other.get(url).status_code==404,url
        for url in scoped_urls(project_b):
            assert admin_client.get(url).status_code==404,url
        assert other.patch(f"/api/projects/{project_a}",
                           json={"expected_revision":1,"name":"Hijacked"}).status_code==404
        assert other.delete(f"/api/projects/{project_a}").status_code==404
        assert other.post(f"/api/projects/{project_a}/layout/preview",
                          json={"road_centerlines":[]}).status_code==404
        assert other.post(f"/api/projects/{project_a}/proposals",
                          json={"name":"Attack"}).status_code==404

        # Creating a raster for A must not create read/export/copilot access for B.
        aid=str(uuid.uuid4())
        report={"analysis_id":aid,"geometry":SITE,"created_at_utc":auth.iso(),
                "source":{"name":"Synthetic private raster - CI test only"},
                "metrics":{"site_area_ha":1.0},
                "slope_geojson":{"type":"FeatureCollection","features":[1]},
                "elevation_geojson":{"type":"FeatureCollection","features":[2]}}
        directory=main.job_dir(aid)
        main.save_report(directory,report)
        attach_analysis(data,project_a,report)
        assert admin_client.get(f"/api/analyses/{aid}").status_code==200
        assert [r["analysis_id"] for r in admin_client.get("/api/analyses").json()["analyses"]]==[aid]
        assert other.get("/api/analyses").json()["analyses"]==[]
        assert other.get(f"/api/analyses/{aid}").status_code==404
        assert other.get(f"/api/analyses/{aid}/report.md").status_code==404
        assert other.post("/api/copilot/assess",json={
            "analysis_id":aid,"question":"GPP minimum rumah teres"}).status_code==404
        assert other.post(f"/api/projects/{project_b}/activate-analysis",
                          json={"analysis_id":aid}).status_code==404
        assert other.post("/api/terrain/auto",json={
            "geometry":SITE,"project_id":project_a}).status_code==404
        upload=other.post("/api/terrain/upload",data={
            "project_id":project_a,"geometry":json.dumps(SITE),
            "source_name":"Attack sample","vertical_unit":"metres",
            "height_model":"DTM"}, files={"file":("bad.tif",b"X"*100,"image/tiff")})
        assert upload.status_code==404
        assert admin_client.get(f"/api/projects/{project_a}").json()["active_analysis_id"]==aid


def test_legacy_project_retained_but_invisible_until_offline_claim(monkeypatch,tmp_path):
    data,admin=bootstrap(monkeypatch,tmp_path)
    legacy=create_project(data,"Old Private Planning Site",geometry=SITE)
    with TestClient(main.app,base_url="https://testserver") as client:
        sign_in(client,"admin@example.test",ADMIN_PASSWORD)
        assert client.get("/api/projects").json()["projects"]==[]
        assert client.get(f"/api/projects/{legacy['id']}").status_code==404
        with sqlite3.connect(data/"planexus-workspace.sqlite3") as db:
            assert db.execute("SELECT owner_user_id FROM projects WHERE id=?",
                              (legacy["id"],)).fetchone()[0] is None
        assert auth.claim_legacy(data,"admin@example.test")==1
        restored=client.get(f"/api/projects/{legacy['id']}")
        assert restored.status_code==200
        assert shape(restored.json()["geometry"]).equals(shape(SITE))
        assert restored.json()["revision"]==legacy["revision"]
        assert auth.claim_legacy(data,"admin@example.test")==0


def test_login_attempt_limit(monkeypatch,tmp_path):
    bootstrap(monkeypatch,tmp_path)
    with TestClient(main.app,base_url="https://testserver") as client:
        for _ in range(auth.LOGIN_LIMIT):
            assert client.post("/api/auth/login",json={
                "email":"admin@example.test","password":"wrong-password"}).status_code==401
        assert client.post("/api/auth/login",json={
            "email":"admin@example.test","password":ADMIN_PASSWORD}).status_code==429
