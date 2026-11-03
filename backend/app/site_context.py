"""Privacy-aware on-demand surrounding-site discovery from OpenStreetMap.

This is COMMUNITY geographic context, not a legal/public-authority road,
landuse, facility inventory, zoning or flood-risk certification. No Google
data is scraped. A request sends ONLY rounded project representative-point
lat/lon + search radius to a public Overpass server, never a private polygon.
No mock/fallback observations are returned when the service is offline.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException
from pyproj import Geod
from shapely.geometry import shape

# Two documented public, best-effort instances; production can use a
# licensed/self-hosted provider after explicit operator configuration.
OVERPASS_ENDPOINT="https://overpass.private.coffee/api/interpreter"
OVERPASS_FALLBACK="https://overpass-api.de/api/interpreter"
# Documented global-coverage fallback; regional-only Overpass servers must not
# be used for Malaysian sites.
OVERPASS_VK_GLOBAL="https://maps.mail.ru/osm/tools/overpass/api/interpreter"
OVERPASS_CH_KEY_ENDPOINT="https://api.overpass.ch/v1/interpreter"


def _providers() -> list[tuple[str, dict[str, str]]]:
    # A free/paid API key, if explicitly configured by the operator, gives
    # priority access to a managed hosted provider. Never expose the key in
    # endpoint URLs, diagnostics or browser responses.
    key=os.getenv("PLANEXUS_OVERPASS_CH_API_KEY","").strip()
    choices: list[tuple[str,dict[str,str]]]=[]
    if key:
        choices.append((OVERPASS_CH_KEY_ENDPOINT,{"X-API-Key":key}))
    choices.extend((endpoint,{}) for endpoint in
                   (OVERPASS_ENDPOINT,OVERPASS_VK_GLOBAL,OVERPASS_FALLBACK))
    return choices
OSM_LICENSE="https://www.openstreetmap.org/copyright"
CATEGORIES=("education","healthcare","transport","retail","parks","civic","roads","waterways")
MAX_RESULTS=6500
MAX_RESPONSE_BYTES=8*1024*1024
_GEOD=Geod(ellps="WGS84")


def geometry_digest(geometry: dict[str,Any]) -> str:
    return hashlib.sha256(json.dumps(geometry,sort_keys=True,
                                      separators=(",",":")).encode()).hexdigest()


def build_query(latitude: float, longitude: float, radius_m: int) -> str:
    if not 250 <= radius_m <= 2000:
        raise HTTPException(422,"Radius saringan sekitar mesti 250–2000 meter.")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise HTTPException(422,"Koordinat WGS84 tidak sah.")
    near=f"around:{radius_m},{latitude:.5f},{longitude:.5f}"
    return ('[out:json][timeout:24][maxsize:16777216];('
            f'nwr({near})["amenity"~"^(school|college|university|kindergarten|hospital|clinic|doctors|pharmacy|police|fire_station|townhall|library|community_centre|bus_station)$"];'
            f'nwr({near})["public_transport"];'
            f'nwr({near})["railway"~"^(station|halt|tram_stop)$"];'
            f'nwr({near})["shop"~"^(supermarket|mall|convenience)$"];'
            f'nwr({near})["leisure"="park"];'
            f'way({near})["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|unclassified|service)$"];'
            f'way({near})["waterway"~"^(river|stream|drain|canal)$"];'
            ');out center tags;')


def _category(tags: dict[str,Any]) -> str | None:
    if "highway" in tags:
        return "roads"
    if "waterway" in tags:
        return "waterways"
    amenity=tags.get("amenity","")
    if amenity in ("school","college","university","kindergarten"):
        return "education"
    if amenity in ("hospital","clinic","doctors","pharmacy"):
        return "healthcare"
    if amenity in ("police","fire_station","townhall","library","community_centre"):
        return "civic"
    if amenity=="bus_station" or "public_transport" in tags or tags.get("railway") in ("station","halt","tram_stop"):
        return "transport"
    if tags.get("shop") in ("supermarket","mall","convenience"):
        return "retail"
    if tags.get("leisure")=="park":
        return "parks"
    return None


def fetch_context(geometry: dict[str,Any], *, radius_m: int=1500) -> dict[str,Any]:
    # A representative point is inside the site even for concave polygons,
    # unlike the geometric centroid which can be outside it.
    centre=shape(geometry).representative_point()
    lat,lon=round(float(centre.y),5),round(float(centre.x),5)
    query=build_query(lat,lon,radius_m)
    # Public Overpass instances are frequently rate-limited (429/504);
    # try at most one documented alternative, without inventing a 0-count
    # dataset. Do not follow redirects into arbitrary hosts.
    data=None
    used_endpoint=None
    problems=[]
    # Server-side Overpass QL allows 24 seconds of execution. A 20-second
    # client read timeout made slow-but-successful queries fail prematurely.
    # Keep DNS/connect short; allow enough time for the declared query limit.
    with httpx.Client(timeout=httpx.Timeout(36.0,connect=6.0),
                      follow_redirects=False) as client:
        for endpoint,provider_headers in _providers():
            try:
                response=client.post(endpoint,data={"data":query},
                                     headers={"User-Agent":"PLANEXUS-AI-private-site-screening/1.0",
                                              "Accept":"application/json",**provider_headers})
                response.raise_for_status()
                if len(response.content)>MAX_RESPONSE_BYTES:
                    raise ValueError("OSM response exceeds bounded payload.")
                decoded=response.json()
                if not isinstance(decoded,dict):
                    raise ValueError("Overpass did not return a JSON object.")
                # Overpass sometimes returns HTTP 200 with a 'remark' timeout
                # plus partial/empty elements. Never claim that as a valid scan.
                if isinstance(decoded.get("remark"),str) and decoded["remark"].strip():
                    raise ValueError("Overpass reported a query error: "+decoded["remark"][:150])
                if not isinstance(decoded.get("elements"),list):
                    raise ValueError("Overpass did not return JSON elements.")
                data=decoded
                used_endpoint=endpoint
                break
            except (httpx.HTTPError,ValueError,UnicodeDecodeError) as exc:
                status=exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
                problems.append({"provider":endpoint.split("/")[2],
                                 "type":type(exc).__name__,"http_status":status})
    if data is None:
        raise HTTPException(503,
            "Sumber OpenStreetMap/Overpass tidak tersedia pada pelayan yang dikonfigurasi; "
            "tiada jalan atau kemudahan direka. Status: "+json.dumps(problems))
    elements=data.get("elements") if isinstance(data,dict) else None
    if not isinstance(elements,list) or len(elements)>MAX_RESULTS:
        raise HTTPException(503,"Respons OSM melebihi had atau tidak mempunyai rekod yang sah.")
    grouped={key:0 for key in CATEGORIES}
    named=[]
    seen=set()
    for e in elements:
        if not isinstance(e,dict) or e.get("type") not in ("node","way","relation"):
            continue
        try:
            osm_id=int(e["id"])
        except (KeyError,ValueError,TypeError):
            continue
        marker=(e["type"],osm_id)
        if marker in seen:
            continue
        seen.add(marker)
        tags=e.get("tags") or {}
        if not isinstance(tags,dict):
            continue
        kind=_category(tags)
        if not kind:
            continue
        grouped[kind]+=1
        name=tags.get("name") or tags.get("name:ms") or tags.get("name:en")
        if not isinstance(name,str) or not name.strip() or kind in ("roads","waterways"):
            continue
        point=e.get("center",e)
        try:
            x,y=float(point["lon"]),float(point["lat"])
            if not (math.isfinite(x) and math.isfinite(y)):
                continue
            _,_,distance=_GEOD.inv(lon,lat,x,y)
        except (KeyError,ValueError,TypeError):
            continue
        if distance > radius_m+100:
            continue
        named.append({
            "name":name.strip()[:120],"category":kind,
            "distance_from_reference_point_m":round(distance),
            "coordinates_wgs84":[round(x,6),round(y,6)],
            "osm_url":f"https://www.openstreetmap.org/{e['type']}/{osm_id}",
            "osm_feature_id":f"{e['type']}/{osm_id}",
        })
    named.sort(key=lambda v:(v["distance_from_reference_point_m"],v["name"]))
    osm_meta=data.get("osm3s") if isinstance(data,dict) else None
    dataset_timestamp=(osm_meta.get("timestamp_osm_base") if isinstance(osm_meta,dict) else None)
    if not isinstance(dataset_timestamp,str) or not dataset_timestamp.strip():
        dataset_timestamp=None
    return {
        "status":"retrieved","source_id":"openstreetmap-overpass-community",
        "source_name":"© OpenStreetMap contributors / Overpass",
        "source_url":OSM_LICENSE,"api_endpoint":used_endpoint,
        "provider_failures_before_success":problems,
        "retrieval_service_reliability":"third_party_best_effort_unless_hosted_plan_configured",
        "licence":"ODbL; https://www.openstreetmap.org/copyright",
        "retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
        "dataset_timestamp_utc":dataset_timestamp,
        "source_quality":"community_unverified_not_official",
        "reference_point_wgs84":{"latitude":lat,"longitude":lon},
        "radius_m":radius_m,"counts":grouped,"named_places":named[:30],
        "returned_feature_count":sum(grouped.values()),
        "named_places_truncated":len(named)>30,
        "geometry_sha256":geometry_digest(geometry),
        "warnings":[
            "Sumber komuniti OpenStreetMap; rekod mungkin tidak lengkap, lapuk atau salah. Tiada data contoh ditambah.",
            "Radius berpusat pada satu titik di dalam tapak, BUKAN jarak setiap bahagian sempadan.",
            "Jarak ialah anggaran garis lurus daripada titik rujukan, bukan jarak memandu atau laluan masuk.",
            "Bilangan jalan ialah bilangan segmen OSM, BUKAN bilangan akses sah ke tapak.",
            "Waterway OSM bukan pemetaan banjir, kapasiti saliran atau data JPS yang disahkan.",
            "Tag dan nama OSM tidak mengesahkan kewujudan kemudahan, tahap perkhidmatan atau status PBT.",
            "Koordinat titik rujukan dibundarkan 5 perpuluhan dan dihantar kepada pelayan Overpass awam.",
        ],
    }


def _path(data_dir:Path,project_id:str)->Path:
    # project_id checked by parent FastAPI ownership middleware.
    return data_dir/"site_context"/(project_id+".json")


def get_cached_context(data_dir:Path,project_id:str,geometry:dict[str,Any]|None)->dict[str,Any]:
    if geometry is None:
        return {"exists":False,"reason":"project_has_no_boundary"}
    file=_path(data_dir,project_id)
    if not file.is_file():
        return {"exists":False,"reason":"not_scanned"}
    try:
        data=json.loads(file.read_text(encoding="utf-8"))
        if data.get("geometry_sha256")!=geometry_digest(geometry):
            return {"exists":False,"reason":"boundary_changed_rescan_required"}
        return {"exists":True,"context":data}
    except (OSError,ValueError,AttributeError):
        return {"exists":False,"reason":"cached_result_unreadable"}


def save_context(data_dir:Path,project_id:str,result:dict[str,Any])->None:
    target=_path(data_dir,project_id)
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=target.parent,prefix=".context-",suffix=".tmp")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(result,stream,ensure_ascii=False,allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp,target)
    finally:
        Path(tmp).unlink(missing_ok=True)
