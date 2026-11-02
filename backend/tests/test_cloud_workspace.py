"""Isolated persistent cloud workspaces use fake Blob: no network or secrets."""
import io
import zipfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import cloud_storage

A = "A" * 43
B = "B" * 43


class MemoryBlob:
    def __init__(self):
        self.data = {}
        self.version = 0

    async def get(self, pathname, *, access, use_cache=False):
        assert access == "private"
        if pathname not in self.data:
            return None
        content, etag = self.data[pathname]
        async def stream():
            yield content
        return SimpleNamespace(status_code=200, stream=stream(),
                               blob=SimpleNamespace(etag=etag))

    async def put(self, pathname, content, *, access, content_type,
                  overwrite=False, if_match=None):
        assert access == "private"
        existing = self.data.get(pathname)
        if existing and (not overwrite or if_match != existing[1]):
            raise ValueError("stale ETag")
        self.version += 1
        self.data[pathname] = content, str(self.version)


def test_private_workspace_persists_and_isolates_users(monkeypatch):
    blob = MemoryBlob()
    monkeypatch.setenv("PLANEXUS_CLOUD_STORAGE", "blob")
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "test-not-a-secret")
    monkeypatch.setattr(cloud_storage, "_client", lambda: blob)
    client = TestClient(main.app)
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/policy/catalog").status_code == 200
    assert client.get("/api/projects").status_code == 401
    headers_a = {"X-Planexus-Workspace": A}
    headers_b = {"X-Planexus-Workspace": B}
    first = client.post("/api/projects", json={"name": "Private planning site"}, headers=headers_a)
    assert first.status_code == 201, first.text
    pid = first.json()["id"]
    assert client.get("/api/projects", headers=headers_a).json()["projects"][0]["id"] == pid
    assert client.get("/api/projects", headers=headers_b).json()["projects"] == []
    assert client.get("/api/projects/" + pid, headers=headers_b).status_code == 404
    assert client.get("/api/projects/" + pid, headers=headers_a).status_code == 200
    archive = blob.data[cloud_storage._location(A)][0]
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        assert "planexus-workspace.sqlite3" in z.namelist()
    assert A not in str(blob.data.keys())


def test_config_failure_does_not_claim_success(monkeypatch):
    monkeypatch.setenv("PLANEXUS_CLOUD_STORAGE", "blob")
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    client = TestClient(main.app)
    assert client.get("/api/health").json()["status"] == "degraded"
    response = client.post("/api/projects", json={"name": "No persist"},
                           headers={"X-Planexus-Workspace": A})
    assert response.status_code == 503


def test_archive_rejects_traversal(tmp_path):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        z.writestr("../leaked.txt", "bad")
    with pytest.raises(ValueError, match="Unexpected"):
        cloud_storage._restore(tmp_path, data.getvalue())
