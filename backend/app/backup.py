"""Safe portable local backup of PLANEXUS projects and GIS evidence.

Uses SQLite's online backup API for a transactionally consistent database
snapshot, then archives generated GIS job files. This is a *local* backup;
never upload these files to a public repository.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
import zipfile
from .backup_restore import FORMAT_VERSION, DB_NAME, sha256_file, verify_backup
from .gis_lock import data_lock
from .storage_health import check_storage, require_persistent_volume
from datetime import datetime, timezone
from pathlib import Path

from .settings import DATA_DIR


def create_backup(data_dir: Path, output_dir: Path) -> Path:
    """Verified, atomic private snapshot coordinated with API GIS writes."""
    data_dir = data_dir.expanduser().resolve()
    if require_persistent_volume() and not check_storage(data_dir)["ready"]:
        raise RuntimeError("Persistent data volume missing. Automatic backup refused.")
    # Covers the entire SQLite snapshot AND all raster/file reads.
    with data_lock(data_dir, timeout_s=300):
        return _create_locked_backup(data_dir, output_dir)


def _create_locked_backup(data_dir: Path, output_dir: Path) -> Path:
    data_dir = data_dir.expanduser().resolve()
    database = data_dir / "planexus-workspace.sqlite3"
    if not database.is_file():
        raise RuntimeError(
            "Tiada database projek dijumpai. Cipta sekurang-kurangnya satu projek dahulu. "
            "Pastikan PLANEXUS_DATA_DIR menunjuk ke folder backend yang betul."
        )
    output_dir = output_dir.expanduser().resolve()
    if output_dir == data_dir or data_dir in output_dir.parents:
        raise RuntimeError("Folder backup mesti di luar folder data projek.")
    output_dir.mkdir(parents=True, exist_ok=True)
    name = "PLANEXUS-backup-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + ".zip"
    output = output_dir / name
    partial = output.with_suffix(".partial")
    jobs_dir = data_dir / "jobs"

    with tempfile.TemporaryDirectory(prefix="planexus-sqlite-snapshot-") as tmp:
        snapshot = Path(tmp) / "planexus-workspace.sqlite3"
        # The source may use WAL; sqlite.backup captures committed changes safely.
        with sqlite3.connect(database, timeout=20) as source, sqlite3.connect(snapshot) as dest:
            source.backup(dest)
        with sqlite3.connect(snapshot) as verify:
            check = verify.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise RuntimeError("Pemeriksaan integriti SQLite gagal. Backup dibatalkan.")
            project_count = verify.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

        try:
            # Restrict permissions from creation (no world-readable private
            # site snapshots) and never expose an incomplete *.zip archive.
            fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as target:
                with zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_DEFLATED,
                                     compresslevel=5, allowZip64=True) as archive:
                    archive.write(snapshot, arcname=DB_NAME)
                    count, digest = sha256_file(snapshot)
                    recorded_files = {DB_NAME: {"size": count, "sha256": digest}}
                    archived_jobs = 0
                    root = jobs_dir.resolve()
                    if jobs_dir.is_dir():
                        for file in sorted(jobs_dir.rglob("*")):
                            if not file.is_file() or file.is_symlink():
                                continue
                            if root not in file.resolve().parents:
                                continue
                            if file.suffix.lower() not in (".tif", ".tiff", ".json"):
                                continue
                            relative = file.relative_to(jobs_dir)
                            # Only flat, canonical UUID job folders may be restored.
                            try:
                                import uuid
                                if len(relative.parts) != 2 or str(uuid.UUID(relative.parts[0])) != relative.parts[0]:
                                    continue
                            except ValueError:
                                continue
                            arcname = (Path("jobs") / relative).as_posix()
                            if relative.name.startswith("."):
                                continue
                            size, sha = sha256_file(file)
                            archive.write(file, arcname=arcname)
                            recorded_files[arcname] = {"size": size, "sha256": sha}
                            archived_jobs += 1
                    # A verified community surroundings scan saves the
                    # operator re-querying OSM after disaster recovery.
                    # It remains user-unverified, and cache freshness is not
                    # upgraded by restoring the file.
                    context_dir = data_dir / "site_context"
                    if context_dir.is_dir():
                        import uuid
                        for cached in sorted(context_dir.glob("*.json")):
                            if cached.is_symlink() or not cached.is_file():
                                continue
                            try:
                                if str(uuid.UUID(cached.stem)) != cached.stem:
                                    continue
                            except ValueError:
                                continue
                            with sqlite3.connect(snapshot) as known:
                                project_exists = known.execute(
                                    "SELECT EXISTS(SELECT 1 FROM projects WHERE id=?)",
                                    (cached.stem,)
                                ).fetchone()[0]
                            if not project_exists:
                                continue
                            arcname = "site_context/" + cached.name
                            size, sha = sha256_file(cached)
                            archive.write(cached, arcname=arcname)
                            recorded_files[arcname] = {"size": size, "sha256": sha}
                            archived_jobs += 1
                    manifest = {
                        "product": "PLANEXUS AI local workspace backup",
                        "format_version": FORMAT_VERSION,
                        "files": recorded_files,
                        "created_at_utc": datetime.now(timezone.utc).isoformat(),
                        "project_count": project_count,
                        "gis_files_archived": archived_jobs,
                        "contains_sensitive_site_data": True,
                        "instructions": "Offline restore only: python -m app.backup_restore restore --archive PATH --destination NEW_EMPTY_PATH. Never overwrite a live volume.",
                        "limits": "UNENCRYPTED private copy of users, password hashes, projects and GIS data. Only cooperating API writers use the shared lock. No cloud/off-site sync.",
                    }
                    archive.writestr("BACKUP-MANIFEST.json", json.dumps(manifest, indent=2))
                target.flush()
                os.fsync(target.fileno())
            # Only a fully verified archive receives the final *.zip name.
            verify_backup(partial)
            os.replace(partial, output)
            if os.name == "posix":
                os.chmod(output, 0o600)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup PLANEXUS local SQLite projects and GIS rasters")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[2] / "backups")
    args = parser.parse_args()
    backup = create_backup(args.data_dir, args.output_dir)
    print("PLANEXUS BACKUP CREATED:", backup)
    print("Keep this archive private. It contains site boundaries and analysis outputs.")
    print("SQLite data were safely snapshotted. For the most consistent raster backup, stop the two PLANEXUS servers before running.")


if __name__ == "__main__":
    main()
