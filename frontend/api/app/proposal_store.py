"""SQLite proposal persistence isolated by local PLANEXUS project.

Saved proposal parameters are associated with the boundary fingerprint and GIS
analysis ID present AT SAVE TIME. When the site/report changes, any old scenario
shows 'context_changed' rather than using unrelated terrain data.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .geometry import area_km2
from .project_store import _now, _uuid, connection
from .proposal_engine import ProposalInput, calculate_land_budget
from .policy_registry import REGISTRY_VERSION

MAX_PROPOSALS_PER_PROJECT=20


def _project(db:Any,project_id:str)->Any:
    row=db.execute("SELECT * FROM projects WHERE id=?",(project_id,)).fetchone()
    if row is None:
        raise HTTPException(404,"Project not found.")
    if not row["site_geometry"]:
        raise HTTPException(422,"Define and save a site boundary in this project before adding development proposals.")
    return row


def _geometry_hash(encoded:str)->str:
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _serialize(row:Any,project:Any,active_report:dict[str,Any]|None)->dict[str,Any]:
    fields=json.loads(row["input_json"])
    proposal=ProposalInput.model_validate(fields)
    context_matches=(
        row["site_hash"]==_geometry_hash(project["site_geometry"])
        and row["analysis_id_at_save"]==project["active_analysis_id"]
    )
    from shapely.geometry import shape
    from pyproj import Geod
    geod=Geod(ellps="WGS84")
    site_ha=abs(geod.geometry_area_perimeter(shape(json.loads(project["site_geometry"])))[0])/10000
    result=calculate_land_budget(
        proposal,site_area_ha=site_ha,
        analysis=active_report if context_matches else None,
        context_current=context_matches,
    )
    policy_review_needed=(
        proposal.policy_profile != "none"
        and row["policy_registry_version_at_save"] != REGISTRY_VERSION
    )
    if policy_review_needed:
        # Never silently represent a freshly edited rule set as having been used
        # when an older proposal was saved. Request explicit review/resave.
        result["policy_assessment"]["checks"]=[]
        result["policy_assessment"]["status"]="registry_version_changed_review"
        result["policy_assessment"]["message"]="GPP rule registry changed since this scenario was saved. Re-check source pages and update the scenario to adopt current rules."
        result["policy_assessment"]["warnings"].append("Previously stored policy comparison is not carried forward automatically.")
    return {
        "id":row["id"],"project_id":row["project_id"],
        "created_at_utc":row["created_at_utc"],"updated_at_utc":row["updated_at_utc"],
        "revision":row["revision"],"analysis_id_at_save":row["analysis_id_at_save"],
        "context_changed":not context_matches,
        "policy_registry_version_at_save":row["policy_registry_version_at_save"],
        "policy_review_needed":policy_review_needed,
        "inputs":fields,"result":result,
    }


def list_proposals(data_dir:Path,project_id:str,active_report:dict[str,Any]|None=None)->dict[str,Any]:
    project_id=_uuid(project_id)
    with connection(data_dir) as db:
        project=_project(db,project_id)
        rows=db.execute(
            "SELECT * FROM project_proposals WHERE project_id=? ORDER BY updated_at_utc DESC,id DESC",
            (project_id,),
        ).fetchall()
        proposals=[_serialize(row,project,active_report) for row in rows]
        return {"project_id":project_id,"project_active_analysis_id":project["active_analysis_id"],
                "proposals":proposals,"storage":"local-sqlite; no cloud sync"}


def get_proposal(data_dir:Path,project_id:str,proposal_id:str,active_report:dict[str,Any]|None=None)->dict[str,Any]:
    project_id,proposal_id=_uuid(project_id),_uuid(proposal_id)
    with connection(data_dir) as db:
        project=_project(db,project_id)
        row=db.execute("SELECT * FROM project_proposals WHERE id=? AND project_id=?",
                       (proposal_id,project_id)).fetchone()
        if row is None:raise HTTPException(404,"Development proposal not found in this project.")
        return _serialize(row,project,active_report)


def create_proposal(data_dir:Path,project_id:str,input:ProposalInput,active_report:dict[str,Any]|None=None)->dict[str,Any]:
    project_id=_uuid(project_id)
    ident=str(uuid.uuid4())
    time=_now()
    with connection(data_dir) as db:
        with db:
            project=_project(db,project_id)
            count=db.execute("SELECT COUNT(*) FROM project_proposals WHERE project_id=?",(project_id,)).fetchone()[0]
            if count>=MAX_PROPOSALS_PER_PROJECT:
                raise HTTPException(422,"Local project proposal limit of 20 reached.")
            db.execute(
                "INSERT INTO project_proposals"
                "(id,project_id,input_json,site_hash,analysis_id_at_save,policy_registry_version_at_save,revision,created_at_utc,updated_at_utc)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (ident,project_id,json.dumps(input.model_dump(),allow_nan=False),_geometry_hash(project["site_geometry"]),
                 project["active_analysis_id"],REGISTRY_VERSION,1,time,time),
            )
    return get_proposal(data_dir,project_id,ident,active_report)


def update_proposal(data_dir:Path,project_id:str,proposal_id:str,input:ProposalInput,
                    expected_revision:int,active_report:dict[str,Any]|None=None)->dict[str,Any]:
    project_id,proposal_id=_uuid(project_id),_uuid(proposal_id)
    if expected_revision<1:raise HTTPException(422,"Invalid proposal revision.")
    with connection(data_dir) as db:
        with db:
            project=_project(db,project_id)
            updated=db.execute(
                "UPDATE project_proposals SET input_json=?,site_hash=?,analysis_id_at_save=?,"
                "policy_registry_version_at_save=?,revision=revision+1,updated_at_utc=? WHERE id=? AND project_id=? AND revision=?",
                (json.dumps(input.model_dump(),allow_nan=False),_geometry_hash(project["site_geometry"]),
                 project["active_analysis_id"],REGISTRY_VERSION,_now(),proposal_id,project_id,expected_revision),
            )
            if not updated.rowcount:
                exists=db.execute("SELECT 1 FROM project_proposals WHERE id=? AND project_id=?",
                                  (proposal_id,project_id)).fetchone()
                if exists:raise HTTPException(409,"This scenario changed in another tab. Reload the scenario before updating.")
                raise HTTPException(404,"Proposal does not belong to this project.")
    return get_proposal(data_dir,project_id,proposal_id,active_report)


def delete_proposal(data_dir:Path,project_id:str,proposal_id:str)->None:
    project_id,proposal_id=_uuid(project_id),_uuid(proposal_id)
    with connection(data_dir) as db:
        with db:
            _project(db,project_id)
            deleted=db.execute("DELETE FROM project_proposals WHERE id=? AND project_id=?",
                               (proposal_id,project_id)).rowcount
            if not deleted:raise HTTPException(404,"Development proposal not found in this project.")
