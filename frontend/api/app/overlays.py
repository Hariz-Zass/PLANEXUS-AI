"""Bounded contour and elevation overlays from real elevation raster pixels."""
from __future__ import annotations
import math
from typing import Any
import contourpy
import numpy as np
from rasterio.features import shapes
from rasterio.warp import transform_geom

COLORS = ["#38679B","#398EAA","#43B3B0","#84C8A3","#BCDB84","#E5D67B"]

def _step(minimum:float)->float:
    magnitude=10**math.floor(math.log10(max(minimum,0.001)))
    return next((factor*magnitude for factor in (1,2,5,10) if factor*magnitude>=minimum-1e-9),10*magnitude)

def build_terrain_overlays(elevation:np.ndarray, valid_inside:np.ndarray, transform:Any, crs:Any, source:dict[str,Any])->dict[str,Any]:
    valid=valid_inside & np.isfinite(elevation)
    minimum=float(elevation[valid].min())
    maximum=float(elevation[valid].max())
    spread=maximum-minimum
    bins=np.linspace(minimum,maximum,len(COLORS)+1)
    indexes=np.zeros(elevation.shape,dtype="uint8")
    if spread<1e-7:
        indexes[valid]=1
    else:
        indexes[valid]=np.clip(np.searchsorted(bins[1:],elevation[valid],side="right")+1,1,len(COLORS))
    polygons=[]
    polygon_truncated=False
    for geom,cls in shapes(indexes,mask=indexes>0,transform=transform):
        if len(polygons)>=700:
            polygon_truncated=True
            break
        polygons.append({"type":"Feature","properties":{"class_id":int(cls)},"geometry":transform_geom(crs,"EPSG:4326",geom,precision=6)})
    source_resolution=source.get("nominal_resolution_m")
    lowest=10.0 if source_resolution==90 else 5.0 if source_resolution==30 else 1.0
    interval=_step(max(spread/8,lowest))
    lines=[]
    truncated=False
    if spread>=interval and min(elevation.shape)>=3:
        xs=transform.c+(np.arange(elevation.shape[1])+.5)*transform.a
        ys=transform.f+(np.arange(elevation.shape[0])+.5)*transform.e
        grid=np.ma.array(elevation.astype("float64"),mask=~valid)
        generator=contourpy.contour_generator(x=xs,y=ys,z=grid,name="serial",line_type="Separate",corner_mask=False)
        start=math.floor(minimum/interval)+1
        stop=min(math.ceil(maximum/interval),start+40)
        for level_index in range(start,stop):
            level=float(level_index*interval)
            for line in generator.lines(level):
                if len(line)<2:continue
                if len(lines)>=350:
                    truncated=True
                    break
                stride=max(1,math.ceil((len(line)-1)/300))
                coords=line[::stride]
                if not np.array_equal(coords[-1],line[-1]):
                    coords=np.vstack([coords,line[-1]])
                geom={"type":"LineString","coordinates":coords.tolist()}
                lines.append({"type":"Feature","properties":{"elevation_m":round(level,2)},"geometry":transform_geom(crs,"EPSG:4326",geom,precision=6)})
            if truncated:break
    return {
        "elevation_geojson":{"type":"FeatureCollection","features":polygons},
        "contours_geojson":{"type":"FeatureCollection","features":lines},
        "elevation_legend":[{"class_id":i+1,"color":color,"min_m":round(float(bins[i]),2),"max_m":round(float(bins[i+1]),2)} for i,color in enumerate(COLORS)],
        "contour_interval_m":float(interval) if lines else None,
        "elevation_overlay_truncated":polygon_truncated,
        "contours_truncated":truncated,
    }
