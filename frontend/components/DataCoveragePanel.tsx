"use client";
import {useEffect,useState} from "react";
import {AlertTriangle, Database, ExternalLink, ShieldCheck, LoaderCircle} from "lucide-react";
import {api} from "@/lib/api";

type Module={id:string;name:string;implementation:string;data_status:string;limits:string};
type Source={id:string;title:string;status:string;url:string;evidence:string};
type Portal={name:string;url:string;reuse:string};
type Ledger={
 version:string;modules:Module[];numeric_policy_documents:number;
 catalogue_only_policy_documents:number;policy_sources:Source[];
 official_portals:Portal[];not_a_complete_data_claim:boolean;
 ai_generative_configured:boolean;
};

const ready=(m:Module)=>!m.implementation.startsWith("NOT_")&&m.implementation!=="manual_road_sketch_only";
const title=(m:Module)=>m.implementation.startsWith("NOT_")?"BELUM DISAMBUNG":
 m.implementation.includes("partially")?"LIPUTAN TERHAD":
 m.implementation.includes("on_demand")?"DATA KOMUNITI":
 m.implementation.includes("manual")?"INPUT MANUAL":"ENJIN TERSEDIA";

export default function DataCoveragePanel({backendConnected}:{backendConnected:boolean}){
 const [ledger,setLedger]=useState<Ledger|null>(null);
 const [error,setError]=useState("");
 useEffect(()=>{
   let mounted=true;
   if(!backendConnected){setLedger(null);return;}
   void api<Ledger>("/api/capabilities/data").then(v=>{if(mounted)setLedger(v);}).catch(e=>{
     if(mounted)setError(e instanceof Error?e.message:"Tidak dapat menyemak liputan data.");});
   return()=>{mounted=false;};
 },[backendConnected]);
 return <section className="source-audit-page" aria-label="Actual source and module readiness">
   <div className="eyebrow"><span className="eyebrow-dot"/> DATA TRUST & FUNCTION COVERAGE</div>
   <h1>Source Readiness <span className="h1-accent">.</span></h1>
   <p className="source-audit-lead">Status setiap modul diambil daripada daftar kemampuan backend. “Enjin tersedia” bukan bererti ada data rasmi bagi setiap lot. Data tiada tidak digantikan dengan angka rekaan.</p>
   {!backendConnected?<div className="source-audit-alert"><AlertTriangle size={17}/> Backend tidak bersambung. Tiada sumber live yang boleh disahkan sekarang.</div>:
    !ledger?<div className="source-audit-alert"><LoaderCircle size={16} className="spin"/> Menyemak status sumber… {error}</div>:
    <>
      <div className="source-audit-summary"><div><small>GPP dengan peraturan berangka dikurasi</small><strong>{ledger.numeric_policy_documents}</strong></div>
      <div><small>GPP hanya katalog (tiada aturan berangka)</small><strong>{ledger.catalogue_only_policy_documents}</strong></div>
      <div><small>Modul belum bersambung sepenuhnya</small><strong>{ledger.modules.filter(m=>m.implementation==="NOT_INTEGRATED").length}</strong></div></div>
      <div className="source-audit-grid">{ledger.modules.map(m=>
        <article key={m.id}>
          <div><Database size={15}/><strong>{m.name}</strong>
            <span className={ready(m)?"source-status-ready":"source-status-missing"}>{title(m)}</span></div>
          <p>{m.limits}</p><small>{m.data_status.replaceAll("_"," ")}</small>
        </article>)}</div>
      <h2><ShieldCheck size={18}/> Senarai dokumen GPP</h2>
      <div className="source-audit-docs">{ledger.policy_sources.map(doc=><div key={doc.id}>
        <div><strong>{doc.title}</strong><small>{doc.evidence}</small></div>
        <span>{doc.status==="curated_rules"?"ANGKA DIINDEKS":"RUJUKAN SAHAJA"}</span>
        <a href={doc.url} target="_blank" rel="noopener noreferrer">Sumber <ExternalLink size={12}/></a>
      </div>)}</div>
      <h2>Portal rasmi yang boleh dirujuk — bukan data yang telah diintegrasi</h2>
      <div className="source-audit-docs">{ledger.official_portals.map(source=><div key={source.url}>
        <div><strong>{source.name}</strong><small>{source.reuse}</small></div>
        <a href={source.url} target="_blank" rel="noopener noreferrer">Portal <ExternalLink size={12}/></a>
      </div>)}</div>
      <p className="source-audit-alert"><AlertTriangle size={17}/> Zoning, RT/RTD, hak milik, status banjir tapak dan akses jalan sah belum boleh dijawab secara automatik sebagai fakta rasmi. Lesen data dan versi pewartaan mesti dipenuhi terlebih dahulu.</p>
    </>}
 </section>;
}
