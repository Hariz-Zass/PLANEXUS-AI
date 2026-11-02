"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import {
  AlertTriangle, ArrowRight, ArrowUpRight, CheckCircle2, CircleAlert, Compass,
  Database, Download, FileCode2, Layers3, LoaderCircle, MapPin, MousePointer2,
  PenLine, RotateCcw, Route, Ruler, Save, ShieldCheck, Trash2
} from "lucide-react";
import { api, type ProjectDetail, type TerrainReport, type LayoutLine, type LayoutInputs,
  type LayoutPreview, type SavedLayout } from "@/lib/api";

const LayoutMap=dynamic(()=>import("@/components/LayoutMap"),{ssr:false});
type Props={
  project:ProjectDetail|null;
  report:TerrainReport|null;
  backendConnected:boolean;
  onOpenProjects:()=>void;
  onOpenTerrain:()=>void;
};

const EMPTY_INPUT:LayoutInputs={
  name:"Concept road and land envelope",
  road_centerlines:[],
  assumed_road_width_m:15.24,
  front_road_buffer_m:0,
  perimeter_offset_m:0,
  policy_profile:"none",
  perak_market_segment:null,
};

function fmt(value:number|null|undefined,digits=3){
  return value===null||value===undefined||!Number.isFinite(value)?"—":
    value.toLocaleString("en-MY",{minimumFractionDigits:digits,maximumFractionDigits:digits});
}
function isLine(obj:unknown):obj is LayoutLine{
  if(!obj||typeof obj!=="object")return false;
  const entry=obj as {type?:unknown;coordinates?:unknown};
  return entry.type==="LineString"&&Array.isArray(entry.coordinates)&&
    entry.coordinates.length>=2&&entry.coordinates.length<=200&&
    entry.coordinates.every(p=>Array.isArray(p)&&p.length===2&&
      p.every(v=>typeof v==="number"&&Number.isFinite(v))&&
      p[0]>=-180&&p[0]<=180&&p[1]>=-90&&p[1]<=90);
}
function parseRoads(raw:unknown):LayoutLine[]{
  const object=raw as {type?:string;features?:unknown[];geometry?:unknown;coordinates?:unknown};
  if(!object||typeof object!=="object")throw Error("GeoJSON line geometry is required.");
  if(object.type==="LineString")return isLine(object)?[object]:[];
  if(object.type==="MultiLineString"&&Array.isArray(object.coordinates))
    return object.coordinates.map(coords=>({type:"LineString",coordinates:coords}))
      .filter(isLine);
  if(object.type==="Feature")return parseRoads(object.geometry);
  if(object.type==="FeatureCollection"&&Array.isArray(object.features))
    return object.features.flatMap(item=>parseRoads(item));
  throw Error("Import LineString, MultiLineString or a GeoJSON FeatureCollection of road lines.");
}
function exportLines(inputs:LayoutInputs){
  const geojson={
    type:"FeatureCollection",
    properties:{origin:"PLANEXUS AI conceptual sketched centrelines only",
      width_assumed_m:inputs.assumed_road_width_m,
      warning:"Not a surveyed road reservation or GPP approval"},
    features:inputs.road_centerlines.map((line,index)=>({
      type:"Feature",properties:{road_index:index+1,
        assumed_reservation_width_m:inputs.assumed_road_width_m},
      geometry:line,
    })),
  };
  const url=URL.createObjectURL(new Blob([JSON.stringify(geojson,null,2)],{
    type:"application/geo+json",
  }));
  const anchor=document.createElement("a");
  anchor.href=url;anchor.download="PLANEXUS-concept-road-centrelines.geojson";
  document.body.appendChild(anchor);anchor.click();anchor.remove();
  window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function validInput(value:LayoutInputs){
  if(value.name.trim().length<3||value.name.length>100)return "Enter a layout name of 3–100 characters.";
  if(value.road_centerlines.length>12)return "A local draft is limited to 12 centreline sketches.";
  if(!Number.isFinite(value.assumed_road_width_m)||value.assumed_road_width_m<3||value.assumed_road_width_m>60)
    return "Assumed road reservation width must be 3–60 m.";
  if(!Number.isFinite(value.front_road_buffer_m)||value.front_road_buffer_m<0||value.front_road_buffer_m>30)
    return "Concept front-road band must be 0–30 m.";
  if(!Number.isFinite(value.perimeter_offset_m)||value.perimeter_offset_m<0||value.perimeter_offset_m>30)
    return "Concept site perimeter band must be 0–30 m.";
  return "";
}
const STATUS:Record<string,string>={
  no_active_suitability:"DEM NOT YET ANALYSED",
  no_suitability_in_report:"RERUN DEM ANALYSIS",
  report_site_mismatch:"GIS SITE MISMATCH",
  incomplete_vector_overlay:"GIS OVERLAY INCOMPLETE",
  large_or_invalid_overlay:"GIS VECTOR LIMIT",
  invalid_suitability_overlay:"INVALID GIS OVERLAY",
  low_slope_vector_approximation:"SLOPE OVERLAY AVAILABLE",
  analysis_changed_review_required:"NEW GIS / RECHECK REQUIRED",
};

export default function LayoutStudio({project,report,backendConnected,onOpenProjects,onOpenTerrain}:Props){
  const [inputs,setInputs]=useState<LayoutInputs>(EMPTY_INPUT);
  const [saved,setSaved]=useState<SavedLayout|null>(null);
  const [preview,setPreview]=useState<LayoutPreview|null>(null);
  const [previewKey,setPreviewKey]=useState("");
  const [drawing,setDrawing]=useState(false);
  const [drawPoints,setDrawPoints]=useState(0);
  const [resetCounter,setResetCounter]=useState(0);
  const [loading,setLoading]=useState(false);
  const [busy,setBusy]=useState<"preview"|"save"|null>(null);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const importRef=useRef<HTMLInputElement|null>(null);

  const projectId=project?.id??null;
  const activeAnalysisId=project?.active_analysis_id??null;
  const projectRevision=project?.revision??null;
  const base=projectId?"/api/projects/"+encodeURIComponent(projectId)+"/layout":"";
  const key=JSON.stringify(inputs);
  const visiblePreview=key===previewKey?preview:null;
  const siteChanged=saved?.site_changed??false;
  const analysisChanged=saved?.analysis_changed??false;
  const draftChanged=saved!==null&&JSON.stringify(saved.inputs)!==key;
  const stale=Boolean(siteChanged||analysisChanged);
  const valid=validInput(inputs);
  const roadLines=siteChanged?[]:inputs.road_centerlines;
  const hasSite=Boolean(project?.geometry);
  const hasLow=visiblePreview?.lower_slope_remaining_ha!==null&&
    visiblePreview?.lower_slope_remaining_ha!==undefined;

  const reload=useCallback(async()=>{
    if(!base||!backendConnected||!project?.geometry)return;
    setLoading(true);setError("");
    try{
      const record=await api<SavedLayout>(base);
      setSaved(record);
      setInputs(record.inputs);
      setPreview(record.preview);
      setPreviewKey(JSON.stringify(record.inputs));
      setDrawing(false);setDrawPoints(0);setResetCounter(n=>n+1);
    }catch(e){setError(e instanceof Error?e.message:"Failed to load saved layout.");}
    finally{setLoading(false);}
  },[base,backendConnected,project?.geometry]);

  useEffect(()=>{
    if(!hasSite||!backendConnected){
      setSaved(null);setPreview(null);setPreviewKey("");
      return;
    }
    let alive=true;
    setLoading(true);setError("");
    const load=async()=>{
      try{
        const record=await api<SavedLayout>(base);
        if(!alive)return;
        setSaved(record);setInputs(record.inputs);
        setPreview(record.preview);
        setPreviewKey(JSON.stringify(record.inputs));
        setDrawing(false);setDrawPoints(0);setResetCounter(n=>n+1);
      }catch(e){if(alive)setError(e instanceof Error?e.message:"Cannot open the layout.");}
      finally{if(alive)setLoading(false);}
    };
    void load();
    return()=>{alive=false;};
  },[base,backendConnected,hasSite,projectId,activeAnalysisId,projectRevision]);

  async function previewLayout(value:LayoutInputs=inputs){
    if(!base||!backendConnected||busy||validInput(value))return;
    setBusy("preview");setError("");setNotice("");
    try{
      const result=await api<{preview:LayoutPreview}>(base+"/preview",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(value),
      });
      setPreview(result.preview);setPreviewKey(JSON.stringify(value));
      setNotice("Concept geometry re-calculated from this draft. Use Save layout to preserve it.");
    }catch(e){setError(e instanceof Error?e.message:"Unable to measure this road sketch.");}
    finally{setBusy(null);}
  }
  async function save(){
    if(!base||!backendConnected||busy||valid||!saved)return;
    setBusy("save");setError("");setNotice("");
    try{
      const result=await api<SavedLayout>(base,{
        method:"PUT",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({expected_revision:saved.revision,inputs}),
      });
      setSaved(result);
      setInputs(result.inputs);
      setPreview(result.preview);
      setPreviewKey(JSON.stringify(result.inputs));
      setNotice("Layout sketch saved to this project's local SQLite record. It will survive refresh and be included in backups.");
    }catch(e){setError(e instanceof Error?e.message:"Could not save this project layout.");}
    finally{setBusy(null);}
  }
  function addRoad(road:LayoutLine){
    setDrawing(false);setDrawPoints(0);setResetCounter(n=>n+1);
    if(inputs.road_centerlines.length>=12){
      setError("Maximum 12 road alignments per project sketch.");return;
    }
    setInputs(current=>({...current,road_centerlines:[...current.road_centerlines,road]}));
    setNotice("Road alignment added as a DRAFT. Width is still an assumption. Preview and save to calculate corridor area.");
    setError("");
  }
  function clearRoads(){
    setDrawing(false);setResetCounter(n=>n+1);setDrawPoints(0);
    setInputs(current=>({...current,road_centerlines:[]}));
    setNotice("All road sketches cleared in the draft. Click Save layout to preserve the change.");
    setError("");
  }
  async function upload(event:ChangeEvent<HTMLInputElement>){
    const file=event.target.files?.[0];
    event.target.value="";
    if(!file)return;
    setError("");setNotice("");
    try{
      if(file.size>1_500_000)throw Error("Road GeoJSON exceeds 1.5MB.");
      const content:unknown=JSON.parse(await file.text());
      const lines=parseRoads(content);
      if(!lines.length)throw Error("No valid LineString roads were found.");
      if(lines.length+inputs.road_centerlines.length>12)
        throw Error("Maximum 12 road alignments. Clear existing roads or reduce imported features.");
      setInputs(current=>({...current,road_centerlines:[...current.road_centerlines,...lines]}));
      setNotice(lines.length+" GeoJSON road alignment(s) imported. Preview first; backend validates they remain within the site.");
    }catch(e){setError(e instanceof Error?e.message:"Invalid road GeoJSON.");}
  }
  const layerLegend=[
    {color:"#b4f77d",name:"Site boundary"},
    {color:"#5bb4ce",name:"After assumed exclusions"},
    {color:"#8fea94",name:"Lower-slope overlap (if GIS)"},
    {color:"#38d2c9",name:"Modeled road reservation"},
    {color:"#edba77",name:"Concept front-road band"},
    {color:"#8c97af",name:"Perimeter exclusion"},
  ];

  return <section className="layout-studio" aria-label="PLANEXUS Smart Layout screening">
    <div className="layout-page-header">
      <div>
        <div className="eyebrow"><span className="eyebrow-dot"/> PHASE 05 <span className="eyebrow-slash">//</span> MODULE 003 / CONCEPT LAYOUT</div>
        <h1>Smart <span className="h1-accent">Layout.</span><span className="hero-title-mark">/</span></h1>
        <p>Sketch road centrelines, test assumed reservations and conceptual offsets, then intersect the remaining land with measured lower-slope terrain. No lot placement or development permission is inferred.</p>
      </div>
      <span className="layout-scope-badge"><ShieldCheck size={16}/> GEOMETRY SCREENING · NOT APPROVAL</span>
    </div>
    {!hasSite?<div className="proposal-empty">
      <div className="proposal-empty-icon"><MapPin size={29}/></div>
      <div><strong>Open a project with a saved site boundary</strong>
        <p>Start in Project Workspace. Draw or import its real site polygon, then return here to sketch roads and land buffers.</p>
      </div>
      <button type="button" className="btn btn-accent" onClick={onOpenProjects}>
        <Database size={16}/> Project Workspace <ArrowRight size={16}/>
      </button>
    </div>:<>
      <div className="layout-project-strip">
        <span><MapPin size={17}/><strong>{project?.name}</strong></span>
        <span>{fmt(project?.site_area_ha)} ha site · {activeAnalysisId?"Active GIS linked":"No active DEM"}</span>
        <button type="button" className="btn btn-outline" onClick={onOpenTerrain}>
          <Layers3 size={14}/> Terrain analysis
        </button>
      </div>
      {!backendConnected&&<div className="proposal-alert"><CircleAlert size={17}/> Local FastAPI backend offline. Road edits cannot be verified or saved.</div>}
      {error&&<div className="proposal-alert" role="alert"><CircleAlert size={17}/>{error}</div>}
      {notice&&<div className="proposal-success" role="status"><CheckCircle2 size={17}/>{notice}</div>}
      {loading&&<div className="layout-loading"><LoaderCircle size={18} className="spin"/> Loading local layout record…</div>}
      {siteChanged&&<div className="layout-blocker" role="alert">
        <AlertTriangle size={20}/>
        <div><strong>Site boundary changed — saved road sketches are hidden.</strong>
          <span>These alignments belong to the previous polygon. Clear roads and save a new layout before using the new site.</span>
        </div>
        <button type="button" className="btn btn-outline" onClick={clearRoads}>Clear old roads</button>
      </div>}
      {!siteChanged&&analysisChanged&&<div className="layout-blocker" role="alert">
        <RotateCcw size={20}/>
        <div><strong>Active DEM changed since this layout was saved.</strong>
          <span>Only geometry remains valid. Re-preview against the current DEM and save to confirm this evidence version.</span>
        </div>
        <button type="button" className="btn btn-outline" onClick={()=>void reload()}>Reload</button>
      </div>}
      <div className="layout-main-grid">
        <div className="layout-map-card">
          <div className="layout-card-header">
            <div><span className="section-overline">01 / SPATIAL SKETCH</span><h2>Roads & land constraints</h2></div>
            <span className="layout-tag"><Compass size={13}/> WGS84 DRAW / UTM MEASURE</span>
          </div>
          <div className="layout-toolbar">
            <button type="button" className={"btn "+(drawing?"btn-accent":"btn-outline")}
              disabled={loading||busy!==null||siteChanged||inputs.road_centerlines.length>=12}
              onClick={()=>{setDrawing(value=>!value);setDrawPoints(0);setResetCounter(n=>n+1);}}>
              <PenLine size={15}/>{drawing?"Drawing road…":"Draw road centreline"}
            </button>
            <button type="button" className="btn btn-outline" disabled={drawing||busy!==null||siteChanged}
              onClick={()=>importRef.current?.click()}><FileCode2 size={15}/> Import road GeoJSON</button>
            <button type="button" className="btn btn-outline" disabled={!inputs.road_centerlines.length||busy!==null}
              onClick={()=>{setInputs(value=>({...value,road_centerlines:value.road_centerlines.slice(0,-1)}));setNotice("Last road removed from draft.");}}>
              <RotateCcw size={15}/> Undo road
            </button>
            <button type="button" className="btn btn-outline" disabled={!inputs.road_centerlines.length||busy!==null}
              onClick={clearRoads}><Trash2 size={15}/> Clear</button>
          </div>
          <div className="layout-map-wrap">
            {project?.geometry&&<LayoutMap site={project.geometry} inputRoads={roadLines}
              preview={siteChanged?null:visiblePreview}
              drawing={drawing} onRoadDrawn={addRoad} onPointCount={setDrawPoints}
              resetCounter={resetCounter}/>}
            {drawing&&<div className="layout-draw-notice"><MousePointer2 size={16}/>
              <span>Click to add road vertices · Double-click to finish · <strong>{drawPoints} points</strong></span>
              <button type="button" onClick={()=>{setDrawing(false);setResetCounter(n=>n+1);}}>Cancel</button>
            </div>}
            {!drawing&&!inputs.road_centerlines.length&&<div className="layout-map-overlay-note">
              <Route size={18}/> Sketch a road alignment or import a LineString GeoJSON. The map does not invent roads.
            </div>}
            <span className="layout-map-watermark">CONCEPT / NO PLANNING APPROVAL</span>
          </div>
          <div className="layout-legend">{layerLegend.map(entry=><span key={entry.name}>
            <i style={{backgroundColor:entry.color}}/>{entry.name}</span>)}</div>
          <div className="layout-legend-note"><CircleAlert size={14}/>
            The road line is mapped; its width is a typed assumption. “Front-road band” is not an actual house-frontage setback compliance check.
          </div>
          <input ref={importRef} hidden type="file" accept=".geojson,.json,application/geo+json,application/json"
            onChange={event=>void upload(event)}/>
        </div>
        <div className="layout-controls-card">
          <div className="layout-card-header">
            <div><span className="section-overline">02 / ASSUMPTIONS</span><h2>Concept layout controls</h2></div>
            <Ruler size={20}/>
          </div>
          <div className="layout-form">
            <label className="proposal-field">Concept label
              <input type="text" maxLength={100} value={inputs.name}
                onChange={event=>setInputs(current=>({...current,name:event.target.value}))}/>
            </label>
            <label className="proposal-field">Assumed road reservation width (m)
              <input type="number" min="3" max="60" step="any" value={inputs.assumed_road_width_m}
                onChange={event=>setInputs(current=>({...current,assumed_road_width_m:Number(event.target.value)}))}/>
              <small>This is an entered width, not a measurement of an existing road.</small>
            </label>
            <label className="proposal-field">Assumed front-road margin beyond road edge (m)
              <input type="number" min="0" max="30" step="any" value={inputs.front_road_buffer_m}
                onChange={event=>setInputs(current=>({...current,front_road_buffer_m:Number(event.target.value)}))}/>
              <small>Concept exclusion only; building footprints and actual lot frontages are not modelled.</small>
            </label>
            <label className="proposal-field">Optional inward perimeter exclusion (m)
              <input type="number" min="0" max="30" step="any" value={inputs.perimeter_offset_m}
                onChange={event=>setInputs(current=>({...current,perimeter_offset_m:Number(event.target.value)}))}/>
              <small>Not a GPP side/rear setback; adjust as an illustrative design constraint.</small>
            </label>
            <div className="layout-form-rule"/>
            <span className="section-overline">03 / GPP REFERENCE SCOPE</span>
            <label className="proposal-field">GPP scope (manual choice)
              <select value={inputs.policy_profile}
                onChange={event=>setInputs(current=>({...current,
                  policy_profile:event.target.value as LayoutInputs["policy_profile"],
                  perak_market_segment:null}))}>
                <option value="none">No jurisdiction selected</option>
                <option value="perak_2023">Perak 2023 — PR1 terrace references</option>
              </select>
            </label>
            {inputs.policy_profile==="perak_2023"&&<label className="proposal-field">
              Terrace category under Perak PR1
              <select value={inputs.perak_market_segment??""} onChange={event=>setInputs(current=>({
                ...current,perak_market_segment:(event.target.value||null) as LayoutInputs["perak_market_segment"],
              }))}>
                <option value="">Select cost category</option>
                <option value="perak_low_cost">Kos rendah — front setback 15 ft</option>
                <option value="perak_middle">Kos sederhana — front setback 20 ft</option>
                <option value="perak_affordable">Mampu milik — front setback 20 ft</option>
                <option value="perak_open">Terbuka / bebas — front setback 20 ft</option>
              </select>
            </label>}
            {inputs.policy_profile==="perak_2023"&&<p className="layout-gpp-context">
              Perak PR1 reference: minimum 50 ft (15.24 m) service road. Front setback reference: 15 ft low-cost / 20 ft other terrace classes. Actual geometry and current PBT adoption are <strong>not verified</strong>.
            </p>}
            {valid&&<div className="proposal-validation" role="alert"><CircleAlert size={15}/>{valid}</div>}
            {draftChanged&&<p className="layout-draft-flag"><CircleAlert size={14}/> Unsaved changes. Click Preview to refresh overlays, then Save.</p>}
            <div className="layout-form-actions">
              <button type="button" className="btn btn-outline"
                disabled={!backendConnected||busy!==null||loading||Boolean(valid)||siteChanged}
                onClick={()=>void previewLayout()}>
                {busy==="preview"?<LoaderCircle className="spin" size={16}/>:<Layers3 size={16}/>}
                Preview layout
              </button>
              <button type="button" className="btn btn-accent"
                disabled={!backendConnected||busy!==null||loading||Boolean(valid)||!saved||drawing||siteChanged}
                onClick={()=>void save()}>
                {busy==="save"?<LoaderCircle className="spin" size={16}/>:<Save size={16}/>}
                Save layout
              </button>
            </div>
            {siteChanged&&<button type="button" className="btn btn-outline"
              onClick={()=>{clearRoads();setPreview(null);setPreviewKey("");setSaved(current=>current?{...current,site_changed:false}:null);}}>
              <Trash2 size={15}/> Start fresh for new boundary
            </button>}
            {inputs.road_centerlines.length>0&&<button type="button"
              className="layout-download" onClick={()=>exportLines(inputs)}>
              <Download size={15}/> Export centreline GeoJSON <ArrowUpRight size={12}/>
            </button>}
            <p className="layout-persistence-note"><Database size={15}/>
              {saved?.exists?"SQLite saved revision "+saved.revision:"Not yet saved"} · {inputs.road_centerlines.length} road(s)
              · {saved?.analysis_id_at_save?"DEM ID "+saved.analysis_id_at_save.slice(0,8):"No saved DEM link"}</p>
          </div>
        </div>
      </div>
      <section className="layout-results" aria-label="GIS layout capacity screening results">
        <div className="layout-card-header">
          <div><span className="section-overline">04 / MEASURED GEOMETRY</span><h2>Indicative area envelope</h2></div>
          <span className="layout-tag"><ShieldCheck size={13}/> NOT BUILDABLE AREA</span>
        </div>
        {!visiblePreview?<div className="layout-unavailable"><Layers3 size={22}/>
          <p>{siteChanged?"Previous layout belongs to another site. Reset it before screening.":"Click Preview layout to calculate areas from the current draft."}</p>
        </div>:<>
          <div className="layout-stat-grid">
            {[
              {name:"SITE POLYGON (PROJECTED)",number:visiblePreview.site_area_ha,unit:"ha"},
              {name:"MODELED ROAD CORRIDOR",number:visiblePreview.road_corridor_ha,unit:"ha"},
              {name:"COMBINED MODELED EXCLUSIONS",number:visiblePreview.combined_exclusions_ha,unit:"ha"},
              {name:"GROSS UNENCUMBERED ENVELOPE",number:visiblePreview.gross_unencumbered_ha,unit:"ha"},
            ].map(item=><div className="layout-stat" key={item.name}>
              <small>{item.name}</small><strong>{fmt(item.number)} <em>{item.unit}</em></strong>
            </div>)}
          </div>
          <div className="layout-slope-summary">
            <div className="layout-slope-header"><span><Layers3 size={18}/> LOWER TERRAIN CONSTRAINT OVERLAP</span>
              <span>{STATUS[visiblePreview.terrain_status]??visiblePreview.terrain_status}</span></div>
            {hasLow?<div className="layout-slope-grid">
              <div><small>Low-slope cells remaining after modeled exclusions</small><strong>{fmt(visiblePreview.lower_slope_remaining_ha)} ha</strong></div>
              <div><small>Largest contiguous low-slope polygon</small><strong>{fmt(visiblePreview.largest_contiguous_lower_patch_ha)} ha</strong></div>
              <div><small>Disconnected patches (not lots)</small><strong>{visiblePreview.lower_patch_count}</strong></div>
            </div>:<p>No defensible lower-slope polygon overlap available. Run/select a current DEM analysis with a complete suitability overlay. Gross geometry is NOT a substitute for terrain suitability.</p>}
            <div className={"layout-confidence"+(visiblePreview.quality_status==="quality_limited"?" is-limited":"")}>
              <ShieldCheck size={15}/>
              {visiblePreview.quality_status==="quality_limited"?
                "LOW CONFIDENCE — incomplete/coarse DEM; verify with surveyed DTM":
                visiblePreview.quality_status==="preliminary_raster"?
                "PRELIMINARY RASTER — no lot-level buildability proven":
                "GEOMETRY ONLY — no defensible raster conclusion"}
            </div>
          </div>
          <div className="layout-measurement-strip">
            <span><Route size={15}/> {fmt(visiblePreview.road_centerline_length_m,1)} m total sketched centreline</span>
            <span>{fmt(visiblePreview.road_front_margin_ha)} ha front-road band</span>
            <span>{fmt(visiblePreview.perimeter_exclusion_ha)} ha perimeter band</span>
          </div>
          {visiblePreview.policy_checks.length>0&&<div className="layout-policy-results">
            <h3><Ruler size={16}/> Perak PR1 numerical reference (typed dimensions only)</h3>
            {visiblePreview.policy_checks.map(check=><div key={check.key} className="layout-policy-row">
              <div><strong>{check.label}</strong><small>Entered {fmt(check.entered_m,2)} m · Reference min {fmt(check.minimum_m,2)} m · {check.source_page}</small></div>
              <span className={check.result.includes("below")?"is-below":""}>
                {check.result==="not_drawn"?"No line":check.result.includes("below")?"Below reference":"Entered value meets reference"}
              </span>
              <a href={check.source_url} target="_blank" rel="noopener noreferrer" aria-label={"Official source for "+check.label}><ArrowUpRight size={15}/></a>
            </div>)}
            <p>No building footprints or existing road widths are surveyed. These checks do not establish GPP/PBT compliance.</p>
          </div>}
          <details className="layout-warnings"><summary><CircleAlert size={15}/> GIS warnings & assumptions ({visiblePreview.warnings.length})</summary>
            {visiblePreview.warnings.map((item,index)=><p key={index}>{item}</p>)}
          </details>
        </>}
      </section>
      <div className="layout-footer-warning">
        <AlertTriangle size={20}/>
        <p><strong>Town planner's note:</strong> This module measures preliminary *area envelopes* from the actual site polygon, drawn road-centrelines and slope-polygon intersection. It does <strong>not</strong> fit housing lots, verify road reserve ownership, implement front/side/rear setbacks of individual buildings, establish buildable land or issue planning approval. Full layout feasibility remains future work.</p>
      </div>
    </>}
  </section>;
}
