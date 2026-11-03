"""B3.4 opt-in scheduled GIS backups (not a cloud/off-host service).

Run 'once' from Windows Task Scheduler or run 'run' as a private container
worker. Archives are UNENCRYPTED and must be mirrored to operator-managed
encrypted off-host storage for host failure protection.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backup import create_backup
from .backup_restore import restore_backup, sha256_file, verify_backup
from .gis_lock import data_lock
from .settings import DATA_DIR

BACKUP_RE = re.compile(r"^PLANEXUS-backup-\d{8}-\d{6}-\d{6}\.zip$")
STATUS_NAME = "planexus-automated-backup-status.json"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def archives(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        (p for p in root.iterdir()
         if p.is_file() and not p.is_symlink() and BACKUP_RE.fullmatch(p.name)
         and p.parent.resolve() == root.resolve()), key=lambda p:p.name, reverse=True
    )


def write_status(root: Path, status: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".planexus-status-", suffix=".tmp", dir=root)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(status, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, root / STATUS_NAME)
    finally:
        tmp.unlink(missing_ok=True)


def restore_drill(archive: Path) -> dict[str, Any]:
    """Actually extract and integrity-check in an isolated disposable folder."""
    proof = verify_backup(archive)
    with tempfile.TemporaryDirectory(prefix="planexus-restore-drill-") as tmp:
        target = Path(tmp) / "new-volume"
        recovered = restore_backup(archive, target)
        if recovered["project_count"] != proof["project_count"]:
            raise RuntimeError("Recovered project count differs from verified archive.")
        if recovered["analysis_count"] != proof["analysis_count"]:
            raise RuntimeError("Recovered GIS report count differs from verified archive.")
        if not (target / "planexus-workspace.sqlite3").is_file():
            raise RuntimeError("Recovered SQLite database was not created.")
        return {"passed":True,"project_count":proof["project_count"],
                "analysis_count":proof["analysis_count"],
                "old_sessions_revoked":True}


def mirror_archive(archive: Path, mirror_dir: Path, *, data_dir: Path,
                   primary_dir: Path) -> Path:
    mirror, data, primary = (p.expanduser().resolve()
                             for p in (mirror_dir, data_dir, primary_dir))
    if (mirror == data or mirror == primary
        or mirror in data.parents or data in mirror.parents
        or mirror in primary.parents or primary in mirror.parents):
        raise ValueError("Mirror must be separate from source GIS and backup folders.")
    mirror.mkdir(parents=True, exist_ok=True)
    dest = mirror / archive.name
    if dest.exists():
        raise RuntimeError("Mirror archive already exists; refusing to overwrite.")
    fd, name = tempfile.mkstemp(prefix=".planexus-copy-",suffix=".partial",dir=mirror)
    tmp = Path(name)
    try:
        with archive.open("rb") as source, os.fdopen(fd,"wb") as output:
            shutil.copyfileobj(source,output,length=1024*1024)
            output.flush()
            os.fsync(output.fileno())
        if sha256_file(archive) != sha256_file(tmp):
            raise RuntimeError("Mirrored archive SHA-256 does not match original.")
        verify_backup(tmp)
        os.replace(tmp,dest)
        return dest
    finally:
        tmp.unlink(missing_ok=True)


def run_once(data_dir: Path, output_dir: Path, *, keep: int=14,
             mirror_dir: Path | None=None, drill: bool=False) -> dict[str, Any]:
    """Never prune older ZIP files unless new archive and mirror pass checks."""
    if not 2 <= keep <= 365:
        raise ValueError("Automatic backup retention must keep 2 to 365 generations.")
    output, data = output_dir.expanduser().resolve(), data_dir.expanduser().resolve()
    if output == data or data in output.parents:
        raise ValueError("Backup folder must not be inside GIS data volume.")
    output.mkdir(parents=True,exist_ok=True)
    # Separate scheduler instances cannot race writing status or pruning.
    with data_lock(output, timeout_s=0):
        started=utc()
        try:
            backup=create_backup(data, output)
            proof=verify_backup(backup)
            archive_size, archive_sha=sha256_file(backup)
            mirror=(mirror_archive(backup,mirror_dir,data_dir=data,primary_dir=output)
                    if mirror_dir else None)
            rehearsal=(restore_drill(backup) if drill else
                       {"passed":False,"reason":"Not requested; use drill command."})
            all_files=archives(output)
            to_prune=all_files[keep:]
            for old in to_prune:
                old.unlink()
            result={
                "status":"success","started_at_utc":started,"finished_at_utc":utc(),
                "archive":backup.name,"archive_size_bytes":archive_size,
                "archive_sha256":archive_sha,"verified":proof["verified"],
                "project_count":proof["project_count"],
                "analysis_count":proof["analysis_count"],
                "proposal_count":proof["proposal_count"],
                "layout_count":proof["layout_count"],
                "mirrored":mirror is not None,
                "mirror_archive":str(mirror) if mirror else None,
                "restore_drill":rehearsal,
                "retained_generations":len(archives(output)),
                "pruned_generations":len(to_prune),"encrypted":False,
            }
            write_status(output,result)
            return result
        except Exception as exc:
            # Existing backups MUST survive failed scheduled attempts.
            try:
                write_status(output,{
                    "status":"failed","started_at_utc":started,
                    "finished_at_utc":utc(),"error_type":type(exc).__name__,
                    "detail":str(exc)[:350],"older_backups_preserved":True,
                })
            except OSError:
                pass
            raise


def main() -> None:
    parser=argparse.ArgumentParser(description="PLANEXUS private GIS backup scheduler")
    parser.add_argument("command",choices=("once","run","status","drill"))
    parser.add_argument("--data-dir",type=Path,default=DATA_DIR)
    parser.add_argument("--output-dir",type=Path,
        default=Path(__file__).resolve().parents[2]/"private-backups"/"automatic")
    parser.add_argument("--mirror-dir",type=Path)
    parser.add_argument("--keep",type=int,default=14)
    parser.add_argument("--interval-hours",type=float,default=24.0)
    parser.add_argument("--restore-drill",action="store_true")
    args=parser.parse_args()
    if args.command=="status":
        path=args.output_dir/STATUS_NAME
        print(path.read_text(encoding="utf-8") if path.is_file() else
              json.dumps({"status":"never_ran","archives":len(archives(args.output_dir))}))
        return
    if args.command=="drill":
        existing=archives(args.output_dir)
        if not existing:
            parser.error("No automated backup archives available to restore.")
        print(json.dumps(restore_drill(existing[0]),indent=2))
        return
    if not 1 <= args.interval_hours <= 168:
        parser.error("Recurring interval must be 1 to 168 hours.")
    while True:
        try:
            print(json.dumps(run_once(args.data_dir,args.output_dir,keep=args.keep,
                mirror_dir=args.mirror_dir,drill=args.restore_drill),indent=2),flush=True)
        except Exception as exc:
            print(json.dumps({"status":"failed","type":type(exc).__name__,
                              "detail":str(exc)[:350]}),flush=True)
            if args.command=="once":
                raise SystemExit(1) from exc
        if args.command=="once":
            return
        time.sleep(args.interval_hours*3600)


if __name__ == "__main__":
    main()
