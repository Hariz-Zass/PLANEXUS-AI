"""Three actual Malaysian PUBLIC Copernicus COG sample locations, GDAL parity.

Samples are public reference squares, NOT the user's planning projects.
No field truth/QGIS GUI is claimed. A missing tile or HTTP outage is recorded,
never replaced by a synthetic DEM. This is a NON-BLOCKING external CI smoke.
"""
from __future__ import annotations

import json
import math
import subprocess
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

from app.sources import acquire_copernicus
from app.terrain import analyze_terrain

# Three sites selected BEFORE measurement; relief categories are not assumed.
# BBOX = west,south,east,north in WGS84.
SITES = [
    ("perak_meru_raya", (101.066,4.664,101.083,4.679)),
    ("selangor_klang", (101.435,3.040,101.451,3.055)),
    ("pahang_cameron_highlands", (101.375,4.470,101.390,4.485)),
]
OUTPUT = Path("b3.3_malaysia_live_report.json")


def polygon(bounds: tuple[float,float,float,float]) -> dict:
    west,south,east,north=bounds
    return {"type":"Polygon","coordinates":[[
        [west,south],[east,south],[east,north],[west,north],[west,south]
    ]]}


def gdal_compare(folder: Path) -> dict:
    projected=folder/"elevation_utm.tif"
    planexus=folder/"slope_degrees_utm.tif"
    reference=folder/"gdal_reference_slope.tif"
    command=["gdaldem","slope",str(projected),str(reference),
             "-alg","Horn","-s","1","-of","GTiff"]
    process=subprocess.run(command,capture_output=True,text=True,timeout=80)
    if process.returncode:
        raise RuntimeError("GDAL reference command failed: "+process.stderr[-300:])
    with rasterio.open(planexus) as a, rasterio.open(reference) as b:
        if a.crs != b.crs or a.transform != b.transform or a.shape != b.shape:
            raise AssertionError("Reference grids have incompatible extent/CRS.")
        a_z=a.read(1,masked=True).filled(np.nan).astype("float64")
        b_z=b.read(1,masked=True).filled(np.nan).astype("float64")
        a_valid=np.isfinite(a_z)
        b_valid=np.isfinite(b_z)
        matched=a_valid & b_valid
        if int(matched.sum())<9:
            raise AssertionError("Insufficient common valid Horn slopes.")
        diff=np.abs(a_z[matched]-b_z[matched])
        rmse=float(np.sqrt(np.mean(diff**2)))
        largest=float(diff.max())
        mismatched=int(np.count_nonzero(a_valid^b_valid))
        return {
            "reference":"GDAL gdaldem slope -alg Horn -s 1 (QGIS gdal:slope equivalent)",
            "matched_pixel_count":int(matched.sum()),
            "nodata_mask_mismatch_count":mismatched,
            "slope_rmse_degrees":round(rmse,6),
            "slope_max_abs_difference_degrees":round(largest,6),
            "threshold":"RMSE <= 0.02 degrees, max <= 0.12 degrees; exact NoData mask",
            "parity_pass":rmse<=.02 and largest<=.12 and mismatched==0,
        }


def run() -> None:
    output={
        "program":"PLANEXUS B3.3 — Three Malaysian public DSM sites",
        "date_utc":datetime.now(timezone.utc).isoformat(),
        "scope":"Copernicus DSM screening only; not ground-truthed. QGIS desktop GUI not run.",
        "method":"Actual COG downloads -> Rasterio UTM -> Horn slope -> GDAL slope on IDENTICAL UTM grid",
        "sites":[],
    }
    with tempfile.TemporaryDirectory(prefix="planexus-malaysia-cog-") as tmp:
        for identifier,bounds in SITES:
            site={"site":identifier,"bounds_wgs84":bounds,"source_type":"public Copernicus DSM",
                  "field_accuracy_verified":False,"qgis_desktop_verified":False}
            try:
                folder=Path(tmp)/identifier
                raster,source=acquire_copernicus(bounds,folder)
                report=analyze_terrain(polygon(bounds),raster,source,identifier,artifacts_dir=folder)
                parity=gdal_compare(folder)
                status="pass" if parity["parity_pass"] else "fail"
                site.update({
                    "status":status,"source_id":source["id"],
                    "used_fallback_glo90":source.get("fallback_used",False),
                    "source_tile_urls":source.get("source_tile_urls",[]),
                    "raster_sha256":report["source_file"]["sha256"],
                    "input_crs":report["source_file"]["input_crs"],
                    "projected_crs":report["metrics"]["horizontal_crs"],
                    "elevation_min_m":report["metrics"]["elevation_min_m"],
                    "elevation_mean_m":report["metrics"]["elevation_mean_m"],
                    "elevation_max_m":report["metrics"]["elevation_max_m"],
                    "slope_mean_deg":report["metrics"]["slope_mean_deg"],
                    "slope_max_deg":report["metrics"]["slope_max_deg"],
                    "contour_features":report["metrics"]["contour_features"],
                    "slope_class_area_ha_est":[c["area_ha_est"] for c in report["metrics"]["slope_classes"]],
                    "quality":report["quality"],
                    "gdal_slope_parity":parity,
                })
            except Exception as exc:
                # No invented replacement. Preserve partial results as audit evidence.
                site.update({"status":"unavailable_or_failed",
                             "error_type":type(exc).__name__,
                             "error":str(exc)[:350]})
            output["sites"].append(site)
            OUTPUT.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
            print(identifier,site["status"],site.get("gdal_slope_parity",{}).get("slope_rmse_degrees"))
    counts={status:sum(s["status"]==status for s in output["sites"])
            for status in ("pass","fail","unavailable_or_failed")}
    output["summary"]=counts
    OUTPUT.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"summary":counts,"out":str(OUTPUT)},indent=2))
    if counts["pass"] != len(SITES):
        raise SystemExit("At least one real public DSM site did not pass; inspect the artifact. No fallback to simulated observations.")


if __name__=="__main__":
    run()
