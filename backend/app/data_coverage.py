"""Truthful per-module source capability ledger, not a completeness score."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import os
from .policy_registry import catalog
from .sources import SOURCE_CATALOG
from .copilot import capabilities as ai_capabilities

def manifest():
    docs=catalog()["sources"]
    curated=[s for s in docs if s["status"]=="curated_rules"]
    catalogue=[s for s in docs if s["status"]=="catalog_only"]
    modules=[
        ("terrain_auto","Automatic DSM, slope, elevation and contours","tested_real_data","copernicus_public_if_coverage","GLO-30 Public and clearly labelled GLO-90 fallback; both DSM not survey DTM."),
        ("terrain_upload","User-supplied survey raster","tested_local","manual_authorized_source","File CRS, units, NoData checked; survey source authenticity not independently certified."),
        ("projects","Account, project save/reopen, export","tested_local_ci","server_data","Full production cloud storage not deployed."),
        ("gpp","Housing GPP reference assessment","partially_indexed","limited_official_rules",f"{len(curated)} numeric curated documents; {len(catalogue)} only catalogued. Current PBT adoption unverified."),
        ("nearby","Nearby amenities, roads and waterways","on_demand_external","osm_community_unverified","Live OSM/Overpass plus optional local Geofabrik GeoPackage snapshot; neither is official site/road certification."),
        ("zoning_rt","Current gazetted RT/PBT zoning at coordinates","NOT_INTEGRATED","requires_permission_and_gazette_match","I-Plan online viewer exists, but automated reuse rights and gazetted RT/PBT mapping not established."),
        ("rfn_rsn","RFN, RSN and RKK site applicability","NOT_INTEGRATED","missing_official_georeferenced_index","No location-specific adopted plan and gazette cross-check."),
        ("hydrology","Hydrology, runoff and official flood hazard","NOT_INTEGRATED","jps_data_not_connected","JPS public water levels do not supply parcel flood hazard or design runoff."),
        ("external_roads","Road network and legal public access","manual_road_sketch_only","no_certified_external_access","Road sketches/nearby OSM roads do not establish lawful site access."),
        ("development","Scenario, housing yield, smart layout","tested_screening_only","user_assumptions_plus_limited_gpp","Not a PBT-authorized planning yield; actual RT, road, flood and DTM needed."),
        ("copilot","Evidence-grounded AI planning","deterministic_or_optional_llm","saved_terrain_evidence_only","No connected authoritative RT/RSN, flood or parcel zoning."),
    ]
    return {
       "version":"2026-11-03-functional-evidence-audit-v1",
       "generated_at_utc":datetime.now(timezone.utc).isoformat(),
       "not_a_complete_data_claim":True,
       "modules":[{"id":i,"name":n,"implementation":imp,"data_status":st,"limits":lim} for i,n,imp,st,lim in modules],
       "numeric_policy_documents":len(curated),
       "catalogue_only_policy_documents":len(catalogue),
       "policy_sources":[{"id":s["id"],"title":s["title"],"status":s["status"],"url":s["url"],"alternate_official_url":s.get("alternate_official_url"),"evidence":s["evidence"]} for s in docs],
       "data_adapters":[{"id":s["id"],"name":s["name"],"reference":s["reference"],"type":s["data_type"],"mode":"automatic_when_accessible"} for s in SOURCE_CATALOG],
       "official_portals":[
         {"name":"PLANMalaysia I-Plan","url":"https://iplan.planmalaysia.gov.my/public/geoportal","reuse":"Official viewer; no presumption of extraction licence. Gazetted RT/PBT prevails."},
         {"name":"MyGDI national catalogue","url":"https://mygdix.mygeoportal.gov.my/","reuse":"Catalogue access does not grant G2G/source-agency dataset redistribution."},
         {"name":"JPS InfoBanjir","url":"https://publicinfobanjir.water.gov.my/","reuse":"Live station measurements are NOT site flood-hazard certification."},
         {"name":"Malaysia official open API","url":"https://developer.data.gov.my/","reuse":"Only use dataset-specific licensed, location-relevant data."}],
       "open_source_fallbacks":[
          {"id":"geofabrik_osm_gpkg","source":"Geofabrik / OpenStreetMap",
           "url":"https://download.geofabrik.de/asia/malaysia-singapore-brunei.html",
           "license":"ODbL","configured":bool(os.getenv("PLANEXUS_OSM_GEOFABRIK_GPKG","").strip()
             and Path(os.getenv("PLANEXUS_OSM_GEOFABRIK_GPKG","")).is_file()),
           "mode":"backend_offline_snapshot_after_overpass_error",
           "note":"Operator must provision a regularly refreshed local GeoPackage. Not authoritative."},
          {"id":"overture_maps","source":"Overture Maps Foundation",
           "url":"https://docs.overturemaps.org/","license":"CDLA-Permissive or ODbL depending on layer",
           "configured":False,"mode":"research_only_not_integrated",
           "note":"GeoParquet adapter not implemented; do not claim dataset connected."}],
       "ai_generative_configured":bool(ai_capabilities()["generative_ai_configured"]),
       "legal_warning":"Do not ingest, republish or claim statutory zoning without authority and source-version verification.",
    }
