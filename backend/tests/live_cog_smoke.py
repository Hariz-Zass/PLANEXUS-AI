"""External AWS COG availability smoke test — real public DEM, not a simulated raster.

Run only in CI diagnostic job. A failure may reflect temporary S3/network coverage.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import rasterio
from app.sources import acquire_copernicus
from app.terrain import analyze_terrain

# Public, arbitrary WGS84 test square near Ipoh, not any user's stored site.
BOUNDS=(101.068,4.660,101.090,4.684)
SITE={"type":"Polygon","coordinates":[[
    [BOUNDS[0],BOUNDS[1]],[BOUNDS[2],BOUNDS[1]],
    [BOUNDS[2],BOUNDS[3]],[BOUNDS[0],BOUNDS[3]],[BOUNDS[0],BOUNDS[1]]
]]}


def run():
    with tempfile.TemporaryDirectory(prefix="planexus-live-dem-") as directory:
        path,source=acquire_copernicus(BOUNDS,Path(directory))
        with rasterio.open(path) as dataset:
            print("LIVE_COG SOURCE:",source["id"],"PIXELS:",dataset.width,"x",dataset.height)
            print("LIVE_COG RESOLUTION:",source["nominal_resolution_m"],"M; FALLBACK:",source["fallback_used"])
            print("LIVE_COG VALID NODATA:",dataset.nodata)
            assert dataset.width>5 and dataset.height>5
            assert dataset.crs.to_epsg()==4326
        report=analyze_terrain(SITE,path,source,"external-data-smoke")
        metrics=report["metrics"]
        assert metrics["valid_elevation_pixels"]>=9
        assert 0 <= metrics["slope_mean_deg"] <= 90
        assert metrics["elevation_min_m"]<=metrics["elevation_max_m"]
        print("LIVE_COG GIS OK:",{"coverage":metrics["coverage_percent_est"],
                "mean_slope":metrics["slope_mean_deg"],
                "source":source["name"]})
        print("WARNING: DEM is DSM, not surveyed ground truth.")


if __name__=="__main__":
    run()
