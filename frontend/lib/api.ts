export type FeatureGeometry = {
  type: "Polygon" | "MultiPolygon";
  coordinates: number[][][] | number[][][][];
};

export type SlopeClass = {
  id: number;
  name: string;
  min_deg: number;
  max_deg: number | null;
  color: string;
  area_ha_est: number;
  percent_of_valid_slope: number;
};

export type TerrainSuitabilityBand = {
  id:number;
  key:string;
  label:string;
  min_deg:number|null;
  max_deg:number|null;
  color:string;
  reason:string;
  pixels:number;
  area_ha_est:number;
  share_of_assessed_pct:number|null;
};

export type TerrainSuitabilitySummary = {
  version:string;
  method:string;
  bands:TerrainSuitabilityBand[];
  assessed_pixels:number;
  site_mask_pixels:number;
  assessed_area_ha_est:number;
  unassessed_area_ha_est:number;
  coverage_of_site_pct_est:number;
  area_exceeds_site_due_to_pixelization:boolean;
  source_resolution_m?:number|null;
  class_overlay_truncated:boolean;
  disclaimer:string;
  warnings:string[];
};

export type TerrainReport = {
  analysis_id: string;
  created_at_utc: string;
  geometry: FeatureGeometry;
  source: {
    id: string;
    name: string;
    publisher: string;
    reference?: string;
    data_type: string;
    nominal_resolution_m?: number | null;
    verified: string;
    retrieved_at_utc?: string;
    fallback_used?: boolean;
    fallback_reason?: string | null;
  };
  metrics: {
    site_area_ha: number;
    elevation_min_m: number;
    elevation_mean_m: number;
    elevation_max_m: number;
    elevation_range_m: number;
    slope_mean_deg: number;
    slope_max_deg: number;
    coverage_percent_est: number;
    analysis_resolution_m_est: number;
    valid_elevation_pixels: number;
    valid_slope_pixels: number;
    slope_classes: SlopeClass[];
    contour_interval_m?: number | null;
    contour_features?: number;
    elevation_legend?: {class_id:number;color:string;min_m:number;max_m:number}[];
    horizontal_crs: string;
    method: string;
  };
  slope_geojson: GeoJSON.FeatureCollection;
  suitability?: TerrainSuitabilitySummary;
  suitability_geojson?: GeoJSON.FeatureCollection;
  elevation_geojson?: GeoJSON.FeatureCollection;
  contours_geojson?: GeoJSON.FeatureCollection;
  warnings: string[];
  assessment_scope: string;
};

export type SavedSummary = {
  analysis_id: string;
  created_at_utc: string;
  site_area_ha: number;
  source_name: string;
};

export type ProjectSummary = {
  id: string;
  name: string;
  description: string;
  has_site: boolean;
  site_area_ha: number | null;
  active_analysis_id: string | null;
  revision: number;
  created_at_utc: string;
  updated_at_utc: string;
};

export type ProjectDetail = ProjectSummary & {
  geometry: FeatureGeometry | null;
  analyses: SavedSummary[];
};

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "")).replace(/\/$/, "");

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  if (!API_BASE) throw new Error("GIS backend belum disambungkan pada Vercel. Analisis topografi belum tersedia secara online.");
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...options });
  } catch {
    throw new Error("GIS backend tidak dapat dihubungi. Semak sambungan dan konfigurasi API PLANEXUS.");
  }
  if (!response.ok) {
    let detail = `Ralat HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || detail);
    } catch { /* preserve HTTP status */ }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
