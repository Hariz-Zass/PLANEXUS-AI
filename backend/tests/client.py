"""Legacy GIS regression client that authenticates through REAL auth routes.

Only imported by backend/tests. Production has NO session bypass. When a test
switches main.DATA_DIR, a new invite-free CI-only admin is created directly
in that isolated sqlite directory, and an ordinary login creates the cookie.
Security tests import fastapi.testclient.TestClient directly.
"""
from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient as RealTestClient
from app import auth
import app.main as main
from app.storage_health import check_storage

EMAIL = "fixture-planner@planexus.test"
PASSWORD = "CI-private-Only-2026-Strong-Pass"


class TestClient(RealTestClient):
    __test__ = False

    def __init__(self, *args, **kwargs):
        # The server correctly marks non-local-domain cookies Secure. Run
        # HTTPX's synthetic testserver over HTTPS, not insecure HTTP.
        kwargs.setdefault("base_url", "https://testserver")
        super().__init__(*args, **kwargs)
        self._workspace = ""
        self._csrf = ""

    def request(self, method, url, **kwargs):
        # Health checks must keep returning 503 when storage is deliberately
        # unavailable; never provision an account on that failed filesystem.
        target = str(Path(main.DATA_DIR).resolve())
        if self._workspace != target and check_storage(main.DATA_DIR)["ready"]:
            try:
                auth.create_user(main.DATA_DIR, EMAIL, "Synthetic CI Planner", PASSWORD, role="admin")
            except Exception as exc:
                from fastapi import HTTPException
                if not isinstance(exc, HTTPException) or exc.status_code != 409:
                    raise
            login = super().request("POST","/api/auth/login",
                                    json={"email":EMAIL,"password":PASSWORD})
            assert login.status_code == 200, login.text
            self._csrf = login.json()["csrf_token"]
            self._workspace = target
        if method.upper() in auth.MUTATION_METHODS and not str(url).startswith("/api/auth/"):
            headers = dict(kwargs.get("headers") or {})
            headers.setdefault("X-CSRF-Token", self._csrf)
            kwargs["headers"] = headers
        return super().request(method,url,**kwargs)
