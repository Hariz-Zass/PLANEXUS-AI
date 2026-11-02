from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from rasterio.errors import RasterioError
from shapely.geometry import shape

from .copilot import assess, capabilities, workflow_guidance
from .geometry import validate_site
from .project_store import (create_project, list_projects, get_project, update_project, remove_project,
                            attach_analysis, activate_analysis)
from .settings import CORS_ORIGINS, DATA_DIR, MAX_UPLOAD_BYTES
from .sources import SOURCE_CATALOG, acquire_copernicus
from .terrain import analyze_terrain

app = FastAPI(title="PLANEXUS AI Terrain API", version="0.3.0", description="Evidence-first geospatial screening. Local development only; no authentication.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


class SitePayload(BaseModel):
    geometry: dict[str, Any]
    project_id: str | None = None


class CopilotPayload(BaseModel):
    analysis_id: str | None = None
    question: str = Field(min_length=3, max_length=800)


def job_dir(analysis_id: str) -> Path:
    try:
        value = str(uuid.UUID(analysis_id))
    except ValueError as ex:
        raise HTTPException(422, "ID analisis tidak sah.") from ex
    return DATA_DIR / "jobs" / value


def save_report(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    (path / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def load_report(analysis_id: str) -> dict[str, Any]:
    path = job_dir(analysis_id) / "result.json"
    if not path.is_file():
        raise HTTPException(404, "Analisis tidak ditemui.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "PLANEXUS AI Terrain", "storage": "local-persistent-folder", "production_ready": False}


@app.get("/api/sources")
def sources():
    return {"sources": SOURCE_CATALOG, "note": "Sumber data tidak sama dengan ketepatan ukur tapak. Tiada kelulusan pembangunan dinilai."}


class NewProjectPayload(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    geometry: dict[str, Any] | None = None


class UpdateProjectPayload(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = None
    description: str | None = None
    geometry: dict[str, Any] | None = None


class ActivateAnalysisPayload(BaseModel):
    analysis_id: str


@app.get("/api/projects")
def projects_list():
    return {"projects": list_projects(DATA_DIR), "storage": "local-sqlite; no cloud sync; single trusted user only"}


@app.post("/api/projects", status_code=201)
def projects_create(payload: NewProjectPayload):
    return create_project(DATA_DIR, payload.name, payload.description, payload.geometry)


@app.get("/api/projects/{project_id}")
def projects_get(project_id: str):
    return get_project(DATA_DIR, project_id)


@app.patch("/api/projects/{project_id}")
def projects_update(project_id: str, payload: UpdateProjectPayload):
    fields: dict[str, Any] = {}
    for key in ("name", "description", "geometry"):
        if key in payload.model_fields_set:
            fields[key] = getattr(payload, key)
    if not fields:
        return get_project(DATA_DIR, project_id)
    return update_project(DATA_DIR, project_id, payload.expected_revision, **fields)


@app.delete("/api/projects/{project_id}", status_code=204)
def projects_delete(project_id: str):
    remove_project(DATA_DIR, project_id)
    return Response(status_code=204)


@app.post("/api/projects/{project_id}/activate-analysis")
def projects_activate_analysis(project_id: str, payload: ActivateAnalysisPayload):
    report = load_report(payload.analysis_id)
    return activate_analysis(DATA_DIR, project_id, payload.analysis_id, report)


@app.post("/api/site/inspect")
def inspect_site(payload: SitePayload):
    geometry = validate_site(payload.geometry)
    from .geometry import area_km2
    return {"geometry": geometry, "area_ha": round(area_km2(geometry) * 100, 3), "bounds": list(shape(geometry).bounds), "message": "Sempadan tapak sah dari segi geometri; status hak milik dan zoning belum disemak."}


def verify_project_for_analysis(project_id: str | None, geometry: dict[str, Any]) -> None:
    if project_id is None:
        return
    project = get_project(DATA_DIR, project_id)
    if project["geometry"] is not None and not shape(project["geometry"]).equals(shape(geometry)):
        raise HTTPException(409, "Sempadan projek tidak sama dengan tapak analisis. Buka semula projek.")


@app.post("/api/terrain/auto")
def terrain_auto(payload: SitePayload):
    geometry = validate_site(payload.geometry)
    verify_project_for_analysis(payload.project_id, geometry)
    analysis_id = str(uuid.uuid4())
    directory = job_dir(analysis_id)
    try:
        raster, source = acquire_copernicus(shape(geometry).bounds, directory)
        report = analyze_terrain(geometry, raster, source, analysis_id)
        saved = save_report(directory, report)
        if payload.project_id is not None:
            attach_analysis(DATA_DIR, payload.project_id, saved)
        return saved
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


@app.post("/api/terrain/upload")
def terrain_upload(
    geometry: str = Form(...),
    file: UploadFile = File(...),
    source_name: str = Form(...),
    vertical_unit: str = Form(...),
    height_model: str = Form(...),
    vertical_datum: str = Form("unknown"),
    project_id: str | None = Form(None),
):
    if vertical_unit != "metres":
        raise HTTPException(422, "V1 menerima ketinggian dalam unit meter sahaja; sila sahkan unit fail ukur.")
    if height_model not in ("DTM", "DSM", "DEM-unknown"):
        raise HTTPException(422, "height_model tidak sah.")
    if len(source_name.strip()) < 3 or len(source_name) > 120:
        raise HTTPException(422, "Sila masukkan sumber data (3–120 aksara).")
    if not file.filename or not file.filename.lower().endswith(('.tif', '.tiff')):
        raise HTTPException(422, "Fail mestilah GeoTIFF .tif/.tiff.")
    try:
        geometry_value = json.loads(geometry)
    except json.JSONDecodeError as ex:
        raise HTTPException(422, "Geometri JSON tidak sah.") from ex
    geom = validate_site(geometry_value)
    verify_project_for_analysis(project_id, geom)
    analysis_id = str(uuid.uuid4())
    directory = job_dir(analysis_id)
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / "uploaded_source.tif"
    total = 0
    try:
        with file_path.open("wb") as dest:
            while chunk := file.file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Fail melebihi 60 MB bagi V1.")
                dest.write(chunk)
        if total < 100:
            raise HTTPException(422, "GeoTIFF kosong atau rosak.")
        metadata = {
            "id": "user-upload", "name": source_name.strip(), "publisher": "User supplied — not independently authenticated",
            "data_type": height_model, "nominal_resolution_m": None,
            "access": "Locally uploaded; no external fetching", "reference": None,
            "metadata": None, "vertical_datum": vertical_datum.strip()[:120] or "unknown",
            "vertical_unit": "metres (explicitly declared by uploader)",
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "verified": "CRS and raster contents inspected; source authenticity and survey accuracy NOT verified",
        }
        report = analyze_terrain(geom, file_path, metadata, analysis_id)
        saved = save_report(directory, report)
        if project_id is not None:
            attach_analysis(DATA_DIR, project_id, saved)
        return saved
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


@app.get("/api/analyses")
def list_analyses():
    directory = DATA_DIR / "jobs"
    if not directory.exists():
        return {"analyses": []}
    results = []
    for path in directory.iterdir():
        if not path.is_dir() or not (path / "result.json").exists():
            continue
        try:
            item = json.loads((path / "result.json").read_text(encoding="utf-8"))
            results.append({"analysis_id": item["analysis_id"], "created_at_utc": item["created_at_utc"], "site_area_ha": item["metrics"]["site_area_ha"], "source_name": item["source"]["name"]})
        except (OSError, ValueError, KeyError):
            continue
    return {"analyses": sorted(results, key=lambda r: r["created_at_utc"], reverse=True)[:50]}


@app.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    return load_report(analysis_id)


@app.get("/api/copilot/capabilities")
def copilot_capabilities():
    return capabilities()


@app.post("/api/copilot/assess")
def copilot(payload: CopilotPayload):
    # Operational/workflow guidance can be used before terrain analysis.
    # Site-specific answers MUST be bound to an existing, saved GIS report.
    if payload.analysis_id is None:
        return {"analysis_id": None, **workflow_guidance(payload.question)}
    report = load_report(payload.analysis_id)
    return {"analysis_id": payload.analysis_id, **assess(report, payload.question)}


@app.get("/api/analyses/{analysis_id}/report.md", response_class=PlainTextResponse)
def download_report(analysis_id: str):
    report = load_report(analysis_id)
    m = report["metrics"]
    classification = "\n".join(f"| {c['name']} | {c['min_deg']}°–{str(c['max_deg']) + '°' if c['max_deg'] is not None else 'lebih'} | {c['area_ha_est']} | {c['percent_of_valid_slope']}% |" for c in m["slope_classes"])
    warnings = "\n".join("- " + w for w in report["warnings"])
    text = f"""# PLANEXUS AI — Terrain Screening Report

**Analysis ID:** `{analysis_id}`  
**Created UTC:** {report['created_at_utc']}  
**Data source:** {report['source']['name']}  
**Source reference:** {report['source'].get('reference') or 'User supplied; independent source unverified'}  
**Status:** PRELIMINARY TOPOGRAPHY SCREENING ONLY — NOT PLANNING APPROVAL

## Site statistics

- Site area: {m['site_area_ha']} ha
- Elevation (min/mean/max): {m['elevation_min_m']} / {m['elevation_mean_m']} / {m['elevation_max_m']} metres (assumed per source declaration)
- Mean slope: {m['slope_mean_deg']}°; maximum slope: {m['slope_max_deg']}°
- Valid elevation pixel coverage (approx.): {m['coverage_percent_est']}%
- Resolution (approx.): {m['analysis_resolution_m_est']} m
- Projected CRS: {m['horizontal_crs']}

## Slope classes (pixel-based area estimates)

| Class | Degree band | Area (ha) | Share of valid slope |
|---|---|---:|---:|
{classification}

## Method

{m['method']}

## Data quality and limits

{warnings}

## Outstanding planning checks

Applicable RT/RSN/RFN/GPP, site access, flood risk, geotechnics, utilities, ownership and verified detail survey.

## Data provenance

```json
{json.dumps(report['source'], ensure_ascii=False, indent=2)}
```
"""
    return PlainTextResponse(text, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="planexus-terrain-{analysis_id[:8]}.md"'})
