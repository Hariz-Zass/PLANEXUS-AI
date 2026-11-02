"""Local workspace archive: consistent DB snapshot, GIS assets and no accidental key files."""
from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from app.backup import create_backup
from app.project_store import create_project


def test_backup_contains_sqlite_snapshot_and_report_files(tmp_path):
    data = tmp_path / "data"
    projects=create_project(data,"Backup Test Project")
    analysis=data/"jobs"/"12345678-1234-4234-8234-123456789abc"
    analysis.mkdir(parents=True)
    (analysis/"result.json").write_text('{"source":"synthetic backup test"}',encoding="utf-8")
    (analysis/"source_clipped.tif").write_bytes(b"TEST RASTER BYTES - NOT A REAL TIFF")
    (analysis/"secret.env").write_text("NEVER BACK UP THIS FILE",encoding="utf-8")
    zip_path=create_backup(data,tmp_path/"backups")
    assert zip_path.is_file() and zip_path.stat().st_size>200
    with zipfile.ZipFile(zip_path) as archive:
        names=archive.namelist()
        assert "planexus-workspace.sqlite3" in names
        assert "BACKUP-MANIFEST.json" in names
        assert any(name.endswith("/result.json") for name in names)
        assert any(name.endswith("/source_clipped.tif") for name in names)
        assert not any(name.endswith(".env") for name in names)
        manifest=json.loads(archive.read("BACKUP-MANIFEST.json"))
        assert manifest["project_count"]==1
        assert manifest["gis_files_archived"]==2
        db_path=tmp_path/"restored.sqlite3"
        db_path.write_bytes(archive.read("planexus-workspace.sqlite3"))
    with sqlite3.connect(db_path) as db:
        row=db.execute("SELECT name FROM projects WHERE id=?",(projects["id"],)).fetchone()
        assert row[0]=="Backup Test Project"


def test_backup_refuses_to_archive_inside_data_and_missing_projects(tmp_path):
    data=tmp_path/"data"
    with pytest.raises(RuntimeError):
        create_backup(data,tmp_path/"backups")
    create_project(data,"Second Project")
    with pytest.raises(RuntimeError):
        create_backup(data,data/"backup")
