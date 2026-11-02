"""Safe portable local backup of PLANEXUS projects and GIS evidence.

Uses SQLite's online backup API for a transactionally consistent database
snapshot, then archives generated GIS job files. This is a *local* backup;
never upload these files to a public repository.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .settings import DATA_DIR


def create_backup(data_dir: Path, output_dir: Path) -> Path:
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
            with zipfile.ZipFile(output, mode="x", compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=5, allowZip64=True) as archive:
                archive.write(snapshot, arcname="planexus-workspace.sqlite3")
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
                        archive.write(file, arcname=str(Path("jobs") / file.relative_to(jobs_dir)))
                        archived_jobs += 1
                manifest = {
                    "product": "PLANEXUS AI local workspace backup",
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "project_count": project_count,
                    "gis_files_archived": archived_jobs,
                    "contains_sensitive_site_data": True,
                    "instructions": "Stop PLANEXUS servers before restoring. Extract this ZIP into the backend data directory and retain the original backup.",
                    "limits": "No user accounts or cloud sync. Backups are not encrypted.",
                }
                archive.writestr("BACKUP-MANIFEST.json", json.dumps(manifest, indent=2))
        except Exception:
            output.unlink(missing_ok=True)
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
