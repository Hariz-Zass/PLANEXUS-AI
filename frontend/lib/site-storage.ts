import type { FeatureGeometry } from "./api";

/** Versioned, device-local boundary storage. Not cloud storage or survey validation. */
export const SITE_STORAGE_KEY = "planexus:site-boundary:v1";
export type SiteOrigin = "map-drawing" | "geojson-import" | "analysis-reopened";
export type SiteRecord = { version: 1; geometry: FeatureGeometry; savedAt: string; origin: SiteOrigin };
export type ReadSiteResult = { state: "found"; site: SiteRecord } | { state: "empty" } | { state: "error"; message: string };
export type SaveSiteResult = { saved: true; site: SiteRecord } | { saved: false; message: string };
const MAX_VERTICES = 12000;
const MAX_RECORD_CHARS = 750000;

function normalizeRing(input: unknown, counter: { count: number }): number[][] {
  if (!Array.isArray(input) || input.length < 3) throw new Error("Polygon memerlukan sekurang-kurangnya tiga titik.");
  const vertices = input.map(pos => {
    counter.count += 1;
    if (counter.count > MAX_VERTICES) throw new Error("Terlalu banyak vertices untuk simpanan browser. Ringkaskan sempadan.");
    if (!Array.isArray(pos) || pos.length < 2 || pos.length > 3) throw new Error("GeoJSON memerlukan koordinat [longitude, latitude].");
    const lon = pos[0], lat = pos[1];
    if (typeof lon !== "number" || typeof lat !== "number" ||
        !Number.isFinite(lon) || !Number.isFinite(lat) ||
        lon < -180 || lon > 180 || lat < -90 || lat > 90) {
      throw new Error("Koordinat WGS84 tidak sah. Semak susunan [longitude, latitude].");
    }
    return [lon, lat];
  });
  if (vertices.length > 1 && vertices[0][0] === vertices[vertices.length-1][0] &&
      vertices[0][1] === vertices[vertices.length-1][1]) vertices.pop();
  if (vertices.length < 3 || new Set(vertices.map(p => p.join(","))).size < 3) {
    throw new Error("Polygon mesti mempunyai tiga titik berbeza.");
  }
  let area = 0;
  for (let i=0;i<vertices.length;i++) {
    const a=vertices[i], b=vertices[(i+1)%vertices.length];
    area += a[0]*b[1]-a[1]*b[0];
  }
  if (Math.abs(area) < 1e-12) throw new Error("Polygon tidak mempunyai keluasan yang jelas.");
  return [...vertices, [...vertices[0]]];
}

/** Basic numeric/WGS84 checks only: this does not certify topology, cadastral accuracy, or zoning. */
export function validateSiteBoundary(input: unknown): FeatureGeometry {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new Error("Geometri tidak sah.");
  const raw = input as Record<string, unknown>;
  if (raw.type !== "Polygon" && raw.type !== "MultiPolygon") throw new Error("Hanya Polygon/MultiPolygon WGS84 dibenarkan.");
  if (!Array.isArray(raw.coordinates)) throw new Error("Koordinat tiada.");
  const counter={count:0};
  const polygon = (rings: unknown): number[][][] => {
    if (!Array.isArray(rings) || rings.length < 1 || rings.length > 32) throw new Error("Ring polygon tidak sah.");
    return rings.map(ring=>normalizeRing(ring,counter));
  };
  if(raw.type==="Polygon") return {type:"Polygon",coordinates:polygon(raw.coordinates)};
  if (raw.coordinates.length < 1 || raw.coordinates.length > 32) throw new Error("Bilangan polygon tidak sah.");
  return {type:"MultiPolygon",coordinates:raw.coordinates.map(polygon)};
}

export function readSavedSite(): ReadSiteResult {
  if (typeof window === "undefined") return {state:"empty"};
  try {
    const saved=window.localStorage.getItem(SITE_STORAGE_KEY);
    if(!saved) return {state:"empty"};
    if(saved.length > MAX_RECORD_CHARS) throw new Error("Rekod tersimpan melebihi had saiz.");
    const value:unknown=JSON.parse(saved);
    if(!value || typeof value!=="object" || Array.isArray(value)) throw new Error("Rekod tersimpan rosak.");
    const record=value as Record<string,unknown>;
    if(record.version!==1 || typeof record.savedAt!=="string" || !Number.isFinite(Date.parse(record.savedAt))) {
      throw new Error("Versi atau tarikh rekod tapak tidak sah.");
    }
    if(record.origin!=="map-drawing" && record.origin!=="geojson-import" && record.origin!=="analysis-reopened") {
      throw new Error("Jenis rekod tapak tidak sah.");
    }
    return {state:"found",site:{version:1,geometry:validateSiteBoundary(record.geometry),savedAt:record.savedAt,origin:record.origin}};
  } catch(err) {
    return {state:"error",message:err instanceof Error ? err.message : "Gagal membaca simpanan browser."};
  }
}

export function saveSiteBoundary(geometry:FeatureGeometry,origin:SiteOrigin):SaveSiteResult {
  if (typeof window==="undefined") return {saved:false,message:"Simpanan hanya tersedia dalam browser."};
  const site:SiteRecord={version:1,geometry:validateSiteBoundary(geometry),savedAt:new Date().toISOString(),origin};
  try {
    const value=JSON.stringify(site);
    if(value.length>MAX_RECORD_CHARS) throw new Error("Polygon melebihi had simpanan browser.");
    window.localStorage.setItem(SITE_STORAGE_KEY,value);
    return {saved:true,site};
  } catch(err) { return {saved:false,message:err instanceof Error ? err.message : "Browser menyekat simpanan."}; }
}

export function removeSavedSite():{removed:boolean;message?:string} {
  if(typeof window==="undefined") return {removed:false,message:"Simpanan hanya tersedia dalam browser."};
  try {window.localStorage.removeItem(SITE_STORAGE_KEY);return {removed:true};}
  catch(err) {return {removed:false,message:err instanceof Error ? err.message : "Gagal memadam rekod browser."};}
}

export function downloadSiteGeoJSON(geometry:FeatureGeometry) {
  if(typeof window==="undefined") return;
  const geojson={type:"FeatureCollection",features:[{type:"Feature",properties:{source:"PLANEXUS AI",note:"Preliminary WGS84 site boundary. Not a verified cadastral survey."},geometry:validateSiteBoundary(geometry)}]};
  const blob=new Blob([JSON.stringify(geojson,null,2)],{type:"application/geo+json"});
  const url=URL.createObjectURL(blob);
  const anchor=document.createElement("a");
  anchor.href=url;
  anchor.download="planexus-site-boundary.geojson";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(()=>URL.revokeObjectURL(url),3000);
}
