"use client";
import {useEffect,useMemo,useState} from "react";
import {CircleAlert, Compass, ExternalLink, LoaderCircle, RefreshCw, ShieldCheck} from "lucide-react";
import {api, type ProjectDetail} from "@/lib/api";

type NamedPlace={
  name:string;category:string;distance_from_reference_point_m:number;
  osm_url:string;osm_feature_id:string;
};
type SiteContext={
  status:"retrieved";source_id:string;source_name:string;source_url:string;licence:string;
  retrieved_at_utc:string;source_quality:string;radius_m:number;
  counts:Record<string,number>;named_places:NamedPlace[];
  returned_feature_count:number;warnings:string[];
};
type Response={exists:boolean;reason?:string;context?:SiteContext};
const labels:Record<string,string>={
  education:"Pendidikan",healthcare:"Kesihatan",transport:"Pengangkutan",
  retail:"Runcit / mall",parks:"Taman / rekreasi",civic:"Perkhidmatan awam",
  roads:"Segmen jalan OSM",waterways:"Segmen aliran / sungai OSM"
};

export default function SiteContextPanel({
  project,backendConnected
}: {project:ProjectDetail|null;backendConnected:boolean}) {
  const [result,setResult]=useState<Response|null>(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const identifier=project?.id??null;
  const boundaryRevision=project?.revision??0;
  useEffect(()=>{
    let active=true;
    setResult(null);setError("");
    if(!identifier||!project?.geometry||!backendConnected)return;
    void api<Response>("/api/projects/"+identifier+"/context").then(value=>{
      if(active)setResult(value);
    }).catch(e=>{if(active)setError(e instanceof Error?e.message:"Gagal membaca carian sekitar yang disimpan.");});
    return()=>{active=false;};
  },[identifier,boundaryRevision,Boolean(project?.geometry),backendConnected]);

  const values=useMemo(()=>Object.entries(result?.context?.counts??{}),[result]);
  async function refresh(){
    if(!identifier||!project?.geometry||busy)return;
    setBusy(true);setError("");
    try{
      const data=await api<Response>("/api/projects/"+identifier+"/context/refresh",{method:"POST"});
      setResult(data);
    }catch(e){
      setError(e instanceof Error?e.message:"OSM tidak dapat diakses. Tiada hasil contoh dipaparkan.");
    }finally{setBusy(false);}
  }

  return <section className="site-evidence-panel" role="region" aria-label="Automatically sourced nearby site evidence">
    <div className="site-evidence-head">
      <div><span className="section-overline"><Compass size={14}/> DATA SEKITAR TAPAK</span>
        <h2>Nearby Evidence <em>Discovery</em></h2>
        <p>Carian kemudahan, rangkaian jalan dan aliran air daripada data terbuka sebenar, bukan senarai yang direka.</p>
      </div>
      <span className="site-evidence-source-state">OSM COMMUNITY DATA · NOT OFFICIAL</span>
    </div>
    <div className="site-evidence-actions">
      <button type="button" className="btn btn-primary"
        onClick={()=>void refresh()} disabled={!project?.geometry||!backendConnected||busy}>
        {busy?<LoaderCircle size={15} className="spin"/>:<RefreshCw size={15}/>}
        {busy?"Mengambil data sumber…":"Imbas sekitar 1.5 km"}
      </button>
      <p>Imbasan menghantar titik rujukan tapak yang dibundarkan (bukan boundary penuh) kepada pelayan Overpass awam. Data ini tidak membuktikan akses jalan sah, kelulusan atau risiko banjir.</p>
    </div>
    {!backendConnected&&<p className="site-evidence-notice">Backend GIS belum bersambung. Data sekitar tidak dapat diambil.</p>}
    {backendConnected&&!project?.geometry&&<p className="site-evidence-notice">Cipta projek dan simpan boundary dahulu untuk mengimbas kawasan secara automatik.</p>}
    {error&&<p className="site-evidence-error" role="alert"><CircleAlert size={15}/>{error}</p>}
    {result?.exists&&result.context?
      <>
        <p className="site-evidence-provenance"><ShieldCheck size={14}/>
          Sumber: <a href={result.context.source_url} target="_blank" rel="noopener noreferrer">{result.context.source_name}</a>
          {" · "}Diperoleh {new Date(result.context.retrieved_at_utc).toLocaleString("ms-MY")}
          {" · "}Radius {result.context.radius_m.toLocaleString("ms-MY")} m
        </p>
        <div className="site-evidence-counts">{values.map(([key,n])=>
          <div key={key}><small>{labels[key]??key}</small><strong>{n.toLocaleString("ms-MY")}</strong></div>)}</div>
        <h3>Tempat bernama ditemui <small>(maks. 30, jarak garis lurus)</small></h3>
        {result.context.named_places.length?
          <div className="site-evidence-places">{result.context.named_places.map(p=>
            <a key={p.osm_feature_id} href={p.osm_url} target="_blank" rel="noopener noreferrer">
              <span><strong>{p.name}</strong><small>{labels[p.category]??p.category} · kira-kira {p.distance_from_reference_point_m.toLocaleString("ms-MY")} m</small></span>
              <ExternalLink size={13}/></a>)}</div>
          :<p className="site-evidence-notice">Tiada nama tempat direkod dalam respons OSM. Ini TIDAK membuktikan tiada kemudahan.</p>}
        <p className="site-evidence-notice">© OpenStreetMap contributors · ODbL. Sumber komuniti yang mungkin tidak lengkap. Bilangan jalan ialah segmen peta, bukan pengesahan akses tapak. Sungai/parit dalam OSM bukan peta bahaya banjir JPS.</p>
      </>
      :backendConnected&&project?.geometry&&!busy&&<p className="site-evidence-notice">Belum ada imbasan yang sah untuk sempadan projek ini. Klik “Imbas sekitar 1.5 km” untuk mengambil data terkini daripada sumber luar.</p>}
  </section>;
}
