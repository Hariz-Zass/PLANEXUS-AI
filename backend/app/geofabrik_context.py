"""Optional offline Geofabrik OSM GeoPackage adapter for Malaysia.

A server operator provisions the licensed regional GeoPackage once, not every
planner. No network calls, simulated features or regulatory zoning claims.
The default live Overpass adapter remains available. GeoPackage snapshots
should be updated by operations; this code does not silently download 500 MB.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import os
from pathlib import Path
from typing import Any

import fiona
from pyproj import CRS, Geod, Transformer
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform

GEOFABRIK_REFERENCE="https://download.geofabrik.de/asia/malaysia-singapore-brunei.html"
OSM_LICENCE="https://www.openstreetmap.org/copyright"
_GEOD=Geod(ellps="WGS84")
MAX_SCANNED=8000
# Geofabrik free GIS extract classifications, NOT a statutory inventory.
_CLASS={
    "education":{"school","college","university","kindergarten"},
    "healthcare":{"hospital","clinic","doctors","pharmacy","dentist"},
    "transport":{"bus_station","bus_stop","railway_station","tram_stop","station","halt"},
    "retail":{"supermarket","mall","convenience","department_store"},
    "parks":{"park","recreation_ground"},
    "civic":{"police","fire_station","town_hall","library","community_centre"},
}
_CATEGORIES=tuple(_CLASS)+("roads","waterways")


def _category(layer: str, fclass: str) -> str | None:
    name=layer.casefold()
    code=fclass.casefold()
    if "road" in name and code in {
        "motorway","trunk","primary","secondary","tertiary","residential",
        "unclassified","service","living_street","road",
    }:
        return "roads"
    if "waterway" in name and code in {"river","stream","drain","canal"}:
        return "waterways"
    if "park" in name and code=="park":
        return "parks"
    for category, names in _CLASS.items():
        if code in names:return category
    return None


def _layer_relevant(name: str) -> bool:
    n=name.lower()
    return any(tag in n for tag in ("pois","traffic","transport","roads","waterways","natural"))


def fetch_geofabrik_context(geometry:dict[str,Any], *, radius_m:int=1500,
                            gpkg_path:Path, geometry_sha256:str) -> dict[str,Any]:
    if not 250 <= radius_m <= 2000:
        raise ValueError("Unsupported local context radius.")
    path=gpkg_path.resolve()
    # Accept a single multi-layer GPKG or a folder of Geofabrik layer GPKGs,
    # because upstream archives may be unpacked into multiple files.
    sources=([path] if path.is_file() and path.suffix.lower()==".gpkg"
             else sorted(path.glob("*.gpkg")) if path.is_dir() else [])
    if not sources or len(sources)>40:
        raise FileNotFoundError("Configured offline Geofabrik GeoPackage file/folder is not available.")
    centre=shape(geometry).representative_point()
    lat,lon=round(float(centre.y),5),round(float(centre.x),5)
    # Conservative bbox for indexed Fiona spatial filters; exact distance is
    # independently checked against WGS84 great-circle distance below.
    latpad=radius_m/110_000 + 0.003
    lonpad=radius_m/(110_000*max(0.2,math.cos(math.radians(lat))))+0.003
    bbox=(lon-lonpad,lat-latpad,lon+lonpad,lat+latpad)
    counts={key:0 for key in _CATEGORIES}
    names=[]
    seen=set()
    scanned=0
    candidates=[(file,layer) for file in sources
                for layer in fiona.listlayers(str(file)) if _layer_relevant(layer)]
    if not candidates:
        raise ValueError("GeoPackage has no supported Geofabrik OSM feature layers.")
    for file,layer in candidates:
        with fiona.open(str(file),layer=layer) as src:
            if not src.crs:
                raise ValueError("Offline OSM layer missing CRS.")
            crs=CRS.from_user_input(src.crs)
            forward=Transformer.from_crs("EPSG:4326",crs,always_xy=True).transform
            inverse=Transformer.from_crs(crs,"EPSG:4326",always_xy=True).transform
            minx,miny,maxx,maxy=bbox
            xs,ys=zip(*(forward(x,y) for x,y in
                        ((minx,miny),(maxx,miny),(maxx,maxy),(minx,maxy))))
            local_bbox=(min(xs),min(ys),max(xs),max(ys))
            for feature in src.filter(bbox=local_bbox):
                scanned+=1
                if scanned>MAX_SCANNED:
                    raise ValueError("Too many extracted features; no partial counts returned.")
                props=dict(feature.get("properties") or {})
                category=_category(layer,str(props.get("fclass") or ""))
                if category is None:continue
                raw_geometry=feature.get("geometry")
                if not raw_geometry:continue
                g=shape(raw_geometry)
                if g.is_empty:continue
                rep=shapely_transform(inverse,g.representative_point())
                if not (math.isfinite(rep.x) and math.isfinite(rep.y)):continue
                _,_,dist=_GEOD.inv(lon,lat,rep.x,rep.y)
                if dist>radius_m+100:continue
                osm_id=str(props.get("osm_id") or "").strip()
                # Distinct category+layer+feature identity even when OSM ID is
                # absent from an export. Never invent an OSM URL.
                key=(layer,osm_id or str(feature.get("id") or scanned),category)
                if key in seen:continue
                seen.add(key)
                counts[category]+=1
                name=props.get("name")
                if category in ("roads","waterways") or not isinstance(name,str) or not name.strip():
                    continue
                # Geofabrik free layers do not reliably retain the OSM object
                # type, so never guess node/way/relation hyperlinks.
                names.append({
                    "name":name.strip()[:120],"category":category,
                    "distance_from_reference_point_m":round(dist),
                    "coordinates_wgs84":[round(rep.x,6),round(rep.y,6)],
                    "osm_url":OSM_LICENCE,"osm_feature_id":f"geofabrik:{layer}:{osm_id or key[1]}",
                })
    names.sort(key=lambda p:(p["distance_from_reference_point_m"],p["name"]))
    snapshot=os.getenv("PLANEXUS_OSM_EXTRACT_DATE","").strip() or None
    if snapshot:
        try:datetime.fromisoformat(snapshot.replace("Z","+00:00"))
        except ValueError: snapshot=None
    return {
        "status":"retrieved","source_id":"geofabrik-osm-gpkg-snapshot",
        "source_name":"Geofabrik OSM regional extract (community snapshot)",
        "source_url":GEOFABRIK_REFERENCE,
        "api_endpoint":None,"licence":"ODbL; "+OSM_LICENCE,
        "retrieved_at_utc":datetime.now(timezone.utc).isoformat(),
        "dataset_timestamp_utc":snapshot,
        "source_quality":"community_unverified_not_official",
        "retrieval_service_reliability":"offline_snapshot_no_public_api_dependency",
        "reference_point_wgs84":{"latitude":lat,"longitude":lon},
        "radius_m":radius_m,"counts":counts,"named_places":names[:30],
        "named_places_truncated":len(names)>30,
        "returned_feature_count":sum(counts.values()),
        "geometry_sha256":geometry_sha256,
        "warnings":[
            "Open-source OSM snapshot via Geofabrik; not current official facility inventory.",
            "Snapshot may be stale; dataset timestamp only if operator explicitly configured it.",
            "Counts use Geofabrik filtered layers; categories may differ from live Overpass.",
            "Representative geometry-point distance is not physical road access or parcel proximity.",
            "Road segments do not prove legal access; waterways do not prove flood safety.",
            "OSM ODbL attribution is required; do not claim government certification.",
        ],
    }
