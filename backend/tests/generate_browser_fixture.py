"""Deterministic GIS browser-test data. NOT survey/DEM of any real site."""
from pathlib import Path
import json
import sys
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import Polygon, LineString, mapping
from shapely.ops import transform

def main(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    left, top, n, cell = 720000., 520000., 120, 10.
    row, col = np.indices((n, n))
    heights = (25. + col*.25 + row*.15).astype("float32")
    with rasterio.open(folder/"synthetic-elevation-ci.tif","w",driver="GTiff",
        width=n,height=n,count=1,dtype="float32",crs="EPSG:32647",
        nodata=-9999.,transform=from_origin(left,top,cell,cell)) as dst:
        dst.write(heights,1)
    crs=Transformer.from_crs("EPSG:32647","EPSG:4326",always_xy=True)
    polygons={"site":Polygon([(left+200,top-200),(left+1000,top-200),
                              (left+1000,top-1000),(left+200,top-1000)]),
              "road":LineString([(left+600,top-300),(left+600,top-900)])}
    for name, geom in polygons.items():
        feature={"type":"FeatureCollection","features":[{"type":"Feature",
          "properties":{"source":"SYNTHETIC CI TEST ONLY"},
          "geometry":mapping(transform(crs.transform,geom))}]}
        (folder/(name+".geojson")).write_text(json.dumps(feature),encoding="utf-8")
    print("Created real GeoTIFF bytes and synthetic test geometry:",folder)

if __name__=="__main__":
    main(Path(sys.argv[1]).resolve())
