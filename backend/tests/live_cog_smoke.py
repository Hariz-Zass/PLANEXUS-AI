"""External AWS COG availability smoke test — real public DEM, not a simulated raster.

Run only in CI diagnostic job. A failure may reflect temporary S3/network coverage.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import rasterio
from fastapi.testclient import TestClient
from app.sources import acquire_copernicus
from app.terrain import analyze_terrain
import app.main as gis_api

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

        # Exercise REAL public COG evidence through the SAME HTTP entry point
        # used by the Next.js frontend, and verify persisted report + project.
        # Reuse acquired raster rather than making two external S3 downloads.
        gis_api.DATA_DIR=Path(directory)/"api-storage"
        original=gis_api.acquire_copernicus
        try:
            gis_api.acquire_copernicus=lambda bounds, target: (path,source)
            with TestClient(gis_api.app) as api:
                created=api.post("/api/projects",json={"name":"REAL COG CI SMOKE - not a survey"})
                assert created.status_code==201,created.text
                pid=created.json()["id"]
                response=api.post("/api/terrain/auto",json={
                    "geometry":SITE,"project_id":pid
                })
                assert response.status_code==200,response.text
                result=response.json()
                assert result["source"]["id"]==source["id"]
                assert result["slope_geojson"]["features"]
                assert result["elevation_geojson"]["features"]
                analysis_id=result["analysis_id"]
                project=api.get("/api/projects/"+pid).json()
                assert project["active_analysis_id"]==analysis_id
                saved=api.get("/api/analyses/"+analysis_id)
                assert saved.status_code==200
                assert saved.json()["slope_geojson"]["features"]
                assert saved.json()["elevation_geojson"]["features"]
                assert saved.json()["source"]["id"]==source["id"]
                print("REAL COG API/PERSISTENCE OK:",{
                    "project_id":pid,"analysis_id":analysis_id,
                    "slope_shapes":len(result["slope_geojson"]["features"]),
                    "elevation_shapes":len(result["elevation_geojson"]["features"]),
                    "source_id":source["id"],
                })
        finally:
            gis_api.acquire_copernicus=original


if __name__=="__main__":
    run()
