"use client";

import { useEffect, useRef } from "react";
import maplibregl, { type GeoJSONSource, type Map as MapLibreMap } from "maplibre-gl";
import type { FeatureGeometry, TerrainReport } from "@/lib/api";

type Props = {
  geometry: FeatureGeometry | null;
  report: TerrainReport | null;
  drawing: boolean;
  onSiteDrawn: (geometry: FeatureGeometry) => void;
  onPointCount: (count: number) => void;
  resetCounter: number;
};

const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

function toFeatureCollection(geometry: FeatureGeometry | null): GeoJSON.FeatureCollection {
  if (!geometry) return EMPTY;
  return { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: geometry as GeoJSON.Geometry }] };
}

function drawFeature(coords: [number, number][]): GeoJSON.FeatureCollection {
  if (coords.length < 2) return EMPTY;
  const geometry: GeoJSON.Geometry = coords.length >= 3
    ? { type: "Polygon", coordinates: [[...coords, coords[0]]] }
    : { type: "LineString", coordinates: coords };
  return { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry }] };
}

function limits(geometry: FeatureGeometry): [[number, number], [number, number]] {
  const points: number[][] = [];
  if (geometry.type === "Polygon") {
    for (const ring of geometry.coordinates as number[][][]) points.push(...ring);
  } else {
    for (const polygon of geometry.coordinates as number[][][][]) for (const ring of polygon) points.push(...ring);
  }
  return [
    [Math.min(...points.map(p => p[0])), Math.min(...points.map(p => p[1]))],
    [Math.max(...points.map(p => p[0])), Math.max(...points.map(p => p[1]))],
  ];
}

export default function TerrainMap({ geometry, report, drawing, onSiteDrawn, onPointCount, resetCounter }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const drawingRef = useRef(drawing);
  const onSiteDrawnRef = useRef(onSiteDrawn);
  const onPointCountRef = useRef(onPointCount);
  const pointsRef = useRef<[number, number][]>([]);
  const previousFit = useRef("");

  useEffect(() => { drawingRef.current = drawing; if (map.current) { if (drawing) map.current.doubleClickZoom.disable(); else map.current.doubleClickZoom.enable(); } }, [drawing]);
  useEffect(() => { onSiteDrawnRef.current = onSiteDrawn; }, [onSiteDrawn]);
  useEffect(() => { onPointCountRef.current = onPointCount; }, [onPointCount]);

  useEffect(() => {
    pointsRef.current = [];
    onPointCountRef.current(0);
    const source = map.current?.getSource("sketch") as GeoJSONSource | undefined;
    source?.setData(EMPTY);
  }, [resetCounter]);

  useEffect(() => {
    if (!root.current || map.current) return;
    const instance = new maplibregl.Map({
      container: root.current,
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center: [101.5, 4.5], zoom: 6.7, attributionControl: false,
    });
    map.current = instance;
    instance.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    instance.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    instance.on("load", () => {
      instance.addSource("slope", { type: "geojson", data: EMPTY });
      instance.addLayer({ id: "slope-fill", type: "fill", source: "slope", paint: { "fill-color": ["match", ["get", "class_id"], 1, "#4cc9a3", 2, "#e5c46d", 3, "#eb8c64", 4, "#cb626f", "#9ca3af"], "fill-opacity": 0.74 } });
      instance.addSource("site", { type: "geojson", data: EMPTY });
      instance.addLayer({ id: "site-fill", type: "fill", source: "site", paint: { "fill-color": "#a1f3bf", "fill-opacity": 0.16 } });
      instance.addLayer({ id: "site-halo", type: "line", source: "site", paint: { "line-color": "#b4f77d", "line-width": 10, "line-opacity": 0.12 } });
      instance.addLayer({ id: "site-line", type: "line", source: "site", paint: { "line-color": "#b4f77d", "line-width": 2.8, "line-dasharray": [3, 1.3] } });
      instance.addSource("sketch", { type: "geojson", data: EMPTY });
      instance.addLayer({ id: "sketch-fill", type: "fill", source: "sketch", paint: { "fill-color": "#18d9ba", "fill-opacity": 0.25 } });
      instance.addLayer({ id: "sketch-line", type: "line", source: "sketch", paint: { "line-color": "#b4f77d", "line-width": 2.6 } });
    });
    instance.on("click", event => {
      if (!drawingRef.current) return;
      const point: [number, number] = [event.lngLat.lng, event.lngLat.lat];
      const last = pointsRef.current.at(-1);
      if (last && Math.abs(last[0] - point[0]) < 0.00001 && Math.abs(last[1] - point[1]) < 0.00001) return;
      pointsRef.current = [...pointsRef.current, point];
      onPointCountRef.current(pointsRef.current.length);
      (instance.getSource("sketch") as GeoJSONSource | undefined)?.setData(drawFeature(pointsRef.current));
    });
    instance.on("dblclick", event => {
      if (!drawingRef.current) return;
      event.preventDefault();
      const all = pointsRef.current;
      const unique: [number, number][] = [];
      for (const point of all) {
        if (!unique.some(v => Math.abs(v[0] - point[0]) < 0.00001 && Math.abs(v[1] - point[1]) < 0.00001)) unique.push(point);
      }
      if (unique.length < 3) return;
      drawingRef.current = false;
      instance.doubleClickZoom.enable();
      pointsRef.current = [];
      onPointCountRef.current(0);
      (instance.getSource("sketch") as GeoJSONSource | undefined)?.setData(EMPTY);
      onSiteDrawnRef.current({ type: "Polygon", coordinates: [[...unique, unique[0]]] });
    });
    return () => { instance.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const update = () => {
      (instance.getSource("site") as GeoJSONSource | undefined)?.setData(toFeatureCollection(geometry));
      if (geometry) {
        const serialized = JSON.stringify(geometry);
        if (previousFit.current !== serialized) {
          previousFit.current = serialized;
          instance.fitBounds(limits(geometry), { padding: 70, maxZoom: 15, duration: 900 });
        }
      } else previousFit.current = "";
    };
    if (instance.isStyleLoaded()) update(); else instance.once("load", update);
  }, [geometry]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const update = () => (instance.getSource("slope") as GeoJSONSource | undefined)?.setData(report?.slope_geojson || EMPTY);
    if (instance.isStyleLoaded()) update(); else instance.once("load", update);
  }, [report]);

  return <div ref={root} className={`terrain-map ${drawing ? "terrain-map-drawing" : ""}`} aria-label="Peta interaktif PLANEXUS untuk lukis tapak dan melihat kelas kecerunan" />;
}
