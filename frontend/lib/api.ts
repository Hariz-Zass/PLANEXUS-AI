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

export type ProposalInputs = {
  name: string;
  development_type: "terrace_housing" | "shoplots" | "other_landed";
  units: number;
  lot_width_m: number;
  lot_depth_m: number;
  roads_pct: number;
  open_space_pct: number;
  facilities_pct: number;
  other_reserve_pct: number;
  policy_profile?: "none" | "national_2016" | "perak_2023";
  housing_category?: "terrace_low_cost" | "terrace_lower_middle" | "terrace_middle" |
    "cluster" | "semi_detached" | "detached" | "zero_lot" | "townhouse" | null;
  storeys?: number | null;
  perak_market_segment?: "perak_low_cost" | "perak_middle" | "perak_affordable" | "perak_open" | null;
  floor_area_m2?: number | null;
  bedrooms?: number | null;
  building_height_m?: number | null;
};

export type PolicyCheck = {
  key:string; title:string; type:"min"|"max";
  value:number; observed:number|null; unit:string;
  result:"meets_number"|"below_min"|"above_max"|"not_supplied";
  source_id:string;source_title:string;source_url:string;source_page:string;
  role:"primary_reference"|"primary_state_reference"|"supplementary_national_reference";
  binding:false;
};

export type PolicyAssessment = {
  registry_version:string; profile_id:string;profile_label:string;
  status:"not_selected"|"not_indexed"|"outside_numeric_reference"|"more_inputs_needed"|
    "insufficient_rule_coverage"|"numeric_reference_only"|"registry_version_changed_review";
  checks:PolicyCheck[];reference_only:true;warnings:string[];
  max_lot_width_m:null;max_lot_depth_m:null;message:string;
};

export type PolicySource = {
  id:string;title:string;year:number|null;issuer:string;
  jurisdiction:string;url:string;evidence:string;scope:string;
  status:"curated_rules"|"catalog_only";
};

export type PolicyCatalog = {
  registry_version:string;
  sources:PolicySource[];
  profiles:{id:string;label:string;details:string}[];
  housing_categories:{id:string;label:string;development_type:ProposalInputs["development_type"]}[];
  national_lot_rules:{
    category:string;storeys:number[];label:string;min_width_m:number;min_depth_m:number;
    min_floor_area_m2:number|null;page:number;source_id:string;url:string;
    max_width_m:null;max_depth_m:null
  }[];
  perak_floor_min_sqft:Record<string,number>;
  perak_other_housing_rules?:Record<string,{code:string;page:number;min_floor_sqft:number;max_storeys:number;min_bedrooms:number;max_height_ft:number;notes?:string;source_url:string;source_page:string}>;
  perak_layout_references?:{
    id:string;label:string;value_ft:number;value_type:string;
    value_m:number;applicability:string;source_id:string;source_url:string;
    source_page:string;automated_geometry_check:false;
  }[];
  perak_market_segments:{id:string;label:string}[];
  not_indexed:string[];disclaimer:string;
};

export type ProposalCalculation = {
  method: string;
  inputs: ProposalInputs;
  policy_assessment?: PolicyAssessment;
  site_area_ha: number;
  lot_area_m2: number;
  required_plot_area_ha: number;
  reserve_total_pct: number;
  net_plots_share_pct: number;
  required_gross_area_ha: number;
  allocations_ha: Record<string, number>;
  gross_site_density_units_per_ha: number;
  gross_site_area_margin_ha: number;
  gross_site_area_check: "arithmetic_area_envelope" | "gross_area_shortfall";
  screening_status: "no_active_analysis" | "no_suitability_layer" | "context_changed" | "invalid_suitability" | "quality_limited" | "indicative_cell_area_only";
  analysis_id: string | null;
  lower_constraint_cell_area_ha_est: number | null;
  lower_constraint_area_margin_ha_est: number | null;
  terrain_screening_cell_area_check: "cell_area_envelope_only" | "cell_area_shortfall" | null;
  quality_warnings: string[];
  conclusion: string;
  not_approval: true;
};

export type SavedProposal = {
  id: string;
  project_id: string;
  created_at_utc: string;
  updated_at_utc: string;
  revision: number;
  analysis_id_at_save: string | null;
  context_changed: boolean;
  policy_review_needed?: boolean;
  policy_registry_version_at_save?: string | null;
  inputs: ProposalInputs;
  result: ProposalCalculation;
};

export type ProposalList = {
  project_id: string;
  project_active_analysis_id: string | null;
  proposals: SavedProposal[];
  storage: string;
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
