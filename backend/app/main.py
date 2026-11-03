from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel, Field
from rasterio.errors import RasterioError
from shapely.geometry import shape

from .copilot import assess, capabilities, workflow_guidance
from .proposal_engine import ProposalInput
from .layout_engine import LayoutInput, screen_layout
from .layout_store import get_layout, save_layout
from .policy_registry import catalog as policy_catalog, evaluate_policy, answer_gpp_question
from .proposal_store import create_proposal, list_proposals, get_proposal, update_proposal, delete_proposal
from .geometry import validate_site
from .project_store import (create_project, list_projects, get_project, update_project, remove_project,
                            attach_analysis, activate_analysis)
from .settings import CORS_ORIGINS, DATA_DIR, MAX_UPLOAD_BYTES
from .storage_health import check_storage
from . import auth
from .sources import SOURCE_CATALOG, acquire_copernicus
from .terrain import analyze_terrain

app = FastAPI(title="PLANEXUS AI Terrain API", version="0.9.0", description="Evidence-first GIS. Invite-only private workspace with authenticated project ownership; NOT a public multi-tenant production service.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                   allow_headers=["Content-Type", "X-CSRF-Token"])


@app.middleware("http")
async def protect_private_api(request: Request, call_next):
    """Fail closed for all project and GIS operations, including direct URLs.

    Authentication checks happen BEFORE routing or reading a GIS upload; this
    prevents cross-user project and analysis IDs being used in any module.
    """
    path = request.url.path
    if not path.startswith("/api/") or request.method == "OPTIONS":
        return await call_next(request)
    if request.method in auth.MUTATION_METHODS:
        state = check_storage(DATA_DIR)
        if not state["ready"]:
            return JSONResponse(status_code=503, content={
                "detail": state["detail"], "storage": state["type"]
            })
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in CORS_ORIGINS:
            return JSONResponse(status_code=403,content={"detail":"Origin tidak dibenarkan."})
    if path in ("/api/health","/api/auth/login","/api/auth/register"):
        return await call_next(request)
    try:
        identity = auth.request_user(request, DATA_DIR)
        request.state.user = identity
        parts = path.split("/")
        if len(parts) >= 4 and parts[2] == "projects":
            auth.require_project(DATA_DIR, parts[3], identity["id"])
        if len(parts) >= 4 and parts[2] == "analyses":
            auth.require_analysis(DATA_DIR, parts[3], identity["id"])
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail":exc.detail})
    return await call_next(request)


class LoginPayload(BaseModel):
    email: str = Field(min_length=3,max_length=254)
    password: str = Field(min_length=1,max_length=128)


class RegisterPayload(LoginPayload):
    display_name: str = Field(min_length=2,max_length=100)
    invite_token: str = Field(min_length=16,max_length=256)


def secure_auth_cookie(request: Request) -> bool:
    configured = os.getenv("PLANEXUS_COOKIE_SECURE", "").strip().lower()
    if configured in ("1","true","yes","on"):
        return True
    if configured in ("0","false","no","off"):
        return False
    # Default Secure for every non-local origin. Under HTTPS proxies set
    # PLANEXUS_COOKIE_SECURE=1 explicitly in server configuration.
    return request.url.hostname not in ("localhost","127.0.0.1","::1")


@app.post("/api/auth/register",status_code=201)
def register_account(payload: RegisterPayload):
    user = auth.register(DATA_DIR,payload.email,payload.display_name,
                         payload.password,payload.invite_token)
    return {"user":user,"notice":"Akaun didaftarkan. Login untuk memulakan sesi."}


@app.post("/api/auth/login")
def login_account(payload: LoginPayload, response: Response, request: Request):
    user, secret, csrf = auth.authenticate(DATA_DIR,payload.email,payload.password)
    response.set_cookie(
        auth.COOKIE_NAME,secret,httponly=True,secure=secure_auth_cookie(request),
        samesite="lax",path="/",max_age=auth.SESSION_HOURS*3600
    )
    response.headers["Cache-Control"]="no-store"
    return {"user":user,"csrf_token":csrf}


@app.get("/api/auth/me")
def current_account(request: Request, response: Response):
    # Middleware has already checked the session. Re-read the matching CSRF
    # token, returned only to an authorized browser origin.
    identity = request.state.user
    current = auth.session(DATA_DIR, request.cookies.get(auth.COOKIE_NAME))
    if current is None:
        raise HTTPException(401,"Sesi telah tamat.")
    response.headers["Cache-Control"]="no-store"
    return {"user":identity,"csrf_token":current[1]}


@app.post("/api/auth/logout",status_code=204)
def logout_account(request: Request, response: Response):
    auth.revoke(DATA_DIR,request.cookies.get(auth.COOKIE_NAME))
    response.delete_cookie(auth.COOKIE_NAME,path="/")
    response.headers["Cache-Control"]="no-store"
    return Response(status_code=204, headers={
        "Set-Cookie":f"{auth.COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax",
        "Cache-Control":"no-store"
    })


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
    """Atomically replace the report so interrupted writes cannot corrupt it."""
    path.mkdir(parents=True, exist_ok=True)
    staged: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path,
            prefix=".result-", suffix=".tmp", delete=False
        ) as handle:
            staged = Path(handle.name)
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staged, path / "result.json")
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
    return report


def load_report(analysis_id: str) -> dict[str, Any]:
    path = job_dir(analysis_id) / "result.json"
    if not path.is_file():
        raise HTTPException(404, "Analisis tidak ditemui.")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(503, "Laporan GIS disimpan tetapi tidak dapat dibaca. Semak integriti storan dan pulihkan daripada backup yang disahkan.") from exc
    if not isinstance(report, dict) or report.get("analysis_id") != analysis_id:
        raise HTTPException(503, "ID laporan GIS tidak sepadan dengan fail simpanan. Data ini tidak digunakan.")
    return report


@app.get("/api/health")
def health():
    state = check_storage(DATA_DIR)
    payload = {
        "status": "ok" if state["ready"] else "error",
        "service": "PLANEXUS AI Terrain",
        "storage": state["type"],
        "persistent": state["persistent"],
        "detail": state["detail"],
        "public_multiuser_ready": False,
        "production_ready": False,  # backward-compatible explicit caution
    }
    if not state["ready"]:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get("/api/policy/catalog")
def gpp_catalog():
    """Machine-readable curated source list; catalog-only documents are NOT indexed."""
    return policy_catalog()


@app.post("/api/policy/assess")
def gpp_assess(payload: ProposalInput):
    """Dry-run numeric checks, no project save and NO approval determination."""
    return evaluate_policy(payload)


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
def projects_list(request: Request):
    return {"projects": list_projects(DATA_DIR,owner_id=request.state.user["id"]),
            "storage": "private-sqlite; server-side project ownership; cloud durability requires mounted volume"}


@app.post("/api/projects", status_code=201)
def projects_create(payload: NewProjectPayload, request: Request):
    return create_project(DATA_DIR,payload.name,payload.description,payload.geometry,
                          owner_id=request.state.user["id"])


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


class ProposalUpdatePayload(BaseModel):
    expected_revision: int = Field(ge=1)
    proposal: ProposalInput


def active_terrain_report(project_id: str) -> dict[str, Any] | None:
    """Only a report explicitly linked as the project's currently active GIS context."""
    project = get_project(DATA_DIR, project_id)
    if not project["active_analysis_id"]:
        return None
    try:
        return load_report(project["active_analysis_id"])
    except (HTTPException, OSError, ValueError):
        # Preserve proposals; they will be displayed as lacking GIS evidence.
        return None


class LayoutSavePayload(BaseModel):
    expected_revision: int = Field(ge=0)
    inputs: LayoutInput


@app.get("/api/projects/{project_id}/layout")
def layout_get(project_id: str):
    return get_layout(DATA_DIR, project_id, active_terrain_report(project_id))


@app.post("/api/projects/{project_id}/layout/preview")
def layout_preview(project_id: str, payload: LayoutInput):
    project = get_project(DATA_DIR, project_id)
    if not project["geometry"]:
        raise HTTPException(422, "Save a site boundary before layout screening.")
    return {
        "project_id":project["id"],
        "preview":screen_layout(project["geometry"], payload, active_terrain_report(project_id)),
        "saved":False,
        "notice":"Unsaved geometry-only layout preview: user-entered road width, not physically measured or statutory approval.",
    }


@app.put("/api/projects/{project_id}/layout")
def layout_save(project_id: str, payload: LayoutSavePayload):
    return save_layout(DATA_DIR, project_id, payload.inputs,
                       payload.expected_revision, active_terrain_report(project_id))


@app.get("/api/projects/{project_id}/proposals")
def proposals_list(project_id: str):
    active = active_terrain_report(project_id)
    return list_proposals(DATA_DIR, project_id, active)


@app.post("/api/projects/{project_id}/proposals", status_code=201)
def proposals_create(project_id: str, payload: ProposalInput):
    active = active_terrain_report(project_id)
    return create_proposal(DATA_DIR, project_id, payload, active)


@app.get("/api/projects/{project_id}/proposals/{proposal_id}")
def proposals_get(project_id: str, proposal_id: str):
    active = active_terrain_report(project_id)
    return get_proposal(DATA_DIR, project_id, proposal_id, active)


@app.put("/api/projects/{project_id}/proposals/{proposal_id}")
def proposals_update(project_id: str, proposal_id: str, payload: ProposalUpdatePayload):
    active = active_terrain_report(project_id)
    return update_proposal(DATA_DIR, project_id, proposal_id, payload.proposal, payload.expected_revision, active)


@app.delete("/api/projects/{project_id}/proposals/{proposal_id}", status_code=204)
def proposals_delete(project_id: str, proposal_id: str):
    delete_proposal(DATA_DIR, project_id, proposal_id)
    return Response(status_code=204)


@app.post("/api/site/inspect")
def inspect_site(payload: SitePayload):
    geometry = validate_site(payload.geometry)
    from .geometry import area_km2
    return {"geometry": geometry, "area_ha": round(area_km2(geometry) * 100, 3), "bounds": list(shape(geometry).bounds), "message": "Sempadan tapak sah dari segi geometri; status hak milik dan zoning belum disemak."}


def verify_project_for_analysis(project_id: str | None, geometry: dict[str, Any], user_id: str) -> None:
    if project_id is None:
        raise HTTPException(422,"Simpan analisis kepada projek milik akaun anda terlebih dahulu.")
    auth.require_project(DATA_DIR,project_id,user_id)
    project = get_project(DATA_DIR, project_id)
    if project["geometry"] is not None and not shape(project["geometry"]).equals(shape(geometry)):
        raise HTTPException(409, "Sempadan projek tidak sama dengan tapak analisis. Buka semula projek.")


@app.post("/api/terrain/auto")
def terrain_auto(payload: SitePayload, request: Request):
    geometry = validate_site(payload.geometry)
    verify_project_for_analysis(payload.project_id, geometry, request.state.user["id"])
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
    request: Request,
    geometry: str = Form(...),
    file: UploadFile = File(...),
    source_name: str = Form(...),
    vertical_unit: str = Form(...),
    height_model: str = Form(...),
    vertical_datum: str = Form("unknown"),
    project_id: str = Form(...),
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
    verify_project_for_analysis(project_id, geom, request.state.user["id"])
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
def list_analyses(request: Request):
    # Only project-linked reports belonging to this account; never scan the
    # global jobs directory and disclose other users' raster metadata.
    return {"analyses":auth.owned_analyses(DATA_DIR,request.state.user["id"])}


@app.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    return load_report(analysis_id)


@app.get("/api/copilot/capabilities")
def copilot_capabilities():
    return capabilities()


@app.post("/api/copilot/assess")
def copilot(payload: CopilotPayload, request: Request):
    # Even if the prompt routes to generic GPP rules, a supplied analysis_id
    # must belong to the requesting user; never allow ID probing.
    if payload.analysis_id is not None:
        auth.require_analysis(DATA_DIR,payload.analysis_id,request.state.user["id"])
    # Operational/workflow guidance can be used before terrain analysis.
    # Site-specific answers MUST be bound to an existing, saved GIS report.
    if any(token in payload.question.casefold() for token in ("gpp", "garis panduan perancangan", "saiz minimum rumah", "saiz lot minimum", "piawaian perumahan")):
        return {"analysis_id": payload.analysis_id, **answer_gpp_question(payload.question)}
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
    screening = report.get("suitability")
    if screening:
        screen_lines = "\n".join(
            f"| {b['label']} | "
            f"{b['min_deg'] if b['min_deg'] is not None else 'n/a'}–"
            f"{b['max_deg'] if b['max_deg'] is not None else 'upwards'} | "
            f"{b['area_ha_est']} | "
            f"{str(b['share_of_assessed_pct']) + '%' if b['share_of_assessed_pct'] is not None else 'not assessed'} |"
            for b in screening["bands"]
        )
        suitability_block = (
            "\n## Preliminary terrain constraint screening (NOT development approval)\n\n"
            "| Screening group | Slope (degrees) | Cell area (ha, approx.) | Share of assessed slope |\n"
            "|---|---|---:|---:|\n" + screen_lines +
            "\n\nArea with a verified slope sample (pixel estimate): "
            + str(screening["assessed_area_ha_est"]) + " ha.\n"
            + "Unassessed area (approximate, includes pixel-boundary effects): "
            + str(screening["unassessed_area_ha_est"]) + " ha.\n\n"
            + screening["disclaimer"] + "\n\n"
        )
    else:
        suitability_block = "\n## Terrain constraint screening\n\nUnavailable in this older analysis. Rerun DEM analysis to compute it.\n\n"

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

{suitability_block}
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
