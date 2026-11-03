"""Unprivileged CI smoke of a real Docker named-volume GIS backend.

No external DEM is downloaded and no Vercel deployment is performed.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:18000"
MARKER = Path("/tmp/planexus_ci_project_record.json")
EMAIL = "ci-volume@planexus.test"
PASSWORD = "Synthetic-Docker-CI-2026!"
SESSION_COOKIE = ""
CSRF_TOKEN = ""

# Executed INSIDE the actual built GIS container. The raster, report and
# SQLite association are written on the named /data volume and re-read after
# the entire container is destroyed and replaced with a new one.
MAKE_RASTER_REPORT = r"""
import json,sys,uuid
import numpy as np,rasterio
from pathlib import Path
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import Polygon,mapping
from shapely.ops import transform
from app.terrain import analyze_terrain
from app.main import save_report
from app.project_store import attach_analysis

project_id=sys.argv[1]
analysis_id=str(uuid.uuid4())
folder=Path("/data/jobs")/analysis_id
folder.mkdir(parents=True,exist_ok=True)
raster=folder/"source_clipped.tif"
row,col=np.indices((120,120))
heights=(25+col*.25+row*.15).astype("float32")
with rasterio.open(raster,"w",driver="GTiff",width=120,height=120,
                   count=1,dtype="float32",crs="EPSG:32647",
                   nodata=-9999.,transform=from_origin(720000,520000,10,10)) as ds:
    ds.write(heights,1)
to_wgs=Transformer.from_crs("EPSG:32647","EPSG:4326",always_xy=True)
site=Polygon([(720200,519800),(721000,519800),
              (721000,519000),(720200,519000)])
geo=mapping(transform(to_wgs.transform,site))
source={"id":"docker-synthetic","name":"SYNTHETIC Docker CI terrain",
        "publisher":"CI test only","data_type":"DTM",
        "nominal_resolution_m":10,"verified":"synthetic not field/survey",
        "vertical_datum":"synthetic","vertical_unit":"metres"}
report=analyze_terrain(geo,raster,source,analysis_id)
assert report["slope_geojson"]["features"]
assert report["elevation_geojson"]["features"]
save_report(folder,report)
project=attach_analysis(Path("/data"),project_id,report)
print(json.dumps({"analysis_id":analysis_id,"revision":project["revision"]}))
"""



def get(path: str) -> tuple[int, dict]:
    headers = {"Cookie": SESSION_COOKIE} if SESSION_COOKIE else {}
    request = urllib.request.Request(BASE + path, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def login() -> None:
    global SESSION_COOKIE, CSRF_TOKEN
    request = urllib.request.Request(
        BASE+"/api/auth/login",method="POST",
        headers={"Content-Type":"application/json"},
        data=json.dumps({"email":EMAIL,"password":PASSWORD}).encode(),
    )
    with urllib.request.urlopen(request,timeout=10) as response:
        assert response.status == 200
        SESSION_COOKIE = response.headers["Set-Cookie"].split(";",1)[0]
        CSRF_TOKEN = json.load(response)["csrf_token"]
    assert SESSION_COOKIE.startswith("planexus_session=") and CSRF_TOKEN


def mode_wait() -> None:
    for attempt in range(45):
        if attempt >= 3:
            probe=subprocess.run(["docker","inspect","--format","{{.State.Running}}","planexus-ci-api"],
                                 capture_output=True, text=True, check=False)
            if probe.returncode == 0 and probe.stdout.strip() == "false":
                logs=subprocess.run(["docker","logs","--tail","100","planexus-ci-api"],
                                    capture_output=True,text=True,check=False)
                raise AssertionError("FastAPI container exited on startup: " + logs.stdout + logs.stderr)
        try:
            status, result = get("/api/health")
            if status in (200, 503):
                return
        except (OSError, ValueError):
            pass
        time.sleep(2)
    raise AssertionError("Backend never responded to health.")


def mode_create() -> None:
    status, health = get("/api/health")
    assert status == 200 and health["persistent"] is True, health
    # Create the identity through the REAL backend API's account library;
    # login uses the actual Cookie + CSRF, with no authorization bypass.
    seed = subprocess.run([
        "docker","exec","planexus-ci-api","python","-c",
        "from app.auth import create_user; from app.settings import DATA_DIR;"
        "create_user(DATA_DIR,'ci-volume@planexus.test','Synthetic Volume Planner',"
        "'Synthetic-Docker-CI-2026!',role='admin')"
    ],capture_output=True,text=True,timeout=20,check=False)
    assert seed.returncode == 0, seed.stdout+seed.stderr
    login()
    request = urllib.request.Request(
        BASE + "/api/projects", method="POST",
        headers={"Content-Type": "application/json",
                 "Cookie":SESSION_COOKIE,"X-CSRF-Token":CSRF_TOKEN},
        data=json.dumps({"name": "Persist after container replacement"}).encode(),
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 201
        project = json.load(response)
    assert project["revision"] == 1
    result = subprocess.run(
        ["docker","exec","planexus-ci-api","python","-c",MAKE_RASTER_REPORT,project["id"]],
        capture_output=True, text=True, check=False, timeout=50
    )
    if result.returncode != 0:
        raise AssertionError("GIS synthetic raster write failed: "+result.stdout+result.stderr)
    produced = json.loads(result.stdout.splitlines()[-1])
    MARKER.write_text(json.dumps({"id": project["id"], "revision": produced["revision"],
                                  "analysis_id": produced["analysis_id"]}))
    print("Project, analysed raster and report saved on mounted volume:",project["id"])


def mode_verify() -> None:
    status, health = get("/api/health")
    assert status == 200 and health["persistent"] is True, health
    expected = json.loads(MARKER.read_text())
    login()  # Fresh session issued from the persisted users table after restart.
    status, project = get("/api/projects/" + expected["id"])
    assert status == 200, project
    assert project["name"] == "Persist after container replacement"
    assert project["revision"] == expected["revision"]
    assert project["active_analysis_id"] == expected["analysis_id"]
    assert project["geometry"] is not None and len(project["analyses"]) == 1
    status, report = get("/api/analyses/" + expected["analysis_id"])
    assert status == 200, report
    assert report["slope_geojson"]["features"]
    assert report["elevation_geojson"]["features"]
    assert report["source"]["id"] == "docker-synthetic"
    verify_files = subprocess.run([
        "docker","exec","planexus-ci-api","python","-c",
        "import sys,rasterio;from pathlib import Path;"
        "p=Path('/data/jobs')/sys.argv[1];"
        "assert (p/'result.json').is_file();"
        "ds=rasterio.open(p/'source_clipped.tif');"
        "assert ds.width==120 and ds.crs.to_epsg()==32647;ds.close();",
        expected["analysis_id"]
    ], capture_output=True, text=True, check=False, timeout=20)
    assert verify_files.returncode == 0, verify_files.stdout+verify_files.stderr
    print("Project, real raster file, saved report and both map layers survived container replacement:",project["id"])


def mode_unmounted() -> None:
    for _ in range(60):
        try:
            code, body = get("/api/health")
            if code == 503:
                assert body["storage"] == "required_volume_missing", body
                print("Unprotected container layer correctly rejected")
                return
        except (OSError, ValueError):
            pass
        time.sleep(2)
    raise AssertionError("Unmounted container did not refuse ephemeral storage")


if __name__ == "__main__":
    options = {"wait": mode_wait, "create": mode_create,
               "verify": mode_verify, "unmounted": mode_unmounted}
    options[sys.argv[1]]()
