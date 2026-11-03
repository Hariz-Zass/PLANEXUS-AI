"""Unprivileged CI smoke of a real Docker named-volume GIS backend.

No external DEM is downloaded and no Vercel deployment is performed.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:18000"
MARKER = Path("/tmp/planexus_ci_project_record.json")


def get(path: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=3) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def mode_wait() -> None:
    for _ in range(90):
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
    request = urllib.request.Request(
        BASE + "/api/projects", method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"name": "Persist after container replacement"}).encode(),
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 201
        project = json.load(response)
    assert project["revision"] == 1
    MARKER.write_text(json.dumps({"id": project["id"], "revision": project["revision"]}))
    print("Created project on mounted volume:", project["id"])


def mode_verify() -> None:
    status, health = get("/api/health")
    assert status == 200 and health["persistent"] is True, health
    expected = json.loads(MARKER.read_text())
    status, project = get("/api/projects/" + expected["id"])
    assert status == 200, project
    assert project["name"] == "Persist after container replacement"
    assert project["revision"] == expected["revision"]
    print("Project survived container replacement:", project["id"])


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
