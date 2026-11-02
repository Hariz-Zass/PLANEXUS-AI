"use client";

import { useEffect, useState } from "react";
import { ArrowRight, ArrowUpRight, BookMarked, BookOpen, CheckCircle2, CircleAlert, Database, FileSearch, LoaderCircle, ShieldCheck } from "lucide-react";
import { api, type PolicyCatalog } from "@/lib/api";

export default function GppLibrary({backendConnected,onOpenStudio}:{backendConnected:boolean;onOpenStudio:()=>void}){
  const [catalog,setCatalog]=useState<PolicyCatalog|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  useEffect(()=>{
    if(!backendConnected){setCatalog(null);return;}
    let active=true;setLoading(true);
    const load=async()=>{
      try{
        const data=await api<PolicyCatalog>("/api/policy/catalog");
        if(active)setCatalog(data);
      }catch(e){if(active)setError(e instanceof Error?e.message:"GPP sources cannot be loaded.");}
      finally{if(active)setLoading(false);}
    };
    void load();
    return()=>{active=false;};
  },[backendConnected]);
  const curated=catalog?.sources.filter(item=>item.status==="curated_rules").length??0;
  const pending=catalog?.sources.filter(item=>item.status==="catalog_only").length??0;
  return <section className="gpp-library" aria-label="GPP official policy knowledge registry">
    <div className="eyebrow"><span className="eyebrow-dot"/> POLICY INTELLIGENCE <span className="eyebrow-slash">//</span> GPP REFERENCE SYSTEM</div>
    <h1>GPP <span className="h1-accent">Knowledge Registry</span><span className="hero-title-mark">/</span></h1>
    <p>Official planning guideline sources and machine-readable rules — with jurisdiction, publication year, evidence page and explicit indexing status. PLANEXUS does not claim to have imported every GPP.</p>
    {loading&&<div className="proposal-loading"><LoaderCircle className="spin" size={18}/> Loading source registry…</div>}
    {!backendConnected&&<div className="proposal-alert"><CircleAlert size={17}/> Local GIS backend offline. Start FastAPI to load the official GPP registry.</div>}
    {error&&<div className="proposal-alert" role="alert"><CircleAlert size={17}/>{error}</div>}
    {catalog&&<>
      <div className="gpp-library-summary">
        <div><small>NUMERICALLY INDEXED SOURCE DOCUMENTS</small><strong>{curated}</strong></div>
        <div><small>CATALOGUED, NOT YET DIGITIZED</small><strong>{pending}</strong></div>
        <div><small>EXPLICIT NATIONAL LOT RULE ROWS</small><strong>{catalog.national_lot_rules.length}</strong></div>
      </div>
      <div className="project-storage-status" style={{marginBottom:20}}>
        <div className="project-storage-icon"><ShieldCheck size={20}/></div>
        <div><strong>Planning evidence layers are jurisdiction-aware</strong>
          <span>National GP001-A (2016) gives housing lot-size minima. Perak Housing 2023 adds PR1–PR6 floor-space and storey limits for terrace, semi-detached, cluster, detached, zero-lot and townhouse categories. PBT adoption, RT zoning and all uncatalogued amendments still require verification.</span>
        </div>
        <span className="project-storage-local">VERSIONED</span>
      </div>
      {catalog.sources.map(source=><article key={source.id} className="gpp-library-source">
        <div className="gpp-library-source-icon">{source.status==="curated_rules"?<BookMarked size={22}/>:<BookOpen size={22}/>}</div>
        <div className="gpp-library-source-content">
          <div className="gpp-library-source-top">
            <h3>{source.title}</h3>
            <span className={"gpp-library-source-status"+(source.status==="curated_rules"?" is-curated":"")}>
              {source.status==="curated_rules"?"RULES INDEXED":"SOURCE ONLY"}
            </span>
          </div>
          <p>{source.issuer} · {source.year??"Year requires document verification"} · {source.jurisdiction}</p>
          <p>{source.scope}</p>
          <small>Evidence locator: {source.evidence}</small>
          <div><a href={source.url} target="_blank" rel="noopener noreferrer"><FileSearch size={14}/> Open official document/source <ArrowUpRight size={14}/></a></div>
        </div>
      </article>)}
      <div className="gpp-library-caveat"><CircleAlert size={18}/>
        <span>{catalog.disclaimer} Every numeric check is a reference comparison only; where no valid maximum has been indexed, the system MUST leave it unknown.</span>
      </div>
      <div className="project-actions" style={{marginTop:18,justifyContent:"flex-start"}}>
        <button className="btn btn-accent" onClick={onOpenStudio}><Database size={16}/> Check a project against GPP <ArrowRight size={14}/></button>
      </div>
    </>}
  </section>;
}
