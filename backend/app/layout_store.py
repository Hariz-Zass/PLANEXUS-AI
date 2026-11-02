"""Single revisioned road/layout draft per local project, preserved with SQLite backups."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .layout_engine import LayoutInput, screen_layout
from .project_store import _now, _uuid, connection


def _project(db:Any,project_id:str)->Any:
    row=db.execute("SELECT * FROM projects WHERE id=?",(project_id,)).fetchone()
    if row is None:
        raise HTTPException(404,"Project not found.")
    if row["site_geometry"] is None:
        raise HTTPException(422,"Save a site boundary in Project Workspace before layout screening.")
    return row


def _fingerprint(site_json:str)->str:
    return hashlib.sha256(site_json.encode("utf-8")).hexdigest()


def _payload(row:Any,project:Any,report:dict[str,Any]|None)->dict[str,Any]:
    site=json.loads(project["site_geometry"])
    if row is None:
        inputs=LayoutInput()
        return {
            "project_id":project["id"],"exists":False,
            "revision":0,"inputs":inputs.model_dump(),
            "site_changed":False,"analysis_changed":False,
            "analysis_id_at_save":None,
            "created_at_utc":None,"updated_at_utc":None,
            "preview":screen_layout(site,inputs,report),
        }
    inputs=LayoutInput.model_validate(json.loads(row["input_json"]))
    site_changed=_fingerprint(project["site_geometry"])!=row["site_hash"]
    analysis_changed=project["active_analysis_id"]!=row["analysis_id_at_save"]
    if site_changed:
        preview=None  # Geometry and road buffer MUST NOT be used on a different site.
    else:
        preview=screen_layout(site,inputs,report if not analysis_changed else None)
        if analysis_changed:
            preview["terrain_status"]="analysis_changed_review_required"
            preview["warnings"].append(
                "The project's active DEM analysis changed since the road sketch was saved. Only geometry envelopes are shown. Re-save to review terrain with the new report."
            )
    return {
        "project_id":project["id"],"exists":True,
        "revision":row["revision"],"inputs":inputs.model_dump(),
        "site_changed":site_changed,"analysis_changed":analysis_changed,
        "analysis_id_at_save":row["analysis_id_at_save"],
        "created_at_utc":row["created_at_utc"],
        "updated_at_utc":row["updated_at_utc"],
        "preview":preview,
    }


def get_layout(data_dir:Path,project_id:str,report:dict[str,Any]|None=None)->dict[str,Any]:
    project_id=_uuid(project_id)
    with connection(data_dir) as db:
        project=_project(db,project_id)
        row=db.execute("SELECT * FROM project_layouts WHERE project_id=?",(project_id,)).fetchone()
        return _payload(row,project,report)


def save_layout(
    data_dir:Path,project_id:str,inputs:LayoutInput,expected_revision:int,
    report:dict[str,Any]|None=None,
)->dict[str,Any]:
    project_id=_uuid(project_id)
    if expected_revision<0:
        raise HTTPException(422,"Invalid layout revision.")
    with connection(data_dir) as db:
        with db:
            project=_project(db,project_id)
            site=json.loads(project["site_geometry"])
            # Validation and polygons are calculated BEFORE modifying saved data.
            screen_layout(site,inputs,report)
            saved=db.execute("SELECT revision FROM project_layouts WHERE project_id=?",(project_id,)).fetchone()
            now=_now()
            if saved is None:
                if expected_revision!=0:
                    raise HTTPException(409,"Layout was deleted in another tab. Reload before saving.")
                db.execute(
                    "INSERT INTO project_layouts(project_id,input_json,site_hash,"
                    "analysis_id_at_save,revision,created_at_utc,updated_at_utc)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (project_id,json.dumps(inputs.model_dump(),allow_nan=False),
                     _fingerprint(project["site_geometry"]),project["active_analysis_id"],1,now,now),
                )
            else:
                if saved["revision"]!=expected_revision:
                    raise HTTPException(409,"Layout has changed in another tab. Reload before saving.")
                changed=db.execute(
                    "UPDATE project_layouts SET input_json=?,site_hash=?,analysis_id_at_save=?,"
                    "revision=revision+1,updated_at_utc=? WHERE project_id=? AND revision=?",
                    (json.dumps(inputs.model_dump(),allow_nan=False),
                     _fingerprint(project["site_geometry"]),project["active_analysis_id"],
                     now,project_id,expected_revision),
                ).rowcount
                if changed!=1:
                    raise HTTPException(409,"Layout has changed in another tab.")
    return get_layout(data_dir,project_id,report)
