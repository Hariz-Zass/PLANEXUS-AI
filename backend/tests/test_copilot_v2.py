"""Copilot policy: no fabricated site facts before GIS, grounded metrics afterward.

Provider interaction uses a fake OpenAI client; no paid keys or external model
calls are needed for this test suite.
"""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app import copilot as assistant
from app.main import app

REPORT={
    "analysis_id":"77777777-7777-4777-8777-777777777777",
    "source":{"id":"copernicus-glo90-public","name":"Copernicus DEM GLO-90 Public (fallback)",
              "data_type":"DSM (includes vegetation and built structures)",
              "nominal_resolution_m":90,"fallback_used":True,
              "publisher":"Copernicus Programme / ESA","verified":"Fixture, not field survey",
              "source_tile_urls":["https://example.test/tiles/large.tif"]},
    "metrics":{
        "site_area_ha":12.5,"elevation_min_m":42.0,"elevation_mean_m":53.0,
        "elevation_max_m":68.0,"elevation_range_m":26.0,
        "slope_mean_deg":8.4,"slope_max_deg":32.0,
        "coverage_percent_est":82.5,
        "slope_classes":[
            {"id":1,"name":"Class I","percent_of_valid_slope":55.0,"area_ha_est":5.6},
            {"id":2,"name":"Class II","percent_of_valid_slope":25.0,"area_ha_est":2.5},
            {"id":3,"name":"Class III","percent_of_valid_slope":15.0,"area_ha_est":1.5},
            {"id":4,"name":"Class IV","percent_of_valid_slope":5.0,"area_ha_est":0.5},
        ],
        "horizontal_crs":"EPSG:32647",
    },
    "warnings":["Coverage less than 95%.","DSM is not field survey."],
    "assessment_scope":"Terrain screening only; no zoning or approval conclusion.",
    "geometry":{"type":"Polygon","coordinates":[[[101,4],[101.02,4],[101.02,4.02],[101,4.02],[101,4]]]},
}


def test_capabilities_are_truthful(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client=TestClient(app)
    cap=client.get("/api/copilot/capabilities")
    assert cap.status_code==200
    assert cap.json()["generative_ai_configured"] is False
    assert cap.json()["guidance_without_analysis"] is True
    assert cap.json()["policy_sources_connected"] is False


@pytest.mark.parametrize("question,expected",[
    ("Apakah zoning atau RT tapak ini?","RT/RSN"),
    ("Adakah tanah ini selamat daripada banjir?","JPS"),
    ("Bagaimana dapatkan DEM dan kelas cerun?","GLO-30"),
    ("Boleh bina berapa rumah?","Bilangan"),
])
def test_workflow_without_report_does_not_invent_site_facts(question,expected):
    result=TestClient(app).post("/api/copilot/assess",json={"question":question})
    assert result.status_code==200,result.text
    content=result.json()
    assert content["analysis_id"] is None
    assert content["mode"]=="workflow_guidance"
    assert content["evidence"] is None
    assert expected in content["response"]
    assert "belum ada analisis GIS" in content["response"]


def test_rule_based_slope_answer_is_specific_and_has_evidence(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response=assistant.assess(REPORT,"Bagaimana taburan kelas cerun dan risiko kecerunan?")
    assert response["mode"]=="deterministic_evidence_summary"
    assert "Class III" in response["response"]
    assert "20.00%" in response["response"]
    assert "GLO-90" in response["response"]
    assert "82.50%" in response["response"]
    assert "bukan AI generatif" in response["response"]
    assert response["evidence"]["analysis_id"] == REPORT["analysis_id"]
    assert response["evidence"]["coverage_percent_est"] == 82.5


@pytest.mark.parametrize("question,expected",[
    ("Adakah tapak ini berisiko banjir?","Tidak dapat menyatakan"),
    ("Apakah zoning dan RT tapak?","tidak dapat mengesahkan"),
    ("Berapa rumah boleh dibina?","Tidak wajar menganggarkan"),
    ("Apakah julat elevasi tapak?","26.00 m"),
    ("Tapak ini sesuai perumahan?","belum cukup"),
])
def test_question_routing_never_approves_planning_use(monkeypatch,question,expected):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r=assistant.assess(REPORT,question)
    assert expected.casefold() in r["response"].casefold()
    assert "Batasan" in r["response"]


def test_configured_llm_receives_compact_measured_facts_not_full_polygon(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","fake-unit-test-key")
    calls=[]
    class FakeResponses:
        def create(self,**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text="**Penemuan:** Data telah dianalisis.\n\n**Batasan:** Bukan kelulusan PBT.")
    class FakeOpenAI:
        def __init__(self,**kwargs):
            self.responses=FakeResponses()
    monkeypatch.setitem(sys.modules,"openai",SimpleNamespace(OpenAI=FakeOpenAI))
    r=assistant.assess(REPORT,"Apakah cerun purata?")
    assert r["mode"]=="llm_grounded"
    assert len(calls)==1
    sent=calls[0]["input"]
    assert "8.4" in sent
    assert "source_tile_urls" not in sent
    assert "coordinates" not in sent
    assert "fake-unit-test-key" not in sent


def test_model_error_never_leaks_key_and_returns_grounded_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","fake-secret-key")
    class BadOpenAI:
        def __init__(self,**kwargs):
            raise TimeoutError("Do not leak this error body")
    monkeypatch.setitem(sys.modules,"openai",SimpleNamespace(OpenAI=BadOpenAI))
    r=assistant.assess(REPORT,"Apakah kecerunan tapak?")
    assert r["mode"]=="fallback_after_ai_error"
    assert "fake-secret-key" not in json.dumps(r)
    assert "TimeoutError" in r["notice"]
    assert "purata cerun" in r["response"]
