"""Durable local project workspace: SQLite metadata + existing raster/report files.

Not an authenticated multi-user or cloud service. The entire backend must remain
bound to localhost until authorization, tenancy and storage are implemented.
All SQL values use parameters; project IDs are validated UUIDs.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from fastapi import HTTPException
from shapely.geometry import shape

from .geometry import area_km2, validate_site


_UNSET = object()
MAX_PROJECTS_LOCAL = 200


def _uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, "ID projek tidak sah.") from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _label(name: str) -> str:
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 100:
        raise HTTPException(422, "Nama projek perlu 2–100 aksara.")
    return name.strip()


def _description(value: str | None) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > 500:
        raise HTTPException(422, "Penerangan projek tidak boleh melebihi 500 aksara.")
    return value.strip()


def _json_geometry(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(validate_site(value), sort_keys=True, separators=(",", ":"))


@contextmanager
def connection(data_dir: Path) -> Iterator[sqlite3.Connection]:
    data_dir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(data_dir / "planexus-workspace.sqlite3", timeout=15)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA journal_mode=WAL")
        with db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                site_geometry TEXT,
                active_analysis_id TEXT,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS project_analyses (
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                analysis_id TEXT NOT NULL UNIQUE,
                created_at_utc TEXT NOT NULL,
                source_name TEXT NOT NULL,
                site_area_ha REAL NOT NULL,
                PRIMARY KEY (project_id, analysis_id)
            );
            CREATE INDEX IF NOT EXISTS ix_project_analyses_project
                ON project_analyses(project_id, created_at_utc DESC);
            """)
        yield db
    finally:
        db.close()


def _summary(row: sqlite3.Row) -> dict[str, Any]:
    geometry = json.loads(row["site_geometry"]) if row["site_geometry"] else None
    return {
        "id": row["id"], "name": row["name"], "description": row["description"],
        "has_site": geometry is not None,
        "site_area_ha": round(area_km2(geometry) * 100, 3) if geometry else None,
        "active_analysis_id": row["active_analysis_id"],
        "revision": row["revision"], "created_at_utc": row["created_at_utc"],
        "updated_at_utc": row["updated_at_utc"],
    }


def list_projects(data_dir: Path) -> list[dict[str, Any]]:
    with connection(data_dir) as db:
        rows = db.execute("SELECT * FROM projects ORDER BY updated_at_utc DESC, rowid DESC LIMIT ?", (MAX_PROJECTS_LOCAL,)).fetchall()
        return [_summary(row) for row in rows]


def get_project(data_dir: Path, project_id: str) -> dict[str, Any]:
    project_id = _uuid(project_id)
    with connection(data_dir) as db:
        row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Projek tidak ditemui.")
        analyses = db.execute(
            "SELECT analysis_id,created_at_utc,source_name,site_area_ha "
            "FROM project_analyses WHERE project_id=? ORDER BY created_at_utc DESC LIMIT 100",
            (project_id,),
        ).fetchall()
        summary = _summary(row)
        summary["geometry"] = json.loads(row["site_geometry"]) if row["site_geometry"] else None
        summary["analyses"] = [dict(item) for item in analyses]
        return summary


def create_project(data_dir: Path, name: str, description: str = "", geometry: dict[str, Any] | None = None) -> dict[str, Any]:
    value, info, encoded = _label(name), _description(description), _json_geometry(geometry)
    project_id = str(uuid.uuid4())
    now = _now()
    with connection(data_dir) as db:
        with db:
            count = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            if count >= MAX_PROJECTS_LOCAL:
                raise HTTPException(422, "Had 200 projek lokal dicapai. Arkib projek lama dahulu.")
            db.execute(
                "INSERT INTO projects(id,name,description,site_geometry,created_at_utc,updated_at_utc)"
                " VALUES(?,?,?,?,?,?)",
                (project_id, value, info, encoded, now, now),
            )
    return get_project(data_dir, project_id)


def update_project(
    data_dir: Path, project_id: str, expected_revision: int,
    *, name: Any = _UNSET, description: Any = _UNSET, geometry: Any = _UNSET,
) -> dict[str, Any]:
    project_id = _uuid(project_id)
    if expected_revision < 1:
        raise HTTPException(422, "Revision projek tidak sah.")
    label = _label(name) if name is not _UNSET else _UNSET
    info = _description(description) if description is not _UNSET else _UNSET
    encoded = _json_geometry(geometry) if geometry is not _UNSET else _UNSET
    with connection(data_dir) as db:
        with db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Projek tidak ditemui.")
            if row["revision"] != expected_revision:
                raise HTTPException(409, "Projek telah berubah dalam tab lain. Buka semula projek sebelum menyimpan.")
            new_geometry = row["site_geometry"] if encoded is _UNSET else encoded
            boundary_changed = encoded is not _UNSET and new_geometry != row["site_geometry"]
            db.execute(
                "UPDATE projects SET name=?,description=?,site_geometry=?,active_analysis_id=?,"
                "revision=revision+1,updated_at_utc=? WHERE id=?",
                (
                    row["name"] if label is _UNSET else label,
                    row["description"] if info is _UNSET else info,
                    new_geometry,
                    None if boundary_changed else row["active_analysis_id"],
                    _now(), project_id,
                ),
            )
    return get_project(data_dir, project_id)


def remove_project(data_dir: Path, project_id: str) -> None:
    """Remove only the project index. Reports/raster artifacts are retained to avoid data loss."""
    project_id = _uuid(project_id)
    with connection(data_dir) as db:
        with db:
            deleted = db.execute("DELETE FROM projects WHERE id=?", (project_id,)).rowcount
            if not deleted:
                raise HTTPException(404, "Projek tidak ditemui.")


def attach_analysis(data_dir: Path, project_id: str, report: dict[str, Any]) -> dict[str, Any]:
    """Save analysis association only when the report geometry matches the active project site.

    This prevents a delayed DEM job from silently switching a different site.
    """
    project_id = _uuid(project_id)
    analysis_id = _uuid(report["analysis_id"])
    encoded = _json_geometry(report["geometry"])
    with connection(data_dir) as db:
        with db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Projek tidak ditemui.")
            if row["site_geometry"] is not None and row["site_geometry"] != encoded:
                raise HTTPException(409, "Sempadan projek telah berubah; analisis ini tidak dipautkan ke tapak lain.")
            db.execute(
                "INSERT INTO project_analyses(project_id,analysis_id,created_at_utc,source_name,site_area_ha)"
                " VALUES(?,?,?,?,?)",
                (
                    project_id, analysis_id, report["created_at_utc"],
                    report["source"]["name"], report["metrics"]["site_area_ha"],
                ),
            )
            db.execute(
                "UPDATE projects SET site_geometry=?,active_analysis_id=?,revision=revision+1,"
                "updated_at_utc=? WHERE id=?",
                (encoded, analysis_id, _now(), project_id),
            )
    return get_project(data_dir, project_id)


def activate_analysis(data_dir: Path, project_id: str, analysis_id: str, report: dict[str, Any]) -> dict[str, Any]:
    project_id, analysis_id = _uuid(project_id), _uuid(analysis_id)
    encoded = _json_geometry(report["geometry"])
    with connection(data_dir) as db:
        with db:
            exists = db.execute(
                "SELECT 1 FROM project_analyses WHERE project_id=? AND analysis_id=?",
                (project_id, analysis_id),
            ).fetchone()
            if exists is None:
                raise HTTPException(404, "Analisis ini tidak dipautkan kepada projek berkenaan.")
            db.execute(
                "UPDATE projects SET site_geometry=?,active_analysis_id=?,revision=revision+1,"
                "updated_at_utc=? WHERE id=?",
                (encoded, analysis_id, _now(), project_id),
            )
    return get_project(data_dir, project_id)
