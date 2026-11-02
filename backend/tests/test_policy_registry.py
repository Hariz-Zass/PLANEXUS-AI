"""Official GPP registry, scoped numeric checks and source-linked policy Q&A.

Only housing rules manually checked from GP001-A (2016), Jadual 2, pp.44-45,
and Perak Housing (2023), PR1 p.5 are eligible for numeric comparison.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.main as main
from app.policy_registry import (
    NATIONAL_SOURCE, PERAK_SOURCE, REGISTRY_VERSION,
    NATIONAL_LOT_RULES, catalog, evaluate_policy, answer_gpp_question
)
from app.proposal_engine import ProposalInput, calculate_land_budget


BASE={
    "name":"Perumahan 300 unit - kajian dasar", "development_type":"terrace_housing",
    "units":300,"lot_width_m":6,"lot_depth_m":20,"roads_pct":20,
    "open_space_pct":10,"facilities_pct":5,"other_reserve_pct":5
}


@pytest.mark.parametrize("category,storeys,width,depth", [
    ("terrace_low_cost",1,6.1,16.8),
    ("terrace_low_cost",2,4.3,16.8),
    ("terrace_lower_middle",1,6.1,18.3),
    ("terrace_lower_middle",2,5.5,16.8),
    ("terrace_middle",1,6.1,19.8),
    ("terrace_middle",2,5.5,19.8),
    ("terrace_middle",3,5.5,19.8),
])
def test_official_national_lot_minima_by_type_and_floor(category,storeys,width,depth):
    p=ProposalInput.model_validate({
        **BASE,"policy_profile":"national_2016","housing_category":category,
        "storeys":storeys,"lot_width_m":width,"lot_depth_m":depth,
    })
    result=evaluate_policy(p)
    assert result["registry_version"] == REGISTRY_VERSION
    assert result["status"] in ("more_inputs_needed","numeric_reference_only")
    checks={item["key"]:item for item in result["checks"]}
    assert checks["min_lot_frontage"]["value"] == width
    assert checks["min_lot_depth"]["value"] == depth
    assert checks["min_lot_frontage"]["result"] == "meets_number"
    assert checks["min_lot_depth"]["result"] == "meets_number"
    assert checks["min_lot_frontage"]["source_page"].startswith("Jadual 2")
    assert checks["min_lot_frontage"]["source_url"].endswith(".pdf")
    assert result["max_lot_width_m"] is None
    assert result["max_lot_depth_m"] is None
    assert result["reference_only"] is True
    below=ProposalInput.model_validate({
        **BASE,"policy_profile":"national_2016","housing_category":category,
        "storeys":storeys,"lot_width_m":width-.1,"lot_depth_m":depth-.1,
    })
    failed=evaluate_policy(below)
    assert failed["status"] == "outside_numeric_reference"
    assert {i["result"] for i in failed["checks"] if i["key"].startswith("min_lot")} == {"below_min"}


@pytest.mark.parametrize("category,storeys,width,depth",[
    ("cluster",1,12.2,15.2),("cluster",2,9.1,16.8),
    ("semi_detached",1,12.2,19.8),
    ("detached",1,15.2,22.9),
    ("zero_lot",1,13.7,21.3),
])
def test_national_other_housing_lot_categories(category,storeys,width,depth):
    p=ProposalInput.model_validate({
        **BASE,"development_type":"other_landed",
        "housing_category":category,"storeys":storeys,
        "policy_profile":"national_2016",
        "lot_width_m":width,"lot_depth_m":depth,
    })
    results=evaluate_policy(p)
    assert [x["value"] for x in results["checks"] if x["key"].startswith("min_lot")] == [width,depth]


def test_perak_2023_min_floor_and_three_storey_height_and_no_false_local_lot_minimum():
    inp=ProposalInput.model_validate({
        **BASE,"policy_profile":"perak_2023",
        "housing_category":"terrace_middle","storeys":2,
        "perak_market_segment":"perak_affordable",
        "floor_area_m2":90,
        "bedrooms":3,"building_height_m":16,
    })
    r=evaluate_policy(inp)
    items={item["key"]:item for item in r["checks"]}
    assert items["min_floor_area_perak"]["value"]==pytest.approx(92.9030,abs=1e-4)
    assert items["min_floor_area_perak"]["result"]=="below_min"
    assert items["min_floor_area_perak"]["role"]=="primary_state_reference"
    assert items["max_storeys_perak"]["value"]==3
    assert items["max_storeys_perak"]["result"]=="meets_number"
    assert items["max_building_height_perak"]["value"]==pytest.approx(18.288)
    assert items["min_bedrooms_perak"]["value"]==3
    assert items["min_lot_frontage"]["role"]=="supplementary_national_reference"
    assert r["status"]=="outside_numeric_reference"
    assert r["max_lot_width_m"] is None
    assert PERAK_SOURCE["url"] in [i["source_url"] for i in r["checks"]]
    # A floor area above the lower bound is not proof of full permission.
    p=ProposalInput.model_validate({**inp.model_dump(),"floor_area_m2":100})
    ok=evaluate_policy(p)
    assert ok["status"]=="numeric_reference_only"
    assert ok["reference_only"]
    assert all(not item["binding"] for item in ok["checks"])


def test_perak_max_storeys_and_height_enforced_but_not_mislabeled_as_max_lot():
    p=ProposalInput.model_validate({
        **BASE,"policy_profile":"perak_2023","housing_category":"terrace_low_cost",
        "perak_market_segment":"perak_low_cost","storeys":4,
        "building_height_m":19,"bedrooms":2,"floor_area_m2":70,
    })
    r=evaluate_policy(p)
    assert r["status"]=="outside_numeric_reference"
    failed={x["key"]:x for x in r["checks"] if x["result"] in ("above_max","below_min")}
    assert {"max_storeys_perak","max_building_height_perak","min_bedrooms_perak","min_floor_area_perak"}.issubset(failed)
    assert r["max_lot_width_m"] is None


def test_no_jurisdiction_no_authoritative_pass_and_shoplot_catalog_only():
    missing=calculate_land_budget(ProposalInput.model_validate(BASE),site_area_ha=10)
    assert missing["required_gross_area_ha"]==pytest.approx(6)
    assert missing["policy_assessment"]["status"]=="not_selected"
    shop=ProposalInput.model_validate({
        **BASE,"development_type":"shoplots","policy_profile":"perak_2023"
    })
    result=evaluate_policy(shop)
    assert result["status"]=="not_indexed"
    assert result["checks"]==[]
    assert "GPP perdagangan" in result["message"]


def test_registry_catalog_not_falsely_complete_and_legal_docs_cited():
    data=catalog()
    assert len(data["national_lot_rules"])==len(NATIONAL_LOT_RULES)
    assert {s["id"] for s in data["sources"] if s["status"]=="curated_rules"}=={
        NATIONAL_SOURCE["id"],PERAK_SOURCE["id"]
    }
    assert any(s["status"]=="catalog_only" for s in data["sources"])
    assert data["not_indexed"]
    assert "NOT all indexed" in data["disclaimer"]
    for source in data["sources"]:
        assert source["url"].startswith("https://")
        assert source["evidence"]
    assert "page" not in data.get("max_lot_width_m",{})


def test_api_catalog_assess_and_copilot_grounded_policy_answer():
    client=TestClient(main.app)
    catalog_response=client.get("/api/policy/catalog")
    assert catalog_response.status_code==200
    assert catalog_response.json()["registry_version"]==REGISTRY_VERSION
    policy=client.post("/api/policy/assess",json={
        **BASE,"policy_profile":"national_2016",
        "housing_category":"terrace_middle","storeys":2,
        "lot_width_m":5.2,"lot_depth_m":19.8,
    })
    assert policy.status_code==200,policy.text
    assert policy.json()["status"]=="outside_numeric_reference"
    assert any(c["source_page"] for c in policy.json()["checks"])
    preanalysis=client.post("/api/copilot/assess",json={
        "question":"Apakah GPP saiz lot minimum rumah teres kos sederhana 2 tingkat?"
    })
    assert preanalysis.status_code==200,preanalysis.text
    response=preanalysis.json()
    assert response["mode"]=="verified_policy_registry_summary"
    assert "5.5 x 19.8 m" in response["response"]
    assert response["policy_sources"][0]["url"]==NATIONAL_SOURCE["url"]
    local=client.post("/api/copilot/assess",json={
        "question":"Berapa luas ruang lantai GPP Perak untuk rumah teres kos rendah?"
    })
    assert local.status_code==200
    assert "900 kps" in local.json()["response"]
    assert local.json()["policy_sources"][0]["url"]==PERAK_SOURCE["url"]


def test_impossible_profile_housing_category_inputs_rejected():
    with pytest.raises(ValidationError):
        ProposalInput.model_validate({
            **BASE,"development_type":"shoplots",
            "housing_category":"terrace_low_cost","policy_profile":"national_2016"
        })
    with pytest.raises(ValidationError):
        ProposalInput.model_validate({**BASE,"storeys":0,"policy_profile":"perak_2023"})
    with pytest.raises(ValidationError):
        ProposalInput.model_validate({**BASE,"floor_area_m2":float("nan")})
