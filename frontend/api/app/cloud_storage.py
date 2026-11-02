"""Browser-keyed private Blob snapshots for PLANEXUS on Vercel.

Access is tied to an unguessable browser-held key, NOT a full user-account
system. SQLite and derived report JSON are snapshotted; raw TIFF files are not.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import io
import os
import re
import sqlite3
import tempfile
import zipfile
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

CURRENT_DATA_DIR: ContextVar[Path | None] = ContextVar("planexus_active_dir", default=None)
LOCK = asyncio.Lock()
WORKSPACE_KEY = re.compile(r"^[A-Za-z0-9_-]{43,96}$")
REPORT_FILE = re.compile(r"jobs/[0-9a-f-]{36}/result\.json")
PUBLIC_PATHS = frozenset({"/api/health", "/api/sources", "/api/policy/catalog", "/api/policy/assess", "/api/copilot/capabilities"})
MAX_STORED_BYTES = 48 * 1024 * 1024
MAX_UNPACKED_BYTES = 75 * 1024 * 1024


def cloud_enabled() -> bool:
    return os.getenv("PLANEXUS_CLOUD_STORAGE", "").lower() == "blob"


def workspace_dir(fallback: Path) -> Path:
    return CURRENT_DATA_DIR.get() or fallback


def _client() -> Any:
    from vercel.blob import AsyncBlobClient
    return AsyncBlobClient()


def _location(key: str) -> str:
    return "planexus/workspaces/v1/" + hashlib.sha256(key.encode("ascii")).hexdigest() + "/snapshot.zip"


def _snapshot(root: Path) -> bytes:
    database = root / "planexus-workspace.sqlite3"
    if database.exists():
        with sqlite3.connect(database) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        if database.is_file():
            archive.write(database, "planexus-workspace.sqlite3")
        for report in sorted((root / "jobs").glob("*/result.json")):
            relative = report.relative_to(root).as_posix()
            if REPORT_FILE.fullmatch(relative) and report.is_file():
                archive.write(report, relative)
    payload = memory.getvalue()
    if len(payload) > MAX_STORED_BYTES:
        raise ValueError("Workspace archive too large")
    return payload


def _restore(root: Path, payload: bytes) -> None:
    if len(payload) > MAX_STORED_BYTES:
        raise ValueError("Workspace archive too large")
    total = 0
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for entry in archive.infolist():
            path = entry.filename
            if path != "planexus-workspace.sqlite3" and not REPORT_FILE.fullmatch(path):
                raise ValueError("Unexpected workspace archive entry")
            total += entry.file_size
            if total > MAX_UNPACKED_BYTES or entry.is_dir():
                raise ValueError("Invalid workspace archive size/type")
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(entry))


async def _read(client: Any, pathname: str) -> tuple[bytes | None, str | None]:
    opts: dict[str, Any] = {"access": "private"}
    if "use_cache" in inspect.signature(client.get).parameters:
        opts["use_cache"] = False
    obj = await client.get(pathname, **opts)
    if obj is None:
        return None, None
    if getattr(obj, "status_code", 200) != 200:
        raise ValueError("Unexpected storage status")
    chunks: list[bytes] = []
    size = 0
    async for chunk in obj.stream:
        size += len(chunk)
        if size > MAX_STORED_BYTES:
            raise ValueError("Stored workspace exceeds limit")
        chunks.append(chunk)
    return b"".join(chunks), obj.blob.etag


async def _write(client: Any, pathname: str, archive: bytes, etag: str | None) -> None:
    options: dict[str, Any] = {"access": "private", "content_type": "application/zip"}
    options.update({"overwrite": True, "if_match": etag} if etag else {"overwrite": False})
    await client.put(pathname, archive, **options)


async def private_workspace(request: Request, call_next: Any) -> Any:
    if not cloud_enabled() or not request.url.path.startswith("/api/") or request.url.path in PUBLIC_PATHS:
        return await call_next(request)
    key = request.headers.get("x-planexus-workspace", "")
    if not WORKSPACE_KEY.fullmatch(key):
        return JSONResponse({"detail": "No personal workspace access key in this browser."}, status_code=401)
    if not (os.getenv("BLOB_READ_WRITE_TOKEN") or os.getenv("VERCEL_OIDC_TOKEN")):
        return JSONResponse({"detail": "Private GIS storage is not configured. Nothing was saved."}, status_code=503)
    async with LOCK:
        with tempfile.TemporaryDirectory(prefix="planexus-workspace-", dir="/tmp") as temporary:
            root = Path(temporary)
            context = CURRENT_DATA_DIR.set(root)
            try:
                client = _client()
                location = _location(key)
                payload, etag = await _read(client, location)
                if payload is not None:
                    _restore(root, payload)
                response = await call_next(request)
                if request.method in ("POST", "PUT", "PATCH", "DELETE") and response.status_code < 400:
                    await _write(client, location, _snapshot(root), etag)
                return response
            except Exception:
                return JSONResponse({
                    "detail": "Private cloud workspace could not be read or confirmed saved. Reload and retry; data changes were not confirmed."
                }, status_code=503)
            finally:
                CURRENT_DATA_DIR.reset(context)
