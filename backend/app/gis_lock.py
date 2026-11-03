"""Cross-process PLANEXUS GIS write/backup lock (Windows and Linux).

Every backend mutating HTTP request holds this lock until the response has
been produced; SQLite+GeoTIFF snapshot then holds the same lock while copying
files. No claim of atomicity for writers that bypass this protocol.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import BinaryIO

LOCK_NAME = ".planexus-data.lock"


class LockBusy(TimeoutError):
    """A live analysis or backup has the writer lock."""


def acquire_data_lock(data_dir: Path, *, timeout_s: float = 180.0) -> BinaryIO:
    root = data_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    handle = (root / LOCK_NAME).open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return handle
            except (BlockingIOError, PermissionError, OSError) as exc:
                if time.monotonic() >= deadline:
                    raise LockBusy("PLANEXUS GIS busy: analysis/backup lock timeout.") from exc
                time.sleep(0.1)
    except BaseException:
        handle.close()
        raise


def release_data_lock(handle: BinaryIO) -> None:
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


class data_lock:
    """Synchronous lock context for offline CLI and scheduled backup worker."""
    def __init__(self, data_dir: Path, *, timeout_s: float = 180.0):
        self.data_dir, self.timeout_s = data_dir, timeout_s
        self.handle: BinaryIO | None = None

    def __enter__(self) -> "data_lock":
        self.handle = acquire_data_lock(self.data_dir, timeout_s=self.timeout_s)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.handle is not None:
            release_data_lock(self.handle)
            self.handle = None
