"""Fail-closed storage check for PLANEXUS single-workspace GIS backend.

SQLite project records, raster and report files must be on the SAME durable
filesystem. Set PLANEXUS_REQUIRE_PERSISTENT_VOLUME=1 and mount the volume at
PLANEXUS_DATA_DIR. This is not authentication, encryption or a backup.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any


def require_persistent_volume() -> bool:
    return os.getenv("PLANEXUS_REQUIRE_PERSISTENT_VOLUME", "0").strip().lower() in (
        "1", "true", "yes", "on"
    )


def check_storage(data_dir: Path, *, require_volume: bool | None = None) -> dict[str, Any]:
    """Check mount, read-after-write and existing SQLite integrity.

    Strict mode rejects an unmounted container path BEFORE creating files.
    """
    strict = require_persistent_volume() if require_volume is None else require_volume
    directory = data_dir.expanduser().resolve()
    if strict and not directory.is_mount():
        return {
            "ready": False, "type": "required_volume_missing", "persistent": False,
            "detail": "Persistent GIS data volume is not mounted. Save and analysis disabled to prevent data loss.",
        }
    temp_path: Path | None = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=directory, prefix=".planexus-write-check-", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(b"PLANEXUS storage check v1")
            handle.flush()
            os.fsync(handle.fileno())
        if temp_path.read_bytes() != b"PLANEXUS storage check v1":
            raise OSError("Read-after-write verification failed")
        db = directory / "planexus-workspace.sqlite3"
        if db.exists():
            with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=5) as connection:
                result = connection.execute("PRAGMA quick_check(1)").fetchone()
                if result is None or result[0] != "ok":
                    raise sqlite3.DatabaseError("SQLite quick_check failed")
    except (OSError, sqlite3.Error, ValueError) as exc:
        return {
            "ready": False, "type": "storage_unavailable", "persistent": False,
            "detail": f"GIS data storage unavailable or SQLite unhealthy: {type(exc).__name__}",
        }
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
    return {
        "ready": True, "type": "mounted_volume" if strict else "local_directory",
        "persistent": strict, "detail": (
            "Persistent volume mounted and storage roundtrip passed."
            if strict else
            "Local directory writable; cloud persistence not verified."
        ),
    }
