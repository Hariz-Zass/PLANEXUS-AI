"""B3.4 automated backup, source-lock, verified retention and disaster drill."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from app import auth, backup, backup_scheduler as scheduler
from app.gis_lock import LockBusy, acquire_data_lock, release_data_lock, data_lock
from app.project_store import create_project


def test_automated_backups_restore_drill_and_bounded_retention(tmp_path):
    data, out=tmp_path/"live-gis",tmp_path/"private-backups"/"automatic"
    admin=auth.create_user(data,"backup-admin@example.test","Backup Admin",
                           "Private-Backup-CI-2026!",role="admin")
    project=create_project(data,"Backup original",owner_id=admin["id"])
    first=scheduler.run_once(data,out,keep=2,drill=True)
    assert first["status"]=="success"
    assert first["restore_drill"]["passed"] is True
    assert first["project_count"]==1 and not first["encrypted"]
    one=out/first["archive"]
    assert one.exists()
    assert scheduler.restore_drill(one)["passed"]
    assert json.loads((out/scheduler.STATUS_NAME).read_text())["status"]=="success"
    create_project(data,"Additional project",owner_id=admin["id"])
    second=scheduler.run_once(data,out,keep=2)
    assert second["project_count"]==2
    third=scheduler.run_once(data,out,keep=2)
    assert third["status"]=="success"
    assert third["pruned_generations"]==1
    assert not one.exists()
    assert len(scheduler.archives(out))==2
    assert set(p.name for p in scheduler.archives(out))=={second["archive"],third["archive"]}
    assert not list(out.glob("*.partial"))
    assert auth.account_count(data)==1


def test_failed_schedule_keeps_every_existing_backup(tmp_path,monkeypatch):
    data,out=tmp_path/"data",tmp_path/"auto"
    create_project(data,"A reliable project")
    first=scheduler.run_once(data,out,keep=2)
    original=out/first["archive"]
    original_bytes=original.read_bytes()

    def crash_mirror(*args,**kwargs):
        raise OSError("synthetic offsite storage failure")

    monkeypatch.setattr(scheduler,"mirror_archive",crash_mirror)
    with pytest.raises(OSError,match="synthetic"):
        scheduler.run_once(data,out,keep=2,mirror_dir=tmp_path/"mirror")
    assert original.exists() and original.read_bytes()==original_bytes
    assert json.loads((out/scheduler.STATUS_NAME).read_text())["status"]=="failed"
    assert len(scheduler.archives(out))>=2


def test_real_separate_mirror_is_checksum_verified(tmp_path):
    data,out,remote=tmp_path/"gis",tmp_path/"local",tmp_path/"independent"
    create_project(data,"Gis evidence A")
    result=scheduler.run_once(data,out,mirror_dir=remote,keep=3)
    assert result["mirrored"] is True
    original=out/result["archive"]
    copied=remote/result["archive"]
    assert copied.exists()
    assert scheduler.sha256_file(original)==scheduler.sha256_file(copied)
    from app.backup_restore import verify_backup
    assert verify_backup(copied)["verified"]


def test_file_lock_excludes_other_processes_and_is_released(tmp_path):
    data=tmp_path/"data"
    create_project(data,"GIS data")
    handle=acquire_data_lock(data,timeout_s=1)
    try:
        with pytest.raises(LockBusy):
            acquire_data_lock(data,timeout_s=0)
    finally:
        release_data_lock(handle)
    with data_lock(data,timeout_s=1):
        pass
    assert scheduler.run_once(data,tmp_path/"automatic",keep=2)["verified"]


def test_atomic_backup_never_publishes_unverified_zip(tmp_path,monkeypatch):
    data=tmp_path/"data"
    create_project(data,"GIS")
    out=tmp_path/"automatic"
    def reject_unverified(_):
        raise RuntimeError("synthetic integrity failure")
    monkeypatch.setattr(backup,"verify_backup",reject_unverified)
    with pytest.raises(RuntimeError,match="synthetic"):
        backup.create_backup(data,out)
    assert not list(out.glob("*.zip"))
    assert not list(out.glob("*.partial"))


def test_mirror_folder_must_not_overlap_source(tmp_path):
    data=tmp_path/"data"
    create_project(data,"GIS")
    with pytest.raises(ValueError):
        scheduler.run_once(data,tmp_path/"automatic",mirror_dir=data)
