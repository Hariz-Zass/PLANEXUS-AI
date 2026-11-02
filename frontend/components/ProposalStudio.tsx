"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  ArrowRight, Building2, Calculator, ChartNoAxesCombined, CheckCircle2, CircleAlert,
  ClipboardList, Database, FilePlus2, Layers3, LoaderCircle, MapPin, RotateCcw,
  Save, ShieldCheck, Trash2
} from "lucide-react";
import { api, type ProjectDetail, type ProposalInputs, type SavedProposal, type ProposalList } from "@/lib/api";
import GppCheckPanel from "@/components/GppCheckPanel";

type Props={
  project:ProjectDetail|null;
  backendConnected:boolean;
  onOpenProjects:()=>void;
};

const DEFAULT_PROPOSAL:ProposalInputs={
  name:"Option A - 300 mid terrace lots (20 x 70 ft)",
  development_type:"terrace_housing",
  units:300,
  lot_width_m:6.096,
  lot_depth_m:21.336,
  roads_pct:20,
  open_space_pct:10,
  facilities_pct:5,
  other_reserve_pct:5,
  policy_profile:"none",
  housing_category:"terrace_middle",
  storeys:1,
  perak_market_segment:null,
  floor_area_m2:null,
  bedrooms:null,
  building_height_m:null,
};
const allocationFields=[
  {key:"roads_pct" as const,name:"Roads and access",short:"Roads",color:"#5bc8ac"},
  {key:"open_space_pct" as const,name:"Open space",short:"Open",color:"#a9da83"},
  {key:"facilities_pct" as const,name:"Community facilities",short:"Facilities",color:"#e5ca7a"},
  {key:"other_reserve_pct" as const,name:"Other reserve / infrastructure",short:"Other",color:"#b09de6"},
];
const DEVELOPMENT_LABELS={
  terrace_housing:"Terrace / landed houses",
  shoplots:"Shoplots / commercial plots",
  other_landed:"Other landed plots",
};

function decimal(value:number|null|undefined,digits=3){
  return value===null||value===undefined||!Number.isFinite(value)?"—":
    value.toLocaleString("en-MY",{minimumFractionDigits:digits,maximumFractionDigits:digits});
}

function validity(value:ProposalInputs){
  const reserved=value.roads_pct+value.open_space_pct+value.facilities_pct+value.other_reserve_pct;
  if(value.name.trim().length<3)return "Enter a scenario name (at least 3 characters).";
  if(!Number.isSafeInteger(value.units)||value.units<1||value.units>100000)return "Units must be a whole number between 1 and 100,000.";
  if(!Number.isFinite(value.lot_width_m)||value.lot_width_m<=0||value.lot_width_m>150)return "Lot frontage must be above zero, at most 150 metres.";
  if(!Number.isFinite(value.lot_depth_m)||value.lot_depth_m<=0||value.lot_depth_m>300)return "Lot depth must be above zero, at most 300 metres.";
  if(allocationFields.some(item=>!Number.isFinite(value[item.key])||value[item.key]<0||value[item.key]>70))
    return "Each allocation percentage must be between 0% and 70%.";
  if(!Number.isFinite(reserved)||reserved>=85)return "Combined land reserves must total less than 85%.";
  return "";
}

export default function ProposalStudio({project,backendConnected,onOpenProjects}:Props){
  const [inputs,setInputs]=useState<ProposalInputs>(DEFAULT_PROPOSAL);
  const [proposals,setProposals]=useState<SavedProposal[]>([]);
  const [selectedId,setSelectedId]=useState<string|null>(null);
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");

  const projectId=project?.id??null;
  const activeAnalysisId=project?.active_analysis_id??null;
  const projectRevision=project?.revision??0;
  const base=projectId?"/api/projects/"+encodeURIComponent(projectId)+"/proposals":"";
  const load=useCallback(async()=>{
    if(!base||!backendConnected||!project?.geometry){setProposals([]);return;}
    const response=await api<ProposalList>(base);
    setProposals(response.proposals);
  },[base,backendConnected,project?.geometry]);

  useEffect(()=>{
    if(!project?.geometry||!backendConnected){setProposals([]);return;}
    let alive=true;
    setLoading(true);setError("");
    const request=async()=>{
      try {
        const response=await api<ProposalList>(base);
        if(alive)setProposals(response.proposals);
      }catch(e){if(alive)setError(e instanceof Error?e.message:"Saved proposals cannot be loaded.");}
      finally{if(alive)setLoading(false);}
    };
    void request();
    return()=>{alive=false;};
  },[base,backendConnected,projectId,activeAnalysisId,projectRevision,project?.geometry]);

  const selected=useMemo(()=>proposals.find(item=>item.id===selectedId)??null,[proposals,selectedId]);
  const validation=validity(inputs);
  const totalReserve=inputs.roads_pct+inputs.open_space_pct+inputs.facilities_pct+inputs.other_reserve_pct;
  const netPct=Math.max(0,100-totalReserve);
  const plotHa=inputs.units*inputs.lot_width_m*inputs.lot_depth_m/10000;
  const requiredHa=netPct>0?plotHa/(netPct/100):NaN;
  const parcelHa=project?.site_area_ha??0;
  const grossDifference=parcelHa-requiredHa;
  const density=parcelHa>0?inputs.units/parcelHa:NaN;
  const isDirty=selected!==null&&JSON.stringify(selected.inputs)!==JSON.stringify(inputs);
  const savedScreening=!isDirty?selected?.result:null;

  function resetNew(){
    setSelectedId(null);
    setInputs({...DEFAULT_PROPOSAL,name:"Option "+String.fromCharCode(65+Math.min(proposals.length,25))+" - 300 mid terrace lots (20 x 70 ft)"});
    setError("");setNotice("New draft. Edit assumptions and save it as a project scenario.");
  }
  function select(item:SavedProposal){
    setSelectedId(item.id);setInputs({...item.inputs});setError("");setNotice("");
  }
  function inputNumber(key:keyof ProposalInputs,value:string){
    setInputs(p=>({...p,[key]:value===""?0:Number(value)}));
  }
  async function save(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    if(!project||!backendConnected||validation||busy)return;
    setBusy(true);setError("");setNotice("");
    try{
      const changed=selected!==null;
      const response=await api<SavedProposal>(changed?base+"/"+encodeURIComponent(selected.id):base,{
        method:changed?"PUT":"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(changed?{expected_revision:selected.revision,proposal:inputs}:inputs),
      });
      await load();
      setSelectedId(response.id);
      setNotice(changed?"Scenario updated against the current project and GIS context.":"Scenario saved to this project's SQLite database.");
    }catch(e){setError(e instanceof Error?e.message:"Unable to save scenario.");}
    finally{setBusy(false);}
  }
  async function remove(){
    if(!selected||!project||!backendConnected||busy)return;
    if(!window.confirm('Delete "'+selected.inputs.name+'" from this project?'))return;
    setBusy(true);setError("");setNotice("");
    try{
      await api<void>(base+"/"+encodeURIComponent(selected.id),{method:"DELETE"});
      await load();setSelectedId(null);setInputs({...DEFAULT_PROPOSAL});
      setNotice("Scenario removed. Other project analyses and scenarios were not changed.");
    }catch(e){setError(e instanceof Error?e.message:"Unable to delete scenario.");}
    finally{setBusy(false);}
  }

  return <section className="proposal-studio" aria-label="Development Proposal Studio">
    <div className="proposal-head">
      <div>
        <div className="eyebrow"><span className="eyebrow-dot"/> PHASE 05 <span className="eyebrow-slash">//</span> MODULE 002</div>
        <h1>Development <span className="h1-accent">Studio</span><span className="hero-title-mark">/</span></h1>
        <p>Translate proposed unit counts and lot dimensions into an auditable land budget. Compare only against measured terrain screening, never invented planning permission.</p>
      </div>
      <span className="proposal-local-chip"><ShieldCheck size={15}/> LOCAL WORKSPACE · ASSUMPTIONS ONLY</span>
    </div>
    {!project||!project.geometry?<div className="proposal-empty">
      <div className="proposal-empty-icon"><MapPin size={29}/></div>
      <div><strong>Start with a saved project boundary</strong><p>Create or open a project, then draw or import its site polygon. A scenario cannot be associated with land that has not been defined.</p></div>
      <button type="button" className="btn btn-accent" onClick={onOpenProjects}><Database size={17}/> Open Project Workspace <ArrowRight size={16}/></button>
    </div>:<>
      <div className="proposal-context">
        <div className="proposal-context-icon"><Building2 size={23}/></div>
        <div className="proposal-context-copy"><small>PROJECT / AUTHORITATIVE LOCAL RECORD</small>
          <strong>{project.name}</strong>
          <span>Site area ≈ {decimal(project.site_area_ha)} ha · {activeAnalysisId?"Terrain report connected":"Terrain analysis not run yet"}</span>
        </div>
        <span className={"proposal-context-state "+(activeAnalysisId?"is-linked":"")}>{activeAnalysisId?"GIS LINKED":"AREA-ONLY MODE"}</span>
      </div>
      {!backendConnected&&<div className="proposal-alert" role="alert"><CircleAlert size={17}/> Backend offline. Scenarios cannot be saved until FastAPI is running locally.</div>}
      {error&&<div className="proposal-alert" role="alert"><CircleAlert size={17}/>{error}</div>}
      {notice&&<div className="proposal-success" role="status"><CheckCircle2 size={17}/>{notice}</div>}
      <div className="proposal-layout">
        <form className="proposal-editor" onSubmit={event=>{void save(event);}}>
          <div className="proposal-section-title"><div><span className="section-overline">01 / USER-DEFINED INPUTS</span><h2>Configure development</h2></div><ClipboardList size={21}/></div>
          <p className="proposal-editor-intro">The values below are <strong>illustrative defaults you can edit</strong>. Default: Mid terrace 20 × 70 ft (a real-world design example, NOT the national GPP minimum). Select Low, Mid or High in the GPP panel. All dimensions and land reserves are editable user assumptions, never planning approval.</p>
          <label className="proposal-field proposal-field-wide">Scenario name
            <input value={inputs.name} type="text" minLength={3} maxLength={100} required
              onChange={event=>setInputs(p=>({...p,name:event.target.value}))} placeholder="e.g. 300 terrace units - option A"/>
          </label>
          <label className="proposal-field proposal-field-wide">Landed development category
            <select value={inputs.development_type} onChange={event=>setInputs(p=>({...p,development_type:event.target.value as ProposalInputs["development_type"],housing_category:null,perak_market_segment:null}))}>
              <option value="terrace_housing">Terrace / landed housing lots</option>
              <option value="shoplots">Commercial shoplots</option>
              <option value="other_landed">Other individual landed lots</option>
            </select>
          </label>
          <div className="proposal-input-grid">
            <label className="proposal-field">Proposed units / lots
              <input inputMode="numeric" type="number" min={1} max={100000} step={1} required value={inputs.units}
                onChange={event=>inputNumber("units",event.target.value)}/>
            </label>
            <div className="proposal-inline-hint">Unit count refers to individual ground-level lots, not apartments, floors or building GFA.</div>
            <label className="proposal-field">Lot frontage (m)
              <input type="number" min="0.01" max="150" step="any" required value={inputs.lot_width_m}
                onChange={event=>inputNumber("lot_width_m",event.target.value)}/>
            </label>
            <label className="proposal-field">Lot depth (m)
              <input type="number" min="0.01" max="300" step="any" required value={inputs.lot_depth_m}
                onChange={event=>inputNumber("lot_depth_m",event.target.value)}/>
            </label>
          </div>
          <div className="proposal-section-divider"/>
          <GppCheckPanel inputs={inputs} onPatch={patch=>setInputs(current=>({...current,...patch}))}
            backendConnected={backendConnected} savedAssessment={selected?.result.policy_assessment}
            isDirty={isDirty} />
          <div className="proposal-section-divider"/>
          <div className="proposal-section-title proposal-allocation-head">
            <div><span className="section-overline">02 / LAND ALLOCATION</span><h2>Reserve assumptions</h2></div>
            <span className="proposal-percent-pill">{decimal(totalReserve,1)}% reserved</span>
          </div>
          <p className="proposal-editor-intro">Each value is a percentage of the <strong>gross land required</strong>. Do not add the same road, reserve or open-space area twice.</p>
          <div className="proposal-allocation-fields">
            {allocationFields.map(item=><label className="proposal-field" key={item.key}>
              <span className="proposal-field-dot"><i style={{backgroundColor:item.color}}/>{item.name}</span>
              <div className="proposal-percent-input"><input type="number" min="0" max="70" step="any"
                value={inputs[item.key]} onChange={event=>inputNumber(item.key,event.target.value)} required/><span>%</span></div>
            </label>)}
          </div>
          <div className="proposal-percent-bar" role="img" aria-label={"Net plots "+decimal(netPct,1)+" percent; reserves "+decimal(totalReserve,1)+" percent"}>
            <span style={{width:netPct+"%",backgroundColor:"#b4f77d"}}/>
            {allocationFields.map(item=><span key={item.key} style={{width:Math.max(0,inputs[item.key])+"%",backgroundColor:item.color}}/>)}
          </div>
          <div className="proposal-net-label"><span>Net plot share <strong>{decimal(netPct,1)}%</strong></span><span>Total reserve <strong>{decimal(totalReserve,1)}%</strong></span></div>
          {validation&&<div className="proposal-validation" role="alert"><CircleAlert size={15}/>{validation}</div>}
          <div className="proposal-form-actions">
            <button type="button" className="btn btn-subtle" onClick={resetNew} disabled={busy}><FilePlus2 size={16}/> New option</button>
            <button type="submit" className="btn btn-accent" disabled={busy||loading||!backendConnected||Boolean(validation)}>
              {busy?<LoaderCircle size={16} className="spin"/>:<Save size={16}/>}
              {selected?"Update scenario":"Save scenario"} <ArrowRight size={15}/>
            </button>
          </div>
          {selected&&<div className="proposal-secondary-actions">
            <span>{selected.context_changed?"Current site/DEM changed; updating will rebind this scenario.":isDirty?"Unsaved edits — save to update the official worksheet.":"Saved revision "+selected.revision}</span>
            <button type="button" onClick={()=>{void remove();}} disabled={busy} aria-label={"Delete scenario "+selected.inputs.name}><Trash2 size={14}/> Delete scenario</button>
          </div>}
        </form>
        <div className="proposal-insight">
          <div className="proposal-section-title"><div><span className="section-overline">03 / LIVE MATHEMATICAL ESTIMATE</span><h2>Land budget intelligence</h2></div><Calculator size={22}/></div>
          <div className="proposal-hero-number"><small>REQUIRED GROSS LAND · USER ASSUMPTIONS</small>
            <strong>{validation?"—":decimal(requiredHa,3)} <em>ha</em></strong>
            <p>Formula: units × frontage × depth ÷ 10,000 ÷ net plot share. No GIS claim is made from this arithmetic alone.</p>
          </div>
          <div className="proposal-result-grid">
            <div><small>Building plot area</small><strong>{validation?"—":decimal(plotHa)} ha</strong></div>
            <div><small>Site gross area</small><strong>{decimal(parcelHa)} ha</strong></div>
            <div><small>Gross arithmetic margin</small><strong className={!validation&&grossDifference<0?"shortfall":""}>{validation?"—":decimal(grossDifference)} ha</strong></div>
            <div><small>Proposed gross density</small><strong>{validation?"—":decimal(density,3)} <small>units / ha</small></strong></div>
          </div>
          {!validation&&<div className={"proposal-area-banner "+(grossDifference<0?"area-deficit":"")}>
            {grossDifference<0?<CircleAlert size={18}/>:<CheckCircle2 size={18}/>}
            <div><strong>{grossDifference<0?"Gross land requirement exceeds site area":"Gross land arithmetic is within site area"}</strong>
              <span>{grossDifference<0?"The input requires more total land than the current polygon.":"This does not prove the proposed plots can fit into an actual compliant layout."}</span></div>
          </div>}
          <div className="proposal-lineitems">
            <div className="proposal-lineitems-heading"><strong>Illustrative land allocation</strong><span>Based on required gross ha</span></div>
            <div><span>Building lots</span><strong>{validation?"—":decimal(plotHa)} ha</strong></div>
            {allocationFields.map(item=><div key={item.key}><span>{item.name}</span><strong>{validation?"—":decimal(requiredHa*inputs[item.key]/100)} ha</strong></div>)}
          </div>
          <div className="proposal-gis-evidence">
            <div className="proposal-gis-head"><Layers3 size={18}/><strong>Measured terrain comparison</strong></div>
            {!selected||isDirty?<p>Save this proposal to obtain an auditable comparison against the active project's measured Suitability layer. The live numbers above use only your typed assumptions.</p>:
              selected.context_changed?<p className="proposal-warning"><CircleAlert size={16}/> Site boundary or GIS analysis changed since this scenario was saved. Review and use "Update scenario" to recalculate against the current evidence.</p>:
              savedScreening?.screening_status==="no_active_analysis"||savedScreening?.screening_status==="no_suitability_layer"?<p>There is no current verified suitability analysis for this scenario. Run terrain analysis and update this scenario. No slope-based area is inferred.</p>:
              <>
                <div className="proposal-gis-stat"><span>Lower-constraint measured cells (capped)</span><strong>{decimal(savedScreening?.lower_constraint_cell_area_ha_est)} ha</strong></div>
                <div className="proposal-gis-stat"><span>Gross requirement vs cell-area margin</span><strong>{decimal(savedScreening?.lower_constraint_area_margin_ha_est)} ha</strong></div>
                <p className={savedScreening?.screening_status==="quality_limited"?"proposal-warning":""}>{savedScreening?.conclusion}</p>
              </>}
            <div className="proposal-gis-disclaimer"><ShieldCheck size={17}/> Lower-slope cells are NOT proven contiguous, accessible, permitted, geotechnically sound or developable. GPP numeric references are supplementary only; adopted PBT/RT requirements, drainage and engineering checks remain outstanding.</div>
          </div>
        </div>
      </div>
      <section className="proposal-saved" aria-label="Saved development scenarios">
        <div className="proposal-section-title"><div><span className="section-overline">04 / SAVED OPTIONS</span>
          <h2>Project scenario register <small>({proposals.length})</small></h2>
        </div><ChartNoAxesCombined size={23}/></div>
        {loading?<div className="proposal-loading"><LoaderCircle size={18} className="spin"/> Loading local project scenarios…</div>:
          proposals.length===0?<div className="proposal-no-scenarios"><Database size={27}/><strong>No scenario saved yet</strong><p>Save your first option to compare gross land demand, road allocation and current GIS screening.</p></div>:
          <div className="proposal-scenario-list">
            {proposals.map(item=><button type="button" key={item.id}
              className={"proposal-scenario "+(item.id===selectedId?"is-active":"")}
              onClick={()=>select(item)} aria-pressed={item.id===selectedId}>
              <div className="proposal-scenario-top"><span>{DEVELOPMENT_LABELS[item.inputs.development_type]}</span>
                {item.context_changed?<span className="proposal-scenario-stale"><RotateCcw size={12}/> REVIEW GIS</span>:item.policy_review_needed?<span className="proposal-scenario-stale"><RotateCcw size={12}/> REVIEW GPP</span>:
                  <span className="proposal-scenario-saved"><CheckCircle2 size={12}/> SAVED</span>}</div>
              <strong>{item.inputs.name}</strong>
              <div className="proposal-scenario-metrics"><span><b>{item.inputs.units.toLocaleString("en-MY")}</b> plots</span>
                <span><b>{decimal(item.result.required_gross_area_ha,3)}</b> ha gross</span>
                <span><b>{decimal(item.result.gross_site_density_units_per_ha,3)}</b> units/ha</span></div>
              <small>{item.context_changed?"Tapak atau analisis telah berubah; semak semula cadangan.":item.policy_review_needed?"GPP registry changed; review the official source pages before re-saving.":item.result.screening_status==="indicative_cell_area_only"?"Comparison based on preliminary slope cells.":item.result.screening_status==="quality_limited"?"GIS quality limited; further checks required.":"Land budget only; GIS conclusions unavailable."}</small>
            </button>)}
          </div>}
      </section>
      <div className="proposal-footnote"><CircleAlert size={17}/>
        <p><strong>Professional limitation:</strong> This module does not calculate approved density or a feasible site layout. Lot, road and reserve inputs are illustrative and user-defined; statutory requirements must be checked with the relevant PBT/PLANMalaysia documents. No apartments, multiple floors or GFA modelling is provided in this module.</p>
      </div>
    </>}
  </section>;
}
