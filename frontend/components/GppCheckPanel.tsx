"use client";
import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, BookOpen, CheckCircle2, CircleAlert, FileSearch, LoaderCircle, Ruler, ShieldCheck } from "lucide-react";
import { api, type PolicyAssessment, type PolicyCatalog, type ProposalInputs } from "@/lib/api";

type Props={
  inputs:ProposalInputs;
  onPatch:(patch:Partial<ProposalInputs>)=>void;
  backendConnected:boolean;
  savedAssessment?:PolicyAssessment|null;
  isDirty:boolean;
};

function fmt(n:number|null|undefined){
  return n===null||n===undefined?"—":Number(n.toFixed(4)).toLocaleString("en-MY",{maximumFractionDigits:4});
}

export default function GppCheckPanel({inputs,onPatch,backendConnected,savedAssessment,isDirty}:Props){
  const [catalog,setCatalog]=useState<PolicyCatalog|null>(null);
  const [error,setError]=useState("");
  const [checking,setChecking]=useState(false);
  const [preview,setPreview]=useState<{key:string;result:PolicyAssessment}|null>(null);
  const [loading,setLoading]=useState(false);
  const currentKey=JSON.stringify(inputs);
  const assessment=preview?.key===currentKey?preview.result:(!isDirty?savedAssessment:null);
  const isHousing=inputs.development_type!=="shoplots";
  const category=inputs.housing_category??"";
  const storeys=inputs.storeys??null;
  const profile=inputs.policy_profile??"none";
  const matches=useMemo(
    ()=>catalog?.housing_categories.filter(item=>item.development_type===inputs.development_type)??[],
    [catalog,inputs.development_type],
  );
  const lotRule=useMemo(
    ()=>catalog?.national_lot_rules.find(item=>item.category===category&&storeys!==null&&item.storeys.includes(storeys)),
    [catalog,category,storeys],
  );

  useEffect(()=>{
    if(!backendConnected){setCatalog(null);return;}
    let active=true;setLoading(true);
    const fetchCatalog=async()=>{
      try{
        const result=await api<PolicyCatalog>("/api/policy/catalog");
        if(active)setCatalog(result);
      }catch(e){if(active)setError(e instanceof Error?e.message:"Cannot load the official GPP index.");}
      finally{if(active)setLoading(false);}
    };
    void fetchCatalog();
    return()=>{active=false;};
  },[backendConnected]);

  async function check(){
    if(!backendConnected||checking)return;
    setChecking(true);setError("");
    const key=JSON.stringify(inputs);
    try{
      const result=await api<PolicyAssessment>("/api/policy/assess",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(inputs),
      });
      setPreview({key,result});
    }catch(e){setError(e instanceof Error?e.message:"GPP assessment is unavailable.");}
    finally{setChecking(false);}
  }

  return <section className="gpp-check" aria-label="GPP housing reference checks">
    <div className="gpp-title-row"><div><span className="section-overline"><BookOpen size={13}/> 01B / VERIFIED PLANNING GUIDANCE</span>
      <h3>GPP <em>Knowledge Engine</em></h3>
      <p>Source-cited numerical guidance — not an automatic PBT approval.</p>
    </div><span className="gpp-version">{catalog?"REGISTRY "+catalog.registry_version:"SOURCE REGISTER"}</span></div>
    <label className="proposal-field proposal-field-wide">GPP / jurisdiction selection
      <select aria-label="GPP jurisdiction" value={profile}
        onChange={event=>onPatch({policy_profile:event.target.value as ProposalInputs["policy_profile"]})}>
        <option value="none">Belum pilih negeri / PBT</option>
        <option value="national_2016">PLANMalaysia GP001-A 2016 (national reference)</option>
        <option value="perak_2023">Perak 2023 (state rules + national reference)</option>
      </select>
    </label>
    {profile==="none"&&<p className="gpp-notice"><CircleAlert size={15}/> Select a jurisdiction to see guidelines. The site map coordinates do not prove which current PBT rules apply.</p>}
    {isHousing&&<>
      <div className="gpp-field-grid">
        <label className="proposal-field">Housing type in GP001-A
          <select aria-label="GPP house category" value={category} onChange={event=>onPatch({housing_category:event.target.value as ProposalInputs["housing_category"]||null})}>
            <option value="">Choose housing category</option>
            {matches.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </label>
        <label className="proposal-field">Number of storeys
          <select aria-label="GPP number of storeys" value={storeys??""} onChange={event=>onPatch({storeys:event.target.value?Number(event.target.value):null})}>
            <option value="">Choose floor count</option>
            {Array.from({length:5},(_,i)=>i+1).map(n=><option key={n} value={n}>{n} {n===1?"storey":"storeys"}</option>)}
          </select>
        </label>
      </div>
      {profile==="perak_2023"&&inputs.development_type==="terrace_housing"&&
        <label className="proposal-field proposal-field-wide">Perak 2023: category of housing cost
          <select aria-label="Perak housing segment" value={inputs.perak_market_segment??""}
            onChange={event=>onPatch({perak_market_segment:event.target.value as ProposalInputs["perak_market_segment"]||null})}>
            <option value="">Choose Perak price / cost class</option>
            {catalog?.perak_market_segments.map(item=><option key={item.id} value={item.id}>{item.label} — floor min {catalog.perak_floor_min_sqft[item.id]} sq ft</option>)}
          </select>
        </label>}
      <div className="gpp-field-grid gpp-other-fields">
        <label className="proposal-field">Proposed floor area (m²)
          <input aria-label="GPP proposed floor area" type="number" step="any" min=".01" max="100000"
            value={inputs.floor_area_m2??""} placeholder="Not supplied"
            onChange={event=>onPatch({floor_area_m2:event.target.value?Number(event.target.value):null})}/>
        </label>
        {profile==="perak_2023"&&inputs.development_type==="terrace_housing"&&<label className="proposal-field">Bedrooms
          <input aria-label="GPP bedrooms" type="number" step="1" min="0" max="50"
            value={inputs.bedrooms??""} placeholder="Not supplied"
            onChange={event=>onPatch({bedrooms:event.target.value?Number(event.target.value):null})}/>
        </label>}
        {profile==="perak_2023"&&inputs.development_type==="terrace_housing"&&<label className="proposal-field">Building height (m, ground to roof)
          <input aria-label="GPP building height" type="number" step="any" min=".01" max="300"
            value={inputs.building_height_m??""} placeholder="Not supplied"
            onChange={event=>onPatch({building_height_m:event.target.value?Number(event.target.value):null})}/>
        </label>}
      </div>
      {lotRule&&<div className="gpp-suggestion">
        <div><Ruler size={17}/><span><strong>Jadual 2 GP001-A: minimum lot reference</strong>
          <small>{lotRule.label} — {fmt(lotRule.min_width_m)} × {fmt(lotRule.min_depth_m)} m. No maximum lot size specified in indexed table.</small></span>
        </div>
        <button type="button" disabled={checking} onClick={()=>onPatch({
          lot_width_m:lotRule.min_width_m,lot_depth_m:lotRule.min_depth_m,
        })}>Use reference dimensions</button>
      </div>}
      {profile==="perak_2023"&&<p className="gpp-notice"><CircleAlert size={15}/>
        Perak PR1 sets terrace floor-space/height rules; GP001-A lot dimensions are <strong>supplementary national references</strong>. Verify adopted PBT and gazetted local-plan provisions before any compliance claim.
      </p>}
      {profile==="perak_2023"&&inputs.development_type==="terrace_housing"&&Boolean(catalog?.perak_layout_references?.length)&&<div className="gpp-manual-layout">
        <div className="gpp-manual-layout-head">
          <strong>Perak PR1 — rujukan geometri jalan / anjakan</strong>
          <span>NOT AUTOMATICALLY CHECKED</span>
        </div>
        <p>Peraturan ini memerlukan pelan susun atur yang boleh diukur. PLANEXUS hanya menyenaraikan angka dalam PR1; ia belum menilai jarak jalan, blok atau anjakan pada peta.</p>
        <div className="gpp-layout-list">
          {catalog?.perak_layout_references?.map(rule=><div key={rule.id}>
            <span>{rule.label}<small>{rule.applicability}</small></span>
            <strong>{rule.value_type==="minimum"?"Min ":rule.value_type==="maximum"?"Max ":"Rujukan "}
              {rule.value_ft}′{rule.value_type==="stated_square"?" × "+rule.value_ft+"′":""}
            </strong>
          </div>)}
        </div>
        <a target="_blank" rel="noopener noreferrer" href={catalog.sources.find(s=>s.id==="perak_housing_2023")?.url||"https://lphp.gov.my/index.php/pekeliling-lphp/35-gp-piawaian-perumahan-negeri-perak-2023-1/file"}>Buka PDF PR1 negeri Perak <ArrowUpRight size={14}/></a>
      </div>}

    </>}
    {inputs.development_type==="shoplots"&&profile!=="none"&&
      <p className="gpp-notice"><CircleAlert size={15}/> Commercial shoplot GPP is listed in the source catalog but its numerical dimensions have NOT been indexed. Residential minima cannot be reused for shoplots.</p>}
    {loading&&<p className="gpp-notice"><LoaderCircle size={15} className="spin"/> Loading verified document register…</p>}
    {error&&<p className="gpp-policy-error" role="alert"><CircleAlert size={15}/>{error}</p>}
    <div className="gpp-action">
      <span><ShieldCheck size={15}/> Only manually checked clauses and pages are compared</span>
      <button type="button" disabled={!backendConnected||checking||profile==="none"}
        onClick={()=>{void check();}}><FileSearch size={16}/>{checking?"Checking…":"Semak GPP"} <ArrowUpRight size={14}/></button>
    </div>
    {assessment&&<div className="gpp-results">
      <div className="gpp-result-heading">
        <strong>Reference check: {assessment.profile_label}</strong>
        <span className={assessment.status==="outside_numeric_reference"?"gpp-result-warning":"gpp-result-neutral"}>
          {assessment.status==="outside_numeric_reference"?"BELOW / ABOVE NUMERIC LIMIT":
           assessment.status==="numeric_reference_only"?"NUMERIC REFERENCE MET · NOT APPROVAL":
           assessment.status==="not_indexed"?"SOURCE NOT INDEXED":"REFERENCE / REVIEW REQUIRED"}
        </span>
      </div>
      {assessment.checks.map((item,i)=><div key={item.key+"-"+i} className="gpp-check-line">
        <div><strong>{item.title}</strong><small>{item.role==="supplementary_national_reference"?"NATIONAL REFERENCE ONLY":"MANUALLY CURATED SOURCE RULE"} · {item.source_page}</small></div>
        <div className="gpp-check-value">
          <span>{item.type==="min"?"Min ":"Max "}{fmt(item.value)} {item.unit}</span>
          <strong className={item.result==="below_min"||item.result==="above_max"?"gpp-check-failed":""}>
            {item.observed===null?"Input required":item.result==="meets_number"?"Numeric match":"Outside range"}
          </strong>
        </div>
        <a target="_blank" rel="noopener noreferrer" href={item.source_url} title={"Open "+item.source_title} aria-label={"Source for "+item.title}><ArrowUpRight size={16}/></a>
      </div>)}
      {!assessment.checks.length&&<p className="gpp-empty-check">{assessment.message}</p>}
      <p className="gpp-warning-bottom"><CircleAlert size={15}/> {assessment.message}</p>
    </div>}
    <div className="gpp-source-foot">
      <span>Sources: PLANMalaysia GP001-A (2016), Perak PR1 (2023). Full GPP library is not yet indexed.</span>
      <a target="_blank" rel="noopener noreferrer" href="https://www.planmalaysia.gov.my/main/garis-panduan-perancangan">Official PLANMalaysia index <ArrowUpRight size={13}/></a>
    </div>
  </section>;
}
