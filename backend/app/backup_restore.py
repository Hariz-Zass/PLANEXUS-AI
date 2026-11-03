"""Verify and restore PLANEXUS single-node SQLite + GIS backup bundles.

Offline administration ONLY. Restore refuses any existing destination, validates
every file digest, checks SQLite integrity and ensures each linked analysis has a
report and its source raster before making a new data directory visible.

This is a private, unencrypted archive. Never serve it from FastAPI or commit it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

DB_NAME = "planexus-workspace.sqlite3"
MANIFEST_NAME = "BACKUP-MANIFEST.json"
FORMAT_VERSION = 2
MAX_FILE_COUNT = 10_000
MAX_TOTAL_BYTES = 20 * 1024 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024 * 1024


def sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            count += len(chunk)
            digest.update(chunk)
    return count, digest.hexdigest()


def _archive_name(value: str) -> bool:
    """Strict archive layout: DB, manifest, or one file under a UUID jobs dir."""
    if not value or "\\" in value or "//" in value or "\x00" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        return False
    if value in (DB_NAME, MANIFEST_NAME):
        return True
    if len(path.parts) != 3 or path.parts[0] != "jobs":
        return False
    try:
        if str(uuid.UUID(path.parts[1])) != path.parts[1]:
            return False
    except (ValueError, TypeError):
        return False
    filename = path.parts[2]
    return (
        filename == "result.json"
        or (
            filename != "" and not filename.startswith(".")
            and path.suffix.lower() in (".json", ".tif", ".tiff")
        )
    )


def _db_integrity(db_path: Path, manifest: dict[str, Any], archive_names: set[str],
                  reports: dict[str, dict[str, Any]]) -> dict[str, int]:
    """A SQLite snapshot must not refer to missing/mislabelled raster evidence."""
    try:
        with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
            check = conn.execute("PRAGMA integrity_check").fetchone()
            if check is None or check[0] != "ok":
                raise RuntimeError("SQLite integrity check failed.")
            count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            if count != manifest["project_count"]:
                raise RuntimeError("Project count differs from backup manifest.")
            refs = conn.execute(
                "SELECT project_id,analysis_id FROM project_analyses"
            ).fetchall()
            active = conn.execute(
                "SELECT id,active_analysis_id FROM projects "
                "WHERE active_analysis_id IS NOT NULL"
            ).fetchall()
            proposals = conn.execute("SELECT COUNT(*) FROM project_proposals").fetchone()[0]
            layouts = conn.execute("SELECT COUNT(*) FROM project_layouts").fetchone()[0]
            linked = {(project, analysis) for project, analysis in refs}
            if any((project, analysis) not in linked for project, analysis in active):
                raise RuntimeError("An active project analysis is not linked in SQLite.")
            for project, analysis_id in refs:
                report_path = f"jobs/{analysis_id}/result.json"
                if report_path not in archive_names:
                    raise RuntimeError("Linked GIS report missing from backup: " + analysis_id)
                report = reports.get(report_path)
                if report is None or report.get("analysis_id") != analysis_id:
                    raise RuntimeError("Saved GIS report ID does not match SQLite: " + analysis_id)
                prefix = f"jobs/{analysis_id}/"
                if not any(
                    name.startswith(prefix) and name.lower().endswith((".tif", ".tiff"))
                    for name in archive_names
                ):
                    raise RuntimeError("Source raster is missing for analysis: " + analysis_id)
            return {"projects": count, "analyses": len(refs),
                    "proposals": proposals, "layouts": layouts}
    except (sqlite3.Error, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Backup SQLite/manifest is invalid: " + type(exc).__name__) from exc


def verify_backup(archive_path: Path) -> dict[str, Any]:
    """Read and checksum EVERY archive member and cross-check project->GIS links."""
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.is_file():
        raise RuntimeError("Backup archive does not exist.")
    try:
        with zipfile.ZipFile(archive_path, "r") as bundle:
            infos = bundle.infolist()
            if not 2 <= len(infos) <= MAX_FILE_COUNT + 2:
                raise RuntimeError("Unexpected backup member count.")
            names = [item.filename for item in infos]
            if len(names) != len(set(names)):
                raise RuntimeError("Duplicate archive paths are unsafe.")
            if not all(_archive_name(name) for name in names):
                raise RuntimeError("Unexpected or unsafe archive member path.")
            if any(
                item.is_dir()
                or (stat.S_IFMT((item.external_attr >> 16) & 0xFFFF)
                    not in (0, stat.S_IFREG))
                for item in infos
            ):
                raise RuntimeError("Backup must contain only regular files (no links).")
            if sum(item.file_size for item in infos) > MAX_TOTAL_BYTES or any(
                item.file_size > MAX_FILE_BYTES for item in infos
            ):
                raise RuntimeError("Backup exceeds safety limits.")
            if DB_NAME not in names or MANIFEST_NAME not in names:
                raise RuntimeError("Backup requires SQLite and a manifest.")
            if bundle.getinfo(MANIFEST_NAME).file_size > 4 * 1024 * 1024:
                raise RuntimeError("Backup manifest exceeds 4 MiB inspection limit.")
            manifest = json.loads(bundle.read(MANIFEST_NAME))
            if not isinstance(manifest, dict) or manifest.get("format_version") != FORMAT_VERSION:
                raise RuntimeError("Legacy/unknown archive format: only checksummed v2 can be restored.")
            assets = manifest.get("files")
            if not isinstance(assets, dict) or set(assets) != set(names) - {MANIFEST_NAME}:
                raise RuntimeError("Manifest does not list exactly every archived asset.")
            if manifest.get("gis_files_archived") != len(assets) - 1:
                raise RuntimeError("Manifest asset count mismatch.")

            reports: dict[str, dict[str, Any]] = {}
            with tempfile.TemporaryDirectory(prefix="planexus-verify-") as temp:
                db_copy = Path(temp) / DB_NAME
                for member in infos:
                    if member.filename == MANIFEST_NAME:
                        continue
                    expected = assets[member.filename]
                    if not isinstance(expected, dict):
                        raise RuntimeError("Malformed backup manifest file metadata.")
                    digest = hashlib.sha256()
                    size = 0
                    with bundle.open(member, "r") as src:
                        dst = db_copy.open("wb") if member.filename == DB_NAME else None
                        try:
                            report_buf = bytearray() if member.filename.endswith("/result.json") else None
                            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                                size += len(chunk)
                                digest.update(chunk)
                                if dst:
                                    dst.write(chunk)
                                if report_buf is not None:
                                    if len(report_buf) + len(chunk) > 64 * 1024 * 1024:
                                        raise RuntimeError("GIS report exceeds 64 MiB inspection limit.")
                                    report_buf.extend(chunk)
                        finally:
                            if dst:
                                dst.close()
                    if size != expected.get("size") or digest.hexdigest() != expected.get("sha256"):
                        raise RuntimeError("Backup asset failed SHA-256 validation: " + member.filename)
                    if report_buf is not None:
                        try:
                            report = json.loads(report_buf)
                            if not isinstance(report, dict):
                                raise ValueError("not a report object")
                            reports[member.filename] = report
                        except (ValueError, UnicodeDecodeError) as exc:
                            raise RuntimeError("Invalid GIS report JSON in archive: " + member.filename) from exc
                counts = _db_integrity(db_copy, manifest, set(assets), reports)
            return {
                "verified": True, "format_version": FORMAT_VERSION,
                "project_count": counts["projects"], "analysis_count": counts["analyses"],
                "proposal_count": counts["proposals"], "layout_count": counts["layouts"],
                "file_count": len(assets), "sha256_verified": True,
                "private_unencrypted": True,
            }
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Backup is invalid or cannot be read: " + type(exc).__name__) from exc


def restore_backup(archive_path: Path, destination: Path) -> dict[str, Any]:
    """OFFLINE restore to a NEW folder only. No overwrite, no merge, no deletion.

    Caller must stop the API and point it to the resulting data directory.
    A mounted /data directory itself cannot be atomically replaced while live.
    """
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise RuntimeError("Restore destination must not exist. Refusing to overwrite any live project.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = verify_backup(archive_path)
    stage = Path(tempfile.mkdtemp(prefix=".planexus-restore-", dir=destination.parent))
    try:
        os.chmod(stage, 0o700)
        with zipfile.ZipFile(archive_path, "r") as bundle:
            for name in sorted(bundle.namelist()):
                if name == MANIFEST_NAME:
                    continue
                target = stage.joinpath(*PurePosixPath(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(name) as src, target.open("xb") as out:
                    shutil.copyfileobj(src, out, length=1024 * 1024)
                    out.flush()
                    os.fsync(out.fileno())
                os.chmod(target, 0o600)
        # Re-audit on-disk DB before a single atomic directory publication.
        with sqlite3.connect(stage / DB_NAME) as con:
            # A restored/off-site backup must never bring old browser sessions
            # or unused invitation links back to life on a replacement host.
            tables = {row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if "auth_sessions" in tables:
                con.execute("DELETE FROM auth_sessions")
            if "registration_invites" in tables:
                con.execute("DELETE FROM registration_invites WHERE used_by IS NULL")
            con.commit()
            check = con.execute("PRAGMA integrity_check").fetchone()
            if check is None or check[0] != "ok":
                raise RuntimeError("Restored SQLite failed post-extraction integrity check.")
        if destination.exists():
            raise RuntimeError("Destination appeared during restore; refusing overwrite.")
        os.rename(stage, destination)
        return {**result, "restored": True, "destination": str(destination)}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify or restore PLANEXUS v2 GIS backup (offline admin tool)"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--archive", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    result = (
        verify_backup(args.archive)
        if args.command == "verify"
        else restore_backup(args.archive, args.destination)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
