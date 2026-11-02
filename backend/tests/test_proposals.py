"""Development Proposal Module 2: deterministic budgets, per-project scenarios and GIS context."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.main as main
from app.proposal_engine import ProposalInput, calculate_land_budget
from app.project_store import attach_analysis

SITE_A={"type":"Polygon","coordinates":[[[101.07,4.66],[101.08,4.66],[101.08,4.67],[101.07,4.67],[101.07,4.66]]]}
SITE_B={"type":"Polygon","coordinates":[[[101.10,4.70],[101.11,4.70],[101.11,4.71],[101.10,4.71],[101.10,4.70]]]}
INPUT={
    "name":"300 terrace lots — area test",
    "development_type":"terrace_housing",
    "units":300,"lot_width_m":6,"lot_depth_m":20,
    "roads_pct":20,"open_space_pct":10,"facilities_pct":5,"other_reserve_pct":5,
}


def test_land_budget_300_lots_and_unit_density_no_rounding_to_zero():
    p=ProposalInput.model_validate(INPUT)
    r=calculate_land_budget(p,site_area_ha=12.0)
    assert r["lot_area_m2"]==pytest.approx(120)
    assert r["required_plot_area_ha"]==pytest.approx(3.6)
    assert r["required_gross_area_ha"]==pytest.approx(6)
    assert r["allocations_ha"]["roads_ha"]==pytest.approx(1.2)
    assert r["allocations_ha"]["open_space_ha"]==pytest.approx(.6)
    assert r["allocations_ha"]["facilities_ha"]==pytest.approx(.3)
    assert r["allocations_ha"]["other_reserve_ha"]==pytest.approx(.3)
    assert r["gross_site_density_units_per_ha"]==pytest.approx(25)
    assert r["gross_site_area_check"]=="arithmetic_area_envelope"
    assert r["screening_status"]=="no_active_analysis"
    assert r["not_approval"] is True
    solo=ProposalInput.model_validate({**INPUT,"units":1,"development_type":"shoplots"})
    single=calculate_land_budget(solo,site_area_ha=12)
    assert single["gross_site_density_units_per_ha"]>0
    assert single["gross_site_density_units_per_ha"]==pytest.approx(.0833)


@pytest.mark.parametrize("change",[
    {"units":0},{"units":-2},{"units":300.5},{"lot_width_m":0},
    {"lot_depth_m":-1},{"roads_pct":75},{"roads_pct":50,"open_space_pct":30,"facilities_pct":5},
    {"lot_width_m":float("inf")},{"lot_depth_m":float("nan")},
    {"development_type":"apartments"},{"name":" "},
])
def test_invalid_or_unsupported_proposal_values_rejected(change):
    with pytest.raises(ValidationError):
        ProposalInput.model_validate({**INPUT,**change})


def _analysis(ident:str,geometry:dict,lower_area:float,coverage:float=99.8,coarse:int=30)->dict:
    return {
        "analysis_id":ident,"created_at_utc":"2026-11-02T05:00:00Z",
        "geometry":geometry,
        "metrics":{"site_area_ha":123.0},
        "source":{"name":"Synthetic fixture — NOT real terrain"},
        "suitability":{
            "bands":[{"id":1,"area_ha_est":lower_area},{"id":2,"area_ha_est":20}],
            "assessed_pixels":600,
            "coverage_of_site_pct_est":coverage,
            "area_exceeds_site_due_to_pixelization":False,
            "class_overlay_truncated":False,
            "source_resolution_m":coarse,
        },
    }


def test_terrain_compares_cell_area_not_planning_permission():
    p=ProposalInput.model_validate(INPUT)
    evidence=_analysis(str(uuid.uuid4()),SITE_A,lower_area=10)
    r=calculate_land_budget(p,site_area_ha=12,analysis=evidence)
    assert r["screening_status"]=="indicative_cell_area_only"
    assert r["lower_constraint_cell_area_ha_est"]==10
    assert r["lower_constraint_area_margin_ha_est"]==pytest.approx(4)
    assert r["terrain_screening_cell_area_check"]=="cell_area_envelope_only"
    assert "DOES NOT prove feasibility" in r["conclusion"]
    assert not any("approved" in str(v).lower() for v in (r["screening_status"],r["terrain_screening_cell_area_check"]))
    limited=calculate_land_budget(p,site_area_ha=12,analysis=_analysis(str(uuid.uuid4()),SITE_A,lower_area=2,coverage=50,coarse=90))
    assert limited["terrain_screening_cell_area_check"]=="cell_area_shortfall"
    assert limited["screening_status"]=="quality_limited"
    assert limited["lower_constraint_area_margin_ha_est"]==pytest.approx(-4)
    assert any("90" in w for w in limited["quality_warnings"])
    stale=calculate_land_budget(p,site_area_ha=12,analysis=evidence,context_current=False)
    assert stale["screening_status"]=="context_changed"
    assert stale["lower_constraint_cell_area_ha_est"] is None


def test_api_proposals_persist_reopen_update_concurrency_and_isolation(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path)
    c=TestClient(main.app)
    a=c.post("/api/projects",json={"name":"Development A","geometry":SITE_A}).json()
    b=c.post("/api/projects",json={"name":"Development B","geometry":SITE_B}).json()
    path=lambda pid:f"/api/projects/{pid}/proposals"
    created=c.post(path(a["id"]),json=INPUT)
    assert created.status_code==201,created.text
    saved=created.json()
    assert saved["project_id"]==a["id"]
    assert saved["revision"]==1
    assert saved["result"]["required_gross_area_ha"]==6
    assert saved["result"]["screening_status"]=="no_active_analysis"
    assert saved["result"]["gross_site_density_units_per_ha"]>0
    assert len(c.get(path(a["id"])).json()["proposals"])==1
    assert c.get(path(b["id"])).json()["proposals"]==[]
    assert c.get(path(b["id"])+"/"+saved["id"]).status_code==404
    with TestClient(main.app) as again:
        persisted=again.get(path(a["id"])).json()["proposals"][0]
        assert persisted["inputs"]==saved["inputs"]
        assert persisted["result"]["required_gross_area_ha"]==pytest.approx(6)
    put=c.put(path(a["id"])+"/"+saved["id"],json={
        "expected_revision":1,
        "proposal":{**INPUT,"units":330,"name":"Optimistic test 330"}
    })
    assert put.status_code==200,put.text
    assert put.json()["result"]["required_gross_area_ha"]==pytest.approx(6.6)
    assert put.json()["revision"]==2
    assert c.put(path(a["id"])+"/"+saved["id"],json={
        "expected_revision":1,"proposal":INPUT
    }).status_code==409
    assert c.post(path(a["id"]),json={**INPUT,"roads_pct":50,"open_space_pct":35}).status_code==422
    assert c.post(path(a["id"]),json={**INPUT,"development_type":"apartments"}).status_code==422
    assert c.delete(path(b["id"])+"/"+saved["id"]).status_code==404
    assert c.delete(path(a["id"])+"/"+saved["id"]).status_code==204
    assert c.get(path(a["id"])).json()["proposals"]==[]


def test_boundary_required_and_project_deletion_cascades_proposals(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path)
    c=TestClient(main.app)
    p=c.post("/api/projects",json={"name":"No Site"}).json()
    path=f"/api/projects/{p['id']}/proposals"
    assert c.post(path,json=INPUT).status_code==422
    assert c.get(path).status_code==422
    p=c.patch(f"/api/projects/{p['id']}",json={"expected_revision":1,"geometry":SITE_A}).json()
    scenario=c.post(path,json=INPUT).json()
    assert scenario["id"]
    assert c.delete(f"/api/projects/{p['id']}").status_code==204
    assert c.get(path).status_code==404


def test_report_change_marks_scenarios_stale_and_explicit_update_rebinds(monkeypatch,tmp_path):
    monkeypatch.setattr(main,"DATA_DIR",tmp_path)
    c=TestClient(main.app)
    p=c.post("/api/projects",json={"name":"Analysis-linked scenario","geometry":SITE_A}).json()
    base=f"/api/projects/{p['id']}/proposals"
    report1=_analysis(str(uuid.uuid4()),SITE_A,lower_area=10)
    report2=_analysis(str(uuid.uuid4()),SITE_A,lower_area=4)
    for report in (report1,report2):
        folder=tmp_path/"jobs"/report["analysis_id"]
        folder.mkdir(parents=True)
        (folder/"result.json").write_text(json.dumps(report))
    attach_analysis(tmp_path,p["id"],report1)
    saved=c.post(base,json=INPUT).json()
    assert saved["analysis_id_at_save"]==report1["analysis_id"]
    assert saved["result"]["screening_status"]=="indicative_cell_area_only"
    assert saved["result"]["terrain_screening_cell_area_check"]=="cell_area_envelope_only"
    attach_analysis(tmp_path,p["id"],report2)
    stale=c.get(base).json()["proposals"][0]
    assert stale["context_changed"]
    assert stale["result"]["screening_status"]=="context_changed"
    assert stale["result"]["lower_constraint_cell_area_ha_est"] is None
    refreshed=c.put(base+"/"+saved["id"],json={
        "expected_revision":stale["revision"],"proposal":saved["inputs"]
    })
    assert refreshed.status_code==200,refreshed.text
    assert refreshed.json()["analysis_id_at_save"]==report2["analysis_id"]
    assert refreshed.json()["result"]["terrain_screening_cell_area_check"]=="cell_area_shortfall"
    assert refreshed.json()["context_changed"] is False
    assert refreshed.json()["result"]["not_approval"]
    # Changing the actual site invalidates the old input context.
    project=c.get("/api/projects/"+p["id"]).json()
    modified=c.patch("/api/projects/"+p["id"],json={
        "expected_revision":project["revision"],"geometry":SITE_B
    })
    assert modified.status_code==200
    response=c.get(base).json()["proposals"][0]
    assert response["context_changed"]
    assert response["result"]["screening_status"]=="context_changed"
    assert response["result"]["analysis_id"] is None
