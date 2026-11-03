"""Independent GDAL Horn slope comparison for PLANEXUS B3.3.

QGIS Processing gdal:slope delegates to GDAL DEM slope (Horn by default).
This executes the GDAL binary on the EXACT exported UTM height grid, not on
the original angular-degree input. It does not run the QGIS desktop GUI and
does not establish site vertical accuracy. All three profiles are synthetic.
"""
from __future__ import annotations

import json
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import Polygon, mapping
from shapely.ops import transform as shapely_transform

from app.terrain import analyze_terrain


def scenario_raster(directory: Path, profile: str) -> tuple[Path, dict]:
    rows, columns = np.indices((120, 120))
    if profile == "flat":
        heights = 38. + 0. * rows
    elif profile == "gentle":
        heights = 20. + .23 * columns + .17 * rows
    elif profile == "mixed":
        heights = (60. + 13 * np.sin(columns / 8) +
                   18 * np.cos(rows / 9) + .23 * columns)
    else:
        raise ValueError(profile)
    heights=heights.astype("float32")
    if profile=="mixed":
        heights[41:48,56:63]=-9999.
    site=Polygon([
        (720180,519820),(721020,519820),(721020,518980),(720180,518980)
    ])
    to_wgs=Transformer.from_crs("EPSG:32647","EPSG:4326",always_xy=True)
    geom=mapping(shapely_transform(to_wgs.transform,site))
    path=directory/(profile+"-input.tif")
    with rasterio.open(path,"w",driver="GTiff",height=120,width=120,
                       count=1,dtype="float32",crs="EPSG:32647",
                       nodata=-9999.,transform=from_origin(720000,520000,10,10)) as ds:
        ds.write(heights,1)
    return path,geom


def compare(profile: str, directory: Path) -> dict:
    file,site=scenario_raster(directory,profile)
    folder=directory/("analysis-"+profile)
    report=analyze_terrain(site,file,{
        "id":"synthetic-gdal-reference", "name":"Synthetic "+profile,
        "data_type":"DTM","nominal_resolution_m":10,
        "vertical_unit":"metres","verified":"test-only synthetic surface"
    },profile,artifacts_dir=folder)
    projected=folder/"elevation_utm.tif"
    planexus=folder/"slope_degrees_utm.tif"
    gdaldem=folder/"gdal_horn.tif"
    command=["gdaldem","slope",str(projected),str(gdaldem),
             "-alg","Horn","-s","1","-of","GTiff"]
    process=subprocess.run(command,check=False,text=True,capture_output=True,
                           timeout=60)
    if process.returncode:
        raise AssertionError("Independent GDAL comparison FAILED: "+
                             process.stderr[-1500:])
    with rasterio.open(planexus) as ours, rasterio.open(gdaldem) as gdal:
        assert ours.crs==gdal.crs and ours.transform==gdal.transform
        assert (ours.width,ours.height)==(gdal.width,gdal.height)
        ours_z=ours.read(1,masked=True).filled(np.nan).astype("float64")
        gdal_z=gdal.read(1,masked=True).filled(np.nan).astype("float64")
        ours_valid=np.isfinite(ours_z)
        gd_valid=np.isfinite(gdal_z)
        compared=ours_valid & gd_valid
        assert compared.sum()>1000
        mismatch=int(np.count_nonzero(ours_valid ^ gd_valid))
        # NoData mask must agree in essentially every cell: GDAL's default
        # no-edge and 3x3 support are matched exactly.
        assert mismatch==0, ("GDAL NoData mask differs",mismatch)
        error=np.abs(ours_z[compared]-gdal_z[compared])
        rmse=float(np.sqrt(np.mean(error**2)))
        maximum=float(error.max())
        assert rmse<=0.02, (profile,"GDAL Horn RMSE",rmse)
        assert maximum<=0.12, (profile,"GDAL Horn max difference",maximum)
        return {
            "profile":profile,"reference_tool":"gdaldem slope -alg Horn -s 1",
            "qgis_processing_equivalent":"gdal:slope ZEVENBERGEN=False SCALE=1 COMPUTE_EDGES=False",
            "comparison_is_synthetic":True,"real_field_accuracy_verified":False,
            "input_raster_sha256":report["source_file"]["sha256"],
            "projected_crs":report["metrics"]["horizontal_crs"],
            "slope_pixels_compared":int(compared.sum()),
            "nodata_mask_disagreements":mismatch,
            "slope_rmse_degrees":round(rmse,6),
            "slope_max_abs_error_degrees":round(maximum,6),
            "result":"pass"
        }


def main():
    with tempfile.TemporaryDirectory(prefix="planexus-gdal-horn-") as directory:
        folder=Path(directory)
        results=[compare(profile,folder) for profile in ("flat","gentle","mixed")]
    report={
        "report_type":"B3.3 independent GDAL/QGIS-equivalent slope parity",
        "scope":"synthetic only; QGIS desktop and actual site survey not verified",
        "results":results,
        "result":"pass" if all(x["result"]=="pass" for x in results) else "fail",
    }
    print(json.dumps(report,indent=2))
    out=Path("b3.3_gdal_reference_report.json")
    out.write_text(json.dumps(report,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
