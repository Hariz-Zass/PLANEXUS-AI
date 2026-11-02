"""Evidence-first PLANEXUS layout envelope: site, sketched road reservations and slope.

A centreline + a user-entered width defines a MODEL corridor. It does not
measure an existing road, verify ownership, enforce a road network or prove GPP
compliance. A front-road band is NOT an actual building/lot setback check.
No housing units are fitted or approved by this module.
"""
from __future__ import annotations

import math
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pyproj import Transformer
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Polygon, mapping, shape
from shapely.ops import transform, unary_union

from .geometry import local_utm_crs, validate_site
from .policy_registry import PERAK_SOURCE
from .road_network import screen_road_network

MAX_ROADS=12
MAX_VERTICES=200
MAX_SOURCE_FEATURES=750


class LayoutInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name: str=Field(default="Concept road and land envelope",min_length=3,max_length=100)
    road_centerlines: list[dict[str,Any]]=Field(default_factory=list,max_length=MAX_ROADS)
    assumed_road_width_m: float=Field(default=15.24,ge=3,le=60,allow_inf_nan=False)
    front_road_buffer_m: float=Field(default=0,ge=0,le=30,allow_inf_nan=False)
    perimeter_offset_m: float=Field(default=0,ge=0,le=30,allow_inf_nan=False)
    policy_profile: Literal["none","perak_2023"]="none"
    perak_market_segment: Literal[
        "perak_low_cost","perak_middle","perak_affordable","perak_open"
    ] | None=None

    @model_validator(mode="after")
    def validate_road_lines(self)->"LayoutInput":
        self.name=self.name.strip()
        if len(self.name)<3:
            raise ValueError("Layout name requires at least 3 characters.")
        for item in self.road_centerlines:
            if not isinstance(item,dict) or item.get("type")!="LineString":
                raise ValueError("Every road alignment must be a GeoJSON LineString.")
            coords=item.get("coordinates")
            if not isinstance(coords,list) or len(coords)<2 or len(coords)>MAX_VERTICES:
                raise ValueError("Each road needs 2–200 vertices.")
            previous=None
            for coord in coords:
                if (not isinstance(coord,(tuple,list)) or len(coord)!=2
                    or any(isinstance(v,bool) or not isinstance(v,(float,int))
                           or not math.isfinite(v) for v in coord)):
                    raise ValueError("Road coordinates must be finite WGS84 [longitude,latitude] pairs.")
                lon,lat=coord
                if not (-180<=lon<=180 and -90<=lat<=90):
                    raise ValueError("Road vertex outside WGS84 coordinate bounds.")
                if previous is not None and tuple(coord)==previous:
                    raise ValueError("Adjacent duplicate road vertices are not allowed.")
                previous=tuple(coord)
        return self


def _polygons(geom:Any)->list[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom,Polygon):
        return [geom] if geom.area>1e-8 else []
    if isinstance(geom,MultiPolygon):
        return [g for g in geom.geoms if g.area>1e-8]
    if isinstance(geom,GeometryCollection):
        return [p for part in geom.geoms for p in _polygons(part)]
    return []


def _collection(geom:Any,world:Transformer,label:str)->dict[str,Any]:
    # Avoid claiming that coordinate simplification is an area calculation.
    polygons=_polygons(geom)
    # Clip/map output only, all area summaries use unsimplified projected data.
    collection={"type":"FeatureCollection","features":[]}
    if len(polygons)>120:
        collection["map_truncated"]=True
        polygons=sorted(polygons,key=lambda x:x.area,reverse=True)[:120]
    for poly in polygons:
        render=poly.simplify(.25,preserve_topology=True)
        collection["features"].append({
            "type":"Feature","properties":{"label":label,"screening_only":True},
            "geometry":mapping(transform(world.transform,render)),
        })
    return collection


def _area(geom:Any)->float:
    return round(max(0,float(geom.area))/10000,5)


def screen_layout(
    site_geometry:dict[str,Any],
    input:LayoutInput,
    active_report:dict[str,Any]|None=None,
)->dict[str,Any]:
    """Projected metres; do not substitute report cell totals for parcel area."""
    validated=validate_site(site_geometry)
    crs=local_utm_crs(validated)
    local=Transformer.from_crs("EPSG:4326",crs,always_xy=True)
    world=Transformer.from_crs(crs,"EPSG:4326",always_xy=True)
    site=transform(local.transform,shape(validated))
    total_area=site.area
    if total_area<=0:
        raise HTTPException(422,"Site polygon has no measurable projected area.")

    lines=[]
    for entry in input.road_centerlines:
        line=transform(local.transform,shape(entry))
        if not isinstance(line,LineString) or line.length<2:
            raise HTTPException(422,"Every road sketch must have at least 2 metres of centreline.")
        if not site.buffer(0.35).covers(line):
            raise HTTPException(422,"A road centreline must stay within the current site boundary. Move the sketch inside the site.")
        lines.append(line)

    if lines:
        corridor=unary_union([line.buffer(input.assumed_road_width_m/2,cap_style=2,join_style=2) for line in lines]).intersection(site)
        # Interpret this as an assumed setback envelope from drawn road
        # centreline, NOT actual building setbacks or surveyed front boundaries.
        if input.front_road_buffer_m>0:
            wider=unary_union([
                line.buffer(input.assumed_road_width_m/2+input.front_road_buffer_m,
                            cap_style=2,join_style=2)
                for line in lines
            ]).intersection(site)
            road_front_zone=wider.difference(corridor)
        else:
            road_front_zone=GeometryCollection()
    else:
        corridor=GeometryCollection()
        road_front_zone=GeometryCollection()

    if input.perimeter_offset_m:
        inner=site.buffer(-input.perimeter_offset_m,join_style=2)
        outer_band=site.difference(inner)
    else:
        outer_band=GeometryCollection()
    exclusions=unary_union([corridor,road_front_zone,outer_band]).intersection(site)
    remaining=site.difference(exclusions)
    return_report={
        "version":"1.1.0",
        "method":"WGS84 boundary projected into site-local UTM. Sketched road centrelines buffered by half of assumed width; assumed front-road margin and optional site perimeter offset excluded from polygon.",
        "projected_crs":crs.to_string(),
        "site_area_ha":_area(site),
        "road_centerline_length_m":round(sum(line.length for line in lines),2),
        "road_corridor_ha":_area(corridor),
        "road_front_margin_ha":_area(road_front_zone),
        "perimeter_exclusion_ha":_area(outer_band),
        "combined_exclusions_ha":_area(exclusions),
        "gross_unencumbered_ha":_area(remaining),
        "road_count":len(lines),
        "terrain_status":"no_active_suitability",
        "terrain_source":None,
        "lower_slope_overlap_ha":None,
        "lower_slope_remaining_ha":None,
        "largest_contiguous_lower_patch_ha":None,
        "lower_patch_count":None,
        "quality_status":"geometry_only",
        "policy_checks":[],
        "warnings":[
            "Road centreline geometry is drawn, but width is a USER ENTERED assumption, not a surveyed or measured carriageway/reserve.",
            "The front-road buffer and perimeter offset are simulated exclusion envelopes, NOT verified lot-front/side/rear building setbacks.",
            "No road junctions, gradients, legal access, drains, streams, flood zones, utilities, boundary ownership or housing lot placement have been verified.",
            "No buildable hectares, allowed housing units, planning permission or development capacity certificate can be inferred from these area envelopes.",
        ],
        "layers":{
            "road_centerlines":{
                "type":"FeatureCollection",
                "features":[{"type":"Feature","properties":{"kind":"sketched_road_centreline"},
                    "geometry":entry} for entry in input.road_centerlines],
            },
            "road_corridor":_collection(corridor,world,"Assumed road corridor"),
            "road_front_margin":_collection(road_front_zone,world,"Assumed front-road band"),
            "perimeter_exclusion":_collection(outer_band,world,"Optional perimeter band"),
            "gross_remaining":_collection(remaining,world,"Area outside modeled exclusions"),
            "lower_slope_remaining":{"type":"FeatureCollection","features":[]},
        },
    }
    network_check=screen_road_network(site,lines,world)
    return_report["network"]=network_check["network"]
    return_report["layers"].update(network_check["layers"])
    return_report["warnings"].extend(network_check["warnings"])

    if not lines:
        return_report["warnings"].append("No road alignment has been drawn yet; road and front-road areas are zero, NOT proof that no roads are needed.")
    elif input.front_road_buffer_m==0:
        return_report["warnings"].append("No front-road margin has been assumed. Actual GPP building setbacks cannot be assessed without individual building and lot geometries.")

    if input.policy_profile=="perak_2023":
        if input.perak_market_segment is None:
            return_report["warnings"].append("Select the applicable Perak terrace cost band for the PR1 front setback reference.")
        road_min=50*.3048
        return_report["policy_checks"].append({
            "key":"perak_pr1_service_road_width",
            "label":"PR1 service road MINIMUM (reference)",
            "document":"Garis Panduan Piawaian Perumahan Negeri Perak 2023",
            "source_url":PERAK_SOURCE["url"],"source_page":"PR1, printed p.5",
            "minimum_m":road_min,"entered_m":input.assumed_road_width_m,
            "result":"not_drawn" if not lines else (
                "entered_value_meets_minimum" if input.assumed_road_width_m>=road_min-1e-8
                else "entered_value_below_minimum"
            ),
            "verified_geometry":False,"binding":False,
        })
        if input.perak_market_segment:
            front_min=(15 if input.perak_market_segment=="perak_low_cost" else 20)*.3048
            return_report["policy_checks"].append({
                "key":"perak_pr1_front_setback_reference",
                "label":"PR1 terrace front setback (reference)",
                "document":"Garis Panduan Piawaian Perumahan Negeri Perak 2023",
                "source_url":PERAK_SOURCE["url"],"source_page":"PR1, printed p.5",
                "minimum_m":front_min,"entered_m":input.front_road_buffer_m,
                "result":"not_drawn" if not lines else (
                    "entered_value_meets_reference" if input.front_road_buffer_m>=front_min-1e-8
                    else "entered_value_below_reference"
                ),
                "verified_geometry":False,"binding":False,
            })
        return_report["warnings"].append(
            "Perak PR1 comparison tests USER ENTERED dimensions only. It does NOT measure built road width, actual building frontage/setback or statutory PBT compliance."
        )

    if active_report is None:
        return_report["warnings"].append("No linked DEM suitability analysis. Gross remaining area must not be labelled slope-safe.")
        return return_report

    summary=active_report.get("suitability")
    overlay=active_report.get("suitability_geojson")
    if not isinstance(summary,dict) or not isinstance(overlay,dict):
        return_report["terrain_status"]="no_suitability_in_report"
        return_report["warnings"].append("Legacy DEM report has no suitability polygon. Re-run terrain analysis to compute slope overlap.")
        return return_report
    if not active_report.get("geometry") or not shape(active_report["geometry"]).equals(shape(validated)):
        return_report["terrain_status"]="report_site_mismatch"
        return_report["warnings"].append("The linked DEM report refers to a different site boundary; slope geometry is not reused.")
        return return_report
    return_report["terrain_source"]={
        "analysis_id":active_report.get("analysis_id"),
        "name":(active_report.get("source") or {}).get("name"),
        "resolution_m":summary.get("source_resolution_m"),
        "coverage_pct_est":summary.get("coverage_of_site_pct_est"),
    }
    if summary.get("class_overlay_truncated"):
        return_report["terrain_status"]="incomplete_vector_overlay"
        return_report["warnings"].append(
            "GIS suitability vector map was truncated at source; computing capacity from partial polygons would invent available land. Reanalyse with a more suitable resolution."
        )
        return return_report

    features=overlay.get("features")
    if not isinstance(features,list) or len(features)>MAX_SOURCE_FEATURES:
        return_report["terrain_status"]="large_or_invalid_overlay"
        return_report["warnings"].append("Suitability polygon count is missing or exceeds safe analysis limits; no spatial capacity is computed.")
        return return_report
    lower=[]
    try:
        for feature in features:
            if feature.get("properties",{}).get("class_id")!=1:
                continue
            piece=transform(local.transform,shape(feature["geometry"]))
            if piece.is_empty or not piece.is_valid or not isinstance(piece,(Polygon,MultiPolygon)):
                raise ValueError("Invalid raster-derived polygon")
            lower.append(piece)
    except (KeyError,TypeError,ValueError) as exc:
        return_report["terrain_status"]="invalid_suitability_overlay"
        return_report["warnings"].append("Invalid suitability overlay; slope patches were not used. Re-run GIS analysis.")
        return return_report
    lower_geom=(unary_union(lower).intersection(site) if lower else GeometryCollection())
    remaining_lower=lower_geom.intersection(remaining)
    patches=_polygons(remaining_lower)
    quality_limited=(
        float(summary.get("coverage_of_site_pct_est",0))<95
        or int(summary.get("assessed_pixels",0))<100
        or bool(summary.get("area_exceeds_site_due_to_pixelization"))
        or bool(summary.get("class_overlay_truncated"))
        or (summary.get("source_resolution_m") is not None
            and float(summary["source_resolution_m"])>=90)
    )
    return_report.update({
        "terrain_status":"low_slope_vector_approximation",
        "lower_slope_overlap_ha":_area(lower_geom),
        "lower_slope_remaining_ha":_area(remaining_lower),
        "largest_contiguous_lower_patch_ha":_area(max(patches,key=lambda x:x.area)) if patches else 0,
        "lower_patch_count":len(patches),
        "quality_status":"quality_limited" if quality_limited else "preliminary_raster",
    })
    return_report["layers"]["lower_slope_remaining"]=_collection(remaining_lower,world,"Remaining low-slope polygon (unverified for development)")
    if any(layer.get("map_truncated") for layer in return_report["layers"].values()):
        return_report["warnings"].append("Map rendering has been limited to 120 largest polygons for performance. Area results still derive from complete projected geometries.")
    return_report["warnings"].append(
        "Low-slope overlap is based on polygonized raster cells clipped to the project boundary. It is NOT a contiguous buildable footprint or a housing-unit yield."
    )
    if quality_limited:
        return_report["warnings"].append(
            "Low terrain confidence: under 95% slope coverage, fewer than 100 samples, coarse 90m raster or boundary pixel-area uncertainty. Do not interpret this overlap as an accurate layout envelope."
        )
    return return_report
