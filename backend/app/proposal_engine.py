"""PLANEXUS development proposal land-budget calculator.

Transparent user-entered assumptions, not a zoning/density or layout approval.
All suggested allocations are input percentages of TOTAL gross land required.
A lower-slope cell is NOT established to be contiguous, accessible or buildable.
"""
from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .policy_registry import evaluate_policy


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=3, max_length=100)
    development_type: Literal["terrace_housing", "shoplots", "other_landed"] = "terrace_housing"
    units: int = Field(ge=1, le=100000)
    lot_width_m: float = Field(gt=0, le=150, allow_inf_nan=False)
    lot_depth_m: float = Field(gt=0, le=300, allow_inf_nan=False)
    roads_pct: float = Field(ge=0, le=70, allow_inf_nan=False)
    open_space_pct: float = Field(ge=0, le=70, allow_inf_nan=False)
    facilities_pct: float = Field(ge=0, le=70, allow_inf_nan=False)
    other_reserve_pct: float = Field(ge=0, le=70, allow_inf_nan=False)
    # Optional for legacy scenarios; never infer PBT scope from coordinates.
    policy_profile: Literal["none", "national_2016", "perak_2023"] = "none"
    housing_category: Literal[
        "terrace_low_cost", "terrace_lower_middle", "terrace_middle",
        "cluster", "semi_detached", "detached", "zero_lot", "townhouse"
    ] | None = None
    storeys: int | None = Field(default=None, ge=1, le=20)
    perak_market_segment: Literal[
        "perak_low_cost", "perak_middle", "perak_affordable", "perak_open"
    ] | None = None
    floor_area_m2: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    bedrooms: int | None = Field(default=None, ge=0, le=50)
    building_height_m: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_total(self) -> "ProposalInput":
        self.name = self.name.strip()
        if len(self.name) < 3:
            raise ValueError("Scenario name must be at least 3 characters.")
        total = self.roads_pct + self.open_space_pct + self.facilities_pct + self.other_reserve_pct
        if not math.isfinite(total) or total >= 85:
            raise ValueError("Combined road, open space, facilities and reserve allocations must be less than 85% of gross land.")
        if self.housing_category:
            is_terrace = self.housing_category.startswith("terrace_")
            if is_terrace and self.development_type != "terrace_housing":
                raise ValueError("Terrace GPP category can only be used with terrace_housing.")
            if not is_terrace and self.development_type != "other_landed":
                raise ValueError("Cluster/semi/detached categories require other_landed.")
        return self


def calculate_land_budget(
    proposal: ProposalInput,
    *,
    site_area_ha: float,
    analysis: dict[str, Any] | None = None,
    context_current: bool = True,
) -> dict[str, Any]:
    """Land budget in hectares. No inferred building permissions or statutory limits."""
    if not math.isfinite(site_area_ha) or site_area_ha <= 0:
        raise ValueError("A validated positive site area is required.")

    inputs=proposal.model_dump()
    policy_assessment=evaluate_policy(proposal)
    lot_m2 = proposal.lot_width_m * proposal.lot_depth_m
    plot_ha = proposal.units * lot_m2 / 10000
    allocations = {
        "roads_pct": proposal.roads_pct,
        "open_space_pct": proposal.open_space_pct,
        "facilities_pct": proposal.facilities_pct,
        "other_reserve_pct": proposal.other_reserve_pct,
    }
    reserved_pct=sum(allocations.values())
    net_share=(100-reserved_pct)/100
    required_gross_ha=plot_ha/net_share
    allocation_ha={key.replace("_pct","_ha"):required_gross_ha*percentage/100 for key,percentage in allocations.items()}
    allocation_ha["building_plots_ha"]=plot_ha

    gross_margin = site_area_ha - required_gross_ha
    site_density = proposal.units / site_area_ha  # explicitly units / GROSS site ha, not floor-area ratio
    notes = [
        "Only an arithmetic gross-land budget; not an approved layout, zoning, density or building permission.",
        "Road/open-space/facilities/other percentages are USER ASSUMPTIONS of total required gross land; they are not statutory minima.",
        "Gross housing/shoplot density is number of proposed lots/units divided by entire site hectares; not permitted density or floor-area ratio.",
        "Does not include setbacks, earthworks, irregular plots, road connectivity, topographic adjacency, drainage, flood limits or verified access.",
    ]
    result={
        "method": "PLANEXUS input-driven gross land area worksheet v1; required gross = units*width*depth/(10000*(1-total_reserves/100)).",
        "policy_assessment":policy_assessment,
        "inputs":inputs,
        "site_area_ha":round(site_area_ha,5),
        "lot_area_m2":round(lot_m2,5),
        "required_plot_area_ha":round(plot_ha,5),
        "reserve_total_pct":round(reserved_pct,4),
        "net_plots_share_pct":round(net_share*100,4),
        "required_gross_area_ha":round(required_gross_ha,5),
        "allocations_ha":{k:round(v,5) for k,v in allocation_ha.items()},
        "gross_site_density_units_per_ha":round(site_density,4),
        "gross_site_area_margin_ha":round(gross_margin,5),
        "gross_site_area_check": "arithmetic_area_envelope" if gross_margin >= -1e-8 else "gross_area_shortfall",
        "screening_status":"no_active_analysis",
        "analysis_id": None,
        "lower_constraint_cell_area_ha_est": None,
        "lower_constraint_area_margin_ha_est": None,
        "terrain_screening_cell_area_check": None,
        "quality_warnings": notes,
        "conclusion": "Arithmetic land requirement only. No verified slope assessment is linked to this scenario.",
        "not_approval": True,
    }

    if not context_current:
        result["screening_status"]="context_changed"
        result["conclusion"]="The site boundary or active GIS analysis has changed since this scenario was saved. Review and update this scenario before comparing it to terrain."
        return result
    if analysis is None:
        return result

    result["analysis_id"]=analysis.get("analysis_id")
    screening=analysis.get("suitability")
    if not isinstance(screening,dict) or not isinstance(screening.get("bands"),list):
        result["screening_status"]="no_suitability_layer"
        result["conclusion"]="The active GIS analysis has no verified suitability layer. Rerun DEM analysis; do not infer lower-constraint land."
        return result
    lower=next((band for band in screening["bands"] if band.get("id")==1),None)
    if not lower:
        result["screening_status"]="no_suitability_layer"
        return result
    low_area=float(lower.get("area_ha_est",0))
    if not math.isfinite(low_area) or low_area<0:
        result["screening_status"]="invalid_suitability"
        return result

    # This is a cell-area comparison, NOT a developable-land calculation.
    # A valid low-slope cell could be inaccessible, isolated or restricted.
    low_area_capped=min(site_area_ha,low_area)
    terrain_margin=low_area_capped-required_gross_ha
    result["lower_constraint_cell_area_ha_est"]=round(low_area_capped,5)
    result["lower_constraint_area_margin_ha_est"]=round(terrain_margin,5)
    result["terrain_screening_cell_area_check"]=(
        "cell_area_envelope_only" if terrain_margin>=-1e-8 else "cell_area_shortfall"
    )
    coverage=float(screening.get("coverage_of_site_pct_est",0))
    n=int(screening.get("assessed_pixels",0))
    coarse=screening.get("source_resolution_m")
    quality_limited=(
        coverage < 95 or n < 100 or bool(screening.get("area_exceeds_site_due_to_pixelization"))
        or (coarse is not None and float(coarse)>=90)
        or bool(screening.get("class_overlay_truncated"))
    )
    result["screening_status"]="quality_limited" if quality_limited else "indicative_cell_area_only"
    if coverage < 95:
        notes.append(f"Only {coverage:.2f}% approximate raster site coverage; unassessed land cannot be counted as available.")
    if n<100:
        notes.append("Fewer than 100 assessed slope cells; site-level area interpretation is highly uncertain.")
    if coarse is not None and float(coarse)>=90:
        notes.append("Coarse GLO-90 / approximately 90m surface data; local slopes may be missing.")
    if screening.get("area_exceeds_site_due_to_pixelization"):
        notes.append("Pixel area exceeds parcel area; cell count has been capped at gross site area for this rough comparison.")
    if screening.get("class_overlay_truncated"):
        notes.append("Map overlay simplified for performance; summary uses full measured pixel counts.")
    notes.append("Lower-constraint cells are not proven continuous, reachable, geotechnically stable, legally permitted or design-ready.")
    if terrain_margin < 0:
        result["conclusion"]="The entered gross land requirement exceeds even the capped lower-constraint raster-cell area. This is an indicative area warning, not a rejection under local planning policy."
    else:
        result["conclusion"]="The entered gross land requirement is no greater than the capped lower-constraint raster-cell area, but this DOES NOT prove feasibility; land may be fragmented or constrained and policy checks are missing."
    if quality_limited:
        result["conclusion"]="INSUFFICIENT TERRAIN CONFIDENCE: "+result["conclusion"]
    return result
