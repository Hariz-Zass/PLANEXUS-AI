"use client";

import { useEffect, useRef } from "react";
import maplibregl, { type Map as MapLibreMap, type GeoJSONSource } from "maplibre-gl";
import type { FeatureGeometry, LayoutLine, LayoutPreview } from "@/lib/api";

type Props={
  site:FeatureGeometry;
  inputRoads:LayoutLine[];
  preview:LayoutPreview|null;
  drawing:boolean;
  onRoadDrawn:(line:LayoutLine)=>void;
  onPointCount:(value:number)=>void;
  resetCounter:number;
};

const EMPTY:GeoJSON.FeatureCollection={type:"FeatureCollection",features:[]};

function polygonFeatures(geometry:FeatureGeometry):GeoJSON.FeatureCollection{
  return {type:"FeatureCollection",features:[{
    type:"Feature",properties:{kind:"project-site"},geometry:geometry as GeoJSON.Geometry,
  }]};
}

function lineFeatures(lines:LayoutLine[]):GeoJSON.FeatureCollection{
  return {type:"FeatureCollection",features:lines.map((line,index)=>({
    type:"Feature",properties:{number:index+1},geometry:line,
  }))};
}
function pointsFeature(points:[number,number][]):GeoJSON.FeatureCollection{
  return points.length<2?EMPTY:{type:"FeatureCollection",features:[
    {type:"Feature",properties:{draft:true},
      geometry:{type:"LineString",coordinates:points} as GeoJSON.Geometry},
  ]};
}

function extent(geometry:FeatureGeometry):[[number,number],[number,number]]{
  const points:number[][]=[];
  if(geometry.type==="Polygon"){
    for(const ring of geometry.coordinates as number[][][]) points.push(...ring);
  }else{
    for(const polygon of geometry.coordinates as number[][][][])
      for(const ring of polygon)points.push(...ring);
  }
  return [
    [Math.min(...points.map(point=>point[0])),Math.min(...points.map(point=>point[1]))],
    [Math.max(...points.map(point=>point[0])),Math.max(...points.map(point=>point[1]))],
  ];
}

export default function LayoutMap({
  site,inputRoads,preview,drawing,onRoadDrawn,onPointCount,resetCounter,
}:Props){
  const root=useRef<HTMLDivElement>(null);
  const instanceRef=useRef<MapLibreMap|null>(null);
  const drawingRef=useRef(drawing);
  const callbackRef=useRef(onRoadDrawn);
  const pointCallbackRef=useRef(onPointCount);
  const pointsRef=useRef<[number,number][]>([]);
  const latest=useRef({site,inputRoads,preview});
  latest.current={site,inputRoads,preview};
  drawingRef.current=drawing;
  callbackRef.current=onRoadDrawn;
  pointCallbackRef.current=onPointCount;
  const applyRef=useRef<(()=>void)|null>(null);
  const fitted=useRef("");

  useEffect(()=>{
    const map=instanceRef.current;
    if(!map)return;
    if(drawing)map.doubleClickZoom.disable();
    else map.doubleClickZoom.enable();
    map.getCanvas().style.cursor=drawing?"crosshair":"";
  },[drawing]);

  useEffect(()=>{
    pointsRef.current=[];
    pointCallbackRef.current(0);
    (instanceRef.current?.getSource("layout-sketch") as GeoJSONSource|undefined)?.setData(EMPTY);
  },[resetCounter]);

  useEffect(()=>{
    if(!root.current||instanceRef.current)return;
    const map=new maplibregl.Map({
      container:root.current,
      style:"https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center:[101.5,4.5],zoom:6.7,attributionControl:false,
    });
    instanceRef.current=map;
    map.addControl(new maplibregl.NavigationControl({showCompass:true}),"top-right");
    map.addControl(new maplibregl.AttributionControl({compact:true}),"bottom-right");
    map.on("load",()=>{
      function polygon(id:string,color:string,opacity:number,outlineColor:string){
        map.addSource(id,{type:"geojson",data:EMPTY});
        map.addLayer({id:id+"-fill",type:"fill",source:id,paint:{
          "fill-color":color,"fill-opacity":opacity,
          "fill-outline-color":outlineColor,
        }});
      }
      polygon("layout-site","#acd981",.07,"#b4f77d");
      polygon("layout-remaining","#5bb4ce",.14,"#84d8e2");
      polygon("layout-low","#8fea94",.51,"#b2f9ad");
      polygon("layout-perimeter","#8c97af",.34,"#8c97af");
      polygon("layout-front","#edba77",.41,"#ffcf89");
      polygon("layout-corridor","#38d2c9",.56,"#75fbf4");
      map.addSource("layout-roads",{type:"geojson",data:EMPTY});
      map.addLayer({id:"layout-roads-line",type:"line",source:"layout-roads",
        paint:{"line-color":"#f7f4b3","line-width":3,"line-dasharray":[2.5,1.5]}});
      map.addSource("layout-boundary",{type:"geojson",data:EMPTY});
      map.addLayer({id:"layout-boundary-line",type:"line",source:"layout-boundary",
        paint:{"line-color":"#c5f58a","line-width":3,"line-dasharray":[3,1.2]}});
      map.addSource("layout-sketch",{type:"geojson",data:EMPTY});
      map.addLayer({id:"layout-sketch-line",type:"line",source:"layout-sketch",
        paint:{"line-color":"#ffffff","line-width":3,"line-dasharray":[2,1]}});
      applyRef.current?.();
    });
    map.on("click",event=>{
      if(!drawingRef.current)return;
      const point:[number,number]=[event.lngLat.lng,event.lngLat.lat];
      const old=pointsRef.current.at(-1);
      if(old&&Math.abs(old[0]-point[0])<.00001&&Math.abs(old[1]-point[1])<.00001)return;
      if(pointsRef.current.length>=200)return;
      pointsRef.current=[...pointsRef.current,point];
      pointCallbackRef.current(pointsRef.current.length);
      (map.getSource("layout-sketch") as GeoJSONSource|undefined)?.setData(pointsFeature(pointsRef.current));
    });
    map.on("dblclick",event=>{
      if(!drawingRef.current)return;
      event.preventDefault();
      const points:[number,number][]=[];
      for(const point of pointsRef.current){
        if(!points.some(p=>Math.abs(p[0]-point[0])<.00001&&Math.abs(p[1]-point[1])<.00001))
          points.push(point);
      }
      if(points.length<2)return;
      drawingRef.current=false;
      map.doubleClickZoom.enable();
      pointsRef.current=[];
      pointCallbackRef.current(0);
      (map.getSource("layout-sketch") as GeoJSONSource|undefined)?.setData(EMPTY);
      callbackRef.current({type:"LineString",coordinates:points});
    });
    const resize=typeof ResizeObserver!=="undefined"&&root.current?
      new ResizeObserver(()=>{if(instanceRef.current===map)map.resize();}):null;
    if(root.current)resize?.observe(root.current);
    return()=>{
      resize?.disconnect();
      applyRef.current=null;
      instanceRef.current=null;
      map.remove();
    };
  },[]);

  useEffect(()=>{
    const sync=()=>{
      const map=instanceRef.current;
      if(!map||!map.getSource("layout-site"))return;
      const input=latest.current;
      const set=(key:string,geojson:GeoJSON.FeatureCollection|undefined)=>{
        (map.getSource(key) as GeoJSONSource|undefined)?.setData(geojson??EMPTY);
      };
      set("layout-site",polygonFeatures(input.site));
      set("layout-boundary",polygonFeatures(input.site));
      set("layout-roads",lineFeatures(input.inputRoads));
      const layers=input.preview?.layers;
      set("layout-corridor",layers?.road_corridor);
      set("layout-front",layers?.road_front_margin);
      set("layout-perimeter",layers?.perimeter_exclusion);
      set("layout-remaining",layers?.gross_remaining);
      set("layout-low",layers?.lower_slope_remaining);
      if(root.current){
        root.current.dataset.layoutRendered="true";
        root.current.dataset.roadCount=String(input.inputRoads.length);
        root.current.dataset.lowSlopeVisible=
          layers?.lower_slope_remaining.features.length?"true":"false";
      }
      const key=JSON.stringify(input.site);
      if(fitted.current!==key){
        fitted.current=key;
        map.fitBounds(extent(input.site),{
          padding:55,maxZoom:16,
          duration:window.matchMedia("(prefers-reduced-motion: reduce)").matches?0:600,
        });
      }
    };
    applyRef.current=sync;
    sync();
  },[site,inputRoads,preview]);

  return <div ref={root} className={"terrain-map layout-map"+(drawing?" terrain-map-drawing":"")}
    role="application"
    aria-label="PLANEXUS concept layout map: click road centreline vertices and double click to finish"
    data-layout-rendered="false"/>;
}
