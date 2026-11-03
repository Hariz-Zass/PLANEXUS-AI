"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, ArrowDownToLine, ArrowRight, BarChart3, BrainCircuit, Check, CheckCircle2, ChevronDown,
  CircleAlert, CloudDownload, Compass, Database, FileCode2, FileText, FolderOpen, GitBranch,
  Globe2, Info, Layers3, LoaderCircle, Map as MapIcon, MapPin, Menu, Mountain, Route,
  Plus, ScanSearch, Send, Settings2, ShieldCheck, Sparkles, Trash2, UploadCloud, X, Radar, Ruler, Crosshair, Orbit, ChevronRight, WandSparkles, CircleDot, MoveUpRight
} from "lucide-react";
import { API_BASE, api, browserApiBase, setAuthCsrf, type AuthResponse, type AuthUser, type FeatureGeometry, type SavedSummary, type TerrainReport, type ProjectSummary, type ProjectDetail } from "@/lib/api";
import ProjectWorkspace from "@/components/ProjectWorkspace";
import SuitabilityPanel from "@/components/SuitabilityPanel";
import ProposalStudio from "@/components/ProposalStudio";
import GppLibrary from "@/components/GppLibrary";
import LayoutStudio from "@/components/LayoutStudio";
import {readSavedSite,saveSiteBoundary,removeSavedSite,downloadSiteGeoJSON,validateSiteBoundary,SITE_STORAGE_KEY,type SiteOrigin} from "@/lib/site-storage";

const TerrainMap = dynamic(() => import("@/components/TerrainMap"), { ssr: false });
type SidebarTab = "workspace" | "sources" | "history" | "projects" | "proposals" | "policy" | "layout";
const PAGE_LABELS:Record<SidebarTab,string>={
  projects:"Project Workspace",
  workspace:"Terrain Intelligence",
  sources:"Data Registry",
  history:"Saved Analyses",
  proposals:"Development Studio",
  policy:"GPP Knowledge Registry",
  layout:"Smart Layout Studio",
};
const ACTIVE_PROJECT_KEY = "planexus:active-project:v1";
function preferredTerrainLayer(value:TerrainReport|null):"slope"|"elevation"|"suitability" {
  if(value?.suitability_geojson?.features?.length)return "suitability";
  if(value?.slope_geojson?.features?.length)return "slope";
  if(value?.elevation_geojson?.features?.length)return "elevation";
  return "slope";
}
type CopilotEvidence = { analysis_id:string; source_name:string; data_type:string; nominal_resolution_m:number|null; coverage_percent_est:number; site_area_ha:number; slope_mean_deg:number; slope_max_deg:number; elevation_min_m:number; elevation_max_m:number; warning_count:number };
type ChatMessage = { role: "user" | "assistant"; text: string; mode?: string; notice?: string; evidence?: CopilotEvidence | null; policy_sources?: {title:string;url:string;evidence:string}[] };

function normalizeGeoJSON(content: unknown): FeatureGeometry {
  if (!content || typeof content !== "object") throw new Error("Fail tidak mengandungi GeoJSON yang sah.");
  const payload = content as Record<string, unknown>;
  let target: unknown = payload;
  if (payload.type === "FeatureCollection") {
    const features = payload.features as unknown[];
    if (!Array.isArray(features) || features.length !== 1) throw new Error("V1 menerima satu polygon GeoJSON pada satu masa. FeatureCollection mesti ada tepat satu feature.");
    target = (features[0] as Record<string, unknown>).geometry;
  } else if (payload.type === "Feature") target = payload.geometry;
  if (!target || typeof target !== "object") throw new Error("Geometri kosong.");
  const geometry = target as Record<string, unknown>;
  if (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") throw new Error("Gunakan GeoJSON Polygon atau MultiPolygon WGS84.");
  if (!Array.isArray(geometry.coordinates)) throw new Error("Koordinat GeoJSON tidak sah.");
  return validateSiteBoundary(geometry);
}

function shortDate(value: string) {
  try { return new Intl.DateTimeFormat("ms-MY", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
  catch { return value; }
}

function formattedNumber(value?: number, digits = 2) {
  return value === undefined ? "—" : value.toLocaleString("en-MY", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function MarkdownParagraph({ text }: { text: string }) {
  return <div className="response-content">{text.split(/\n\n+/).map((block, index) => {
    const parts = block.split(/(\*\*[^*]+\*\*)/g);
    return <p key={index}>{parts.map((part, j) => part.startsWith("**") && part.endsWith("**") ? <strong key={j}>{part.slice(2, -2)}</strong> : <span key={j}>{part}</span>)}</p>;
  })}</div>;
}


function NexusMark({ size = 27 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" fill="none" aria-hidden="true">
      <path d="M18 3 32 11v14L18 33 4 25V11L18 3Z" stroke="currentColor" strokeOpacity=".55" strokeWidth="1.25"/>
      <path d="M18 3v30M4 11l28 14M32 11 4 25" stroke="currentColor" strokeOpacity=".16" strokeWidth="1"/>
      <path d="m11 23 7-12 7 12M14.3 18h7.4" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="18" cy="3" r="2.6" fill="#B4F77D"/>
      <circle cx="4" cy="25" r="2.5" fill="#70DEC9"/>
      <circle cx="32" cy="25" r="2.5" fill="#78A7FF"/>
    </svg>
  );
}

/** Early-stage WGS84 spherical approximation, not a cadastral/survey area. */
function getFootprint(geometry: FeatureGeometry) {
  const polygons: number[][][][] = geometry.type === "Polygon"
    ? [geometry.coordinates as number[][][]] : geometry.coordinates as number[][][][];
  const earthRadius = 6378137;
  const rad = Math.PI / 180;
  let area = 0;
  let perimeter = 0;
  for (const polygon of polygons) {
    for (let ringNumber = 0; ringNumber < polygon.length; ringNumber++) {
      const ring = polygon[ringNumber];
      if (!ring || ring.length < 3) continue;
      let sum = 0;
      let length = 0;
      for (let i = 0; i < ring.length; i++) {
        const a = ring[i];
        const b = ring[(i + 1) % ring.length];
        const latA = a[1] * rad;
        const latB = b[1] * rad;
        let dLon = (b[0] - a[0]) * rad;
        if (dLon > Math.PI) dLon -= Math.PI * 2;
        if (dLon < -Math.PI) dLon += Math.PI * 2;
        sum += dLon * (2 + Math.sin(latA) + Math.sin(latB));
        const dLat = latB - latA;
        const hav = Math.sin(dLat / 2) ** 2 + Math.cos(latA) * Math.cos(latB) * Math.sin(dLon / 2) ** 2;
        length += 2 * earthRadius * Math.asin(Math.min(1, Math.sqrt(hav)));
      }
      area += (ringNumber === 0 ? 1 : -1) * Math.abs(sum) * earthRadius ** 2 / 2;
      perimeter += length;
    }
  }
  return { areaHa: Math.max(0, area / 10000), perimeterKm: perimeter / 1000 };
}

function Workspace({user,onLogout}:{user:AuthUser;onLogout:()=>void}) {
  const [tab, setTab] = useState<SidebarTab>("projects");
  const [mobileNav, setMobileNav] = useState(false);
  const [drawing, setDrawing] = useState(false);
  const [drawPoints, setDrawPoints] = useState(0);
  const [resetCounter, setResetCounter] = useState(0);
  const [geometry, setGeometry] = useState<FeatureGeometry | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [activeProject, setActiveProject] = useState<ProjectDetail | null>(null);
  const [projectBusy, setProjectBusy] = useState(false);
  const [projectError, setProjectError] = useState("");
  const projectRef = useRef<ProjectDetail | null>(null);
  const [saveState,setSaveState]=useState<"checking"|"saved"|"empty"|"error">("checking");
  const [savedAt,setSavedAt]=useState("");
  const [saveMessage,setSaveMessage]=useState("");
  const [report, setReport] = useState<TerrainReport | null>(null);
  const [gisStatus, setGisStatus] = useState<"checking" | "online" | "offline">("checking");
  const [persistentBackend, setPersistentBackend] = useState(false);
  const [llmConfigured, setLlmConfigured] = useState(false);
  const [terrainLayer,setTerrainLayer] = useState<"slope"|"elevation"|"suitability">("slope");
  const [showContours,setShowContours] = useState(true);
  const [recent, setRecent] = useState<SavedSummary[]>([]);
  const [pending, setPending] = useState<null | "auto" | "upload" | "copilot">(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [demFile, setDemFile] = useState<File | null>(null);
  const [sourceName, setSourceName] = useState("");
  const [heightModel, setHeightModel] = useState("DTM");
  const [datum, setDatum] = useState("");
  const [confirmedUnits, setConfirmedUnits] = useState(false);
  const [uploadExpanded, setUploadExpanded] = useState(false);
  const [question, setQuestion] = useState("Bagaimana cara analisis topografi tapak saya?");
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const geojsonInput = useRef<HTMLInputElement>(null);
  const tiffInput = useRef<HTMLInputElement>(null);
  const footprint = useMemo(() => geometry ? getFootprint(geometry) : null, [geometry]);
  const footprintDisplay = geometry ? formattedNumber(report?.metrics.site_area_ha ?? footprint?.areaHa, 3) : "—";
  const perimeterDisplay = geometry ? formattedNumber(footprint?.perimeterKm, 2) : "—";
  const displayedAnalyses = activeProject ? activeProject.analyses : recent;

  const refreshProjectList = useCallback(async () => {
    if (!API_BASE) return;
    const result=await api<{projects:ProjectSummary[]}>("/api/projects");
    setProjects(result.projects);
  }, []);

  const applyProject = useCallback((details:ProjectDetail, analysis:TerrainReport|null) => {
    projectRef.current=details;setActiveProject(details);
    setGeometry(details.geometry);setReport(analysis);setChat([]);
    setTerrainLayer(preferredTerrainLayer(analysis));
    setDrawing(false);setResetCounter(n=>n+1);
    setSaveState(details.geometry?"saved":"empty");
    setSavedAt(details.updated_at_utc);
    setSaveMessage("");
    // Server save succeeded; blocked browser storage must not turn this
    // successful operation into an apparent project-creation failure.
    try { window.localStorage.setItem(ACTIVE_PROJECT_KEY,details.id); }
    catch { setSaveMessage("Project saved on backend. This browser cannot remember the active project automatically."); }
    setStatus("Projek "+details.name+" dibuka. "+
      (analysis?"Layer dan laporan analisis berjaya dipulihkan.":details.geometry?"Sempadan tapak dipulihkan daripada SQLite.":"Cipta atau import sempadan baharu."));
  }, []);

  const refreshRecent = useCallback(async () => {
    try { const results = await api<{ analyses: SavedSummary[] }>("/api/analyses"); setRecent(results.analyses); }
    catch { /* backend may be offline; shown when the user requests analysis */ }
  }, []);
  useEffect(() => { void refreshRecent(); }, [refreshRecent]);
  useEffect(() => {
    if (!API_BASE) { setGisStatus("offline"); return; }
    let active = true;
    const probe = async () => {
      try {
        const health = await api<{ status: string; persistent?: boolean }>("/api/health");
        if (active) {
          setGisStatus(health.status === "ok" ? "online" : "offline");
          setPersistentBackend(health.persistent === true);
        }
      } catch { if (active) { setGisStatus("offline"); setPersistentBackend(false); } }
      try {
        const capabilities = await api<{ generative_ai_configured: boolean }>("/api/copilot/capabilities");
        if (active) setLlmConfigured(Boolean(capabilities.generative_ai_configured));
      } catch { if (active) setLlmConfigured(false); }
    };
    void probe();
    return () => { active = false; };
  }, []);


  useEffect(() => {
    if (!API_BASE) return;
    let active=true;
    const initialize=async()=>{
      try {
        const listing=await api<{projects:ProjectSummary[]}>("/api/projects");
        if(!active)return;
        setProjects(listing.projects);
        const savedId=window.localStorage.getItem(ACTIVE_PROJECT_KEY);
        if(!savedId)return;
        if(!listing.projects.some(item=>item.id===savedId)){
          window.localStorage.removeItem(ACTIVE_PROJECT_KEY);
          return;
        }
        const detail=await api<ProjectDetail>("/api/projects/"+savedId);
        let analysis:TerrainReport|null=null;
        if(detail.active_analysis_id){
          try { analysis=await api<TerrainReport>("/api/analyses/"+detail.active_analysis_id); }
          catch { if(active)setProjectError("Laporan projek terakhir tiada dalam backend. Sempadan masih boleh dipulihkan."); }
        }
        if(active)applyProject(detail,analysis);
      }catch(e){
        if(active)setProjectError(e instanceof Error?e.message:"Project registry tidak boleh dibuka.");
      }
    };
    void initialize();
    return()=>{active=false;};
  }, [applyProject]);

  useEffect(()=>{
    const restore=()=>{
      if(projectRef.current)return;
      // Stand-alone browser draft is NOT the currently selected server project.
      // Never render another project's polygon while backend recovery is pending.
      try {
        if(window.localStorage.getItem(ACTIVE_PROJECT_KEY)){
          setGeometry(null);setReport(null);setChat([]);
          setSaveState("checking");
          setSaveMessage("Menunggu pengesahan projek aktif daripada GIS backend; local draft tidak digunakan.");
          return;
        }
      }catch{
        setSaveState("error");
        setSaveMessage("Browser menyekat project ID; buka semula projek daripada GIS backend.");
        return;
      }
      const r=readSavedSite();
      if(r.state==="found"){setGeometry(r.site.geometry);setSaveState("saved");setSavedAt(r.site.savedAt);setSaveMessage("");setReport(null);setChat([]);}
      else if(r.state==="empty"){setGeometry(null);setSaveState("empty");setSavedAt("");setSaveMessage("");setReport(null);setChat([]);}
      else{setSaveState("error");setSaveMessage(r.message);}
    };
    restore();
    const onStorage=(e:StorageEvent)=>{if(e.key===SITE_STORAGE_KEY){restore();setDrawing(false);}};
    window.addEventListener("storage",onStorage);
    return()=>window.removeEventListener("storage",onStorage);
  },[]);
  async function openProject(id:string){
    if(projectBusy||pending)return;
    setProjectBusy(true);setProjectError("");setError("");
    try{
      const detail=await api<ProjectDetail>("/api/projects/"+encodeURIComponent(id));
      let analysis:TerrainReport|null=null;
      if(detail.active_analysis_id){
        try{analysis=await api<TerrainReport>("/api/analyses/"+detail.active_analysis_id);}
        catch{setProjectError("Hasil analisis untuk projek ini tiada dalam storan. Boundary masih dipulihkan.");}
      }
      applyProject(detail,analysis);
      setTab("workspace");setMobileNav(false);
      try { await refreshProjectList(); }
      catch { setProjectError("Projek dibuka, tetapi senarai projek belum dapat dimuat semula."); }
    }catch(e){setProjectError(e instanceof Error?e.message:"Tidak dapat membuka projek.");throw e;}
    finally{setProjectBusy(false);}
  }

  async function createProject(name:string,description:string,useCurrentBoundary:boolean){
    if(projectBusy||pending)throw Error("Workspace sedang digunakan.");
    setProjectBusy(true);setProjectError("");setError("");
    try{
      const detail=await api<ProjectDetail>("/api/projects",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({name,description,geometry:useCurrentBoundary?geometry:null})
      });
      applyProject(detail,null);
      setTab("workspace");setMobileNav(false);
      try { await refreshProjectList(); }
      catch { setProjectError("Projek dicipta, tetapi senarai projek belum dapat dimuat semula."); }
    }catch(e){setProjectError(e instanceof Error?e.message:"Tidak dapat mencipta projek.");throw e;}
    finally{setProjectBusy(false);}
  }

  async function renameProject(id:string,name:string){
    if(projectBusy||pending)throw Error("Workspace sedang digunakan.");
    setProjectBusy(true);setProjectError("");
    try{
      const current=projects.find(item=>item.id===id);
      if(!current)throw Error("Projek tidak ditemui dalam senarai.");
      const detail=await api<ProjectDetail>("/api/projects/"+encodeURIComponent(id),{
        method:"PATCH",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({expected_revision:current.revision,name})
      });
      if(projectRef.current?.id===id){projectRef.current=detail;setActiveProject(detail);}
      await refreshProjectList();
    }catch(e){setProjectError(e instanceof Error?e.message:"Tidak dapat tukar nama projek.");throw e;}
    finally{setProjectBusy(false);}
  }

  async function deleteProject(id:string){
    if(projectBusy||pending)return;
    const target=projects.find(item=>item.id===id);
    if(!target)return;
    if(!window.confirm("Padam rekod projek '"+target.name+"' daripada database tempatan? Laporan/raster lama masih disimpan di folder backend."))return;
    setProjectBusy(true);setProjectError("");
    try{
      await api<void>("/api/projects/"+encodeURIComponent(id),{method:"DELETE"});
      if(projectRef.current?.id===id){
        projectRef.current=null;setActiveProject(null);
        window.localStorage.removeItem(ACTIVE_PROJECT_KEY);
        removeSavedSite();
        setGeometry(null);setReport(null);setChat([]);setSaveState("empty");setSavedAt("");
        setResetCounter(n=>n+1);
        setStatus("Rekod projek dipadam. Fail analisis asal tidak dipadam.");
      }
      await refreshProjectList();
    }catch(e){setProjectError(e instanceof Error?e.message:"Tidak dapat memadam projek.");}
    finally{setProjectBusy(false);}
  }

  const activateSite=useCallback(async (input:FeatureGeometry,origin:SiteOrigin)=>{
    const valid=validateSiteBoundary(input);
    const current=projectRef.current;
    // Do not change the active project's map or browser backup before SQLite confirms.
    // A failed PATCH must leave the previous verified report and site intact.
    setDrawing(false);setError("");setResetCounter(n=>n+1);
    if(current){
      setProjectBusy(true);setSaveState("checking");
      setStatus("Menyimpan sempadan ke project registry…");
      try{
        const updated=await api<ProjectDetail>("/api/projects/"+current.id,{
          method:"PATCH",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({expected_revision:current.revision,geometry:valid})
        });
        if(projectRef.current?.id===current.id){
          projectRef.current=updated;setActiveProject(updated);
          setGeometry(updated.geometry);setReport(null);setChat([]);
          const backup=saveSiteBoundary(valid,origin);
          setSaveState("saved");setSavedAt(updated.updated_at_utc);setSaveMessage(backup.saved?"":"Project saved on server. Local browser backup unavailable.");
          setStatus("Sempadan projek disimpan dan boleh dibuka semula: '"+updated.name+"'.");
        }
        await refreshProjectList();
      }catch(e){
        const message=e instanceof Error?e.message:"Project save failed";
        setSaveState(current.geometry?"saved":"empty");
        setSaveMessage("Sempadan baharu GAGAL disimpan: "+message+" · Sempadan asal kekal pada projek.");
        setStatus("Tiada perubahan projek disahkan.");
        setError("Sempadan baharu TIDAK dipakai; tapak asal masih dikekalkan. "+message);
      }finally{setProjectBusy(false);}
    }else{
      const local=saveSiteBoundary(valid,origin);
      setGeometry(valid);setReport(null);setChat([]);
      if(local.saved){
        setSaveState("saved");setSavedAt(local.site.savedAt);setSaveMessage("");
        setStatus("Tapak disimpan dalam browser ini sahaja. Cipta projek dan sambungkan GIS backend untuk simpan data projek.");
      }else{
        setSaveState("error");setSaveMessage(local.message);
        setStatus("Tapak belum disimpan. Export GeoJSON sebagai backup.");
      }
    }
  },[refreshProjectList]);

  const onSiteDrawn=useCallback((geo:FeatureGeometry)=>{
    void activateSite(geo,"map-drawing").catch(e=>{
      setError(e instanceof Error?e.message:"Polygon tidak sah.");
      setDrawing(false);
    });
  },[activateSite]);

  function startDraw(){
    if(projectBusy||pending)return;
    setDrawing(true);setError("");
    setStatus("Lukis tapak baharu. Tapak asal tidak dipadam sehingga polygon baharu siap.");
    setResetCounter(n=>n+1);
  }

  async function clearSite(){
    if(projectBusy||pending)return;
    if(!window.confirm("Padam sempadan tapak aktif? Jika projek dipilih, sempadan pada database juga dikosongkan. Export GeoJSON dahulu untuk backup."))return;
    const current=projectRef.current;
    if(current){
      setProjectBusy(true);setError("");
      try{
        const updated=await api<ProjectDetail>("/api/projects/"+current.id,{
          method:"PATCH",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({expected_revision:current.revision,geometry:null})
        });
        projectRef.current=updated;setActiveProject(updated);
        removeSavedSite();
        setGeometry(null);setDrawing(false);setReport(null);setChat([]);
        setResetCounter(n=>n+1);setSaveState("empty");setSavedAt("");
        setStatus("Sempadan projek telah dipadam daripada rekod aktif. Sejarah analisis dikekalkan.");
        await refreshProjectList();
      }catch(e){setSaveState(current.geometry?"saved":"empty");setSaveMessage("Gagal padam; sempadan asal masih disimpan pada projek.");setError(e instanceof Error?e.message:"Gagal memadam sempadan projek.");}
      finally{setProjectBusy(false);}
      return;
    }
    const r=removeSavedSite();
    if(!r.removed){setSaveState("error");setSaveMessage(r.message||"Gagal memadam simpanan.");return;}
    setGeometry(null);setDrawing(false);setReport(null);setChat([]);
    setResetCounter(n=>n+1);setSaveState("empty");setSavedAt("");
    setStatus("Sempadan tapak lokal dipadam.");
  }

  async function loadGeoJson(file?:File){
    if(!file)return;
    setError("");
    try{
      if(file.size>3000000)throw new Error("Fail GeoJSON melebihi 3 MB.");
      await activateSite(normalizeGeoJSON(JSON.parse(await file.text()) as unknown),"geojson-import");
    }catch(e){setError(e instanceof Error?e.message:"Import GeoJSON gagal.");}
    finally{if(geojsonInput.current)geojsonInput.current.value="";}
  }

  async function analyzeAuto(){
    if(!geometry||pending||projectBusy)return;
    const current=projectRef.current;
    setPending("auto");setError("");
    setStatus("Mendapatkan DSM Copernicus, mengira kecerunan dan mengekalkan sumber data…");
    try{
      const result=await api<TerrainReport>("/api/terrain/auto",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({geometry,project_id:current?.id??null})
      });
      setReport(result);setChat([]);setTerrainLayer(preferredTerrainLayer(result));
      setStatus(current?"Analisis selesai dan dipautkan kepada projek aktif.":"Analisis disimpan sebagai laporan lama tanpa pautan projek.");
      if(current){
        try{
          const updated=await api<ProjectDetail>("/api/projects/"+current.id);
          if(projectRef.current?.id===current.id){projectRef.current=updated;setActiveProject(updated);}
          await refreshProjectList();
        }catch{setProjectError("Analisis siap tetapi senarai projek belum dapat dimuat semula.");}
      }
      void refreshRecent();
    }catch(e){setError(e instanceof Error?e.message:"Gagal mengambil DSM. Tiada data rekaan.");setStatus("");}
    finally{setPending(null);}
  }

  async function analyzeUploaded(){
    if(!geometry||!demFile||!sourceName.trim()||!confirmedUnits||pending||projectBusy)return;
    const current=projectRef.current;
    setPending("upload");setError("");setStatus("Memproses GeoTIFF dan mengesahkan CRS serta statistik cerun…");
    try{
      const form=new FormData();
      form.append("geometry",JSON.stringify(geometry));
      form.append("file",demFile);
      form.append("source_name",sourceName);
      form.append("vertical_unit","metres");
      form.append("height_model",heightModel);
      form.append("vertical_datum",datum||"unknown");
      if(current)form.append("project_id",current.id);
      const result=await api<TerrainReport>("/api/terrain/upload",{method:"POST",body:form});
      setReport(result);setChat([]);setTerrainLayer(preferredTerrainLayer(result));
      setStatus(current?"GeoTIFF dianalisis dan dipautkan ke projek aktif.":"GeoTIFF dianalisis, tetapi belum dipautkan ke projek.");
      if(current){
        try{
          const updated=await api<ProjectDetail>("/api/projects/"+current.id);
          if(projectRef.current?.id===current.id){projectRef.current=updated;setActiveProject(updated);}
          await refreshProjectList();
        }catch{setProjectError("Analisis siap tetapi projek perlu dimuat semula.");}
      }
      void refreshRecent();
    }catch(e){setError(e instanceof Error?e.message:"Analisis GeoTIFF gagal.");setStatus("");}
    finally{setPending(null);}
  }

  async function reopenAnalysis(id:string){
    if(pending||projectBusy)return;
    const current=projectRef.current;
    setPending("auto");setError("");
    try{
      if(current&&!current.analyses.some(item=>item.analysis_id===id)){
        throw Error("Analisis ini bukan milik projek aktif. Pilih projek yang betul dahulu.");
      }
      const report=await api<TerrainReport>("/api/analyses/"+id);
      if(current){
        const updated=await api<ProjectDetail>("/api/projects/"+current.id+"/activate-analysis",{
          method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({analysis_id:id})
        });
        applyProject(updated,report);
        await refreshProjectList();
      }else{
        await activateSite(report.geometry,"analysis-reopened");
        setReport(report);
        setTerrainLayer(preferredTerrainLayer(report));
      }
      setStatus("Laporan dan layer GIS dipulihkan daripada analisis tersimpan.");
      setTab("workspace");setMobileNav(false);
    }catch(e){setError(e instanceof Error?e.message:"Tidak dapat membuka analisis.");}
    finally{setPending(null);}
  }

  async function askCopilot() {
    if (gisStatus !== "online" || question.trim().length < 3 || pending) return;
    const prompt = question.trim();
    setChat(messages => [...messages, { role: "user", text: prompt }]); setQuestion(""); setPending("copilot"); setError("");
    try {
      const answer = await api<{ response: string; mode: string; notice: string; evidence?: CopilotEvidence | null; policy_sources?: {title:string;url:string;evidence:string}[] }>("/api/copilot/assess", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ analysis_id: report?.analysis_id ?? null, question: prompt }) });
      setChat(messages => [...messages, { role: "assistant", text: answer.response, mode: answer.mode, notice: answer.notice, evidence: answer.evidence, policy_sources: answer.policy_sources }]);
    } catch (ex) { setError(ex instanceof Error ? ex.message : "Copilot tidak dapat menjawab."); setQuestion(prompt); }
    finally { setPending(null); }
  }

  return (
    <div className="shell shell-v2">
      <header className="topbar">
        <div className="brand-area">
          <button className="icon-button mobile-menu" onClick={() => setMobileNav(v => !v)} aria-label="Buka navigasi"><Menu size={22} /></button>
          <div className="brand-icon"><NexusMark /></div>
          <div className="brand-text"><span className="brand-name">PLANEXUS <em>AI</em></span><span className="brand-sub">GEOSPATIAL INTELLIGENCE SYSTEM</span></div>
        </div>
        <div className="topbar-middle"><span className="topbar-separator" /><span className="crumb"><Crosshair size={13}/> COMMAND CENTER</span><ChevronRight size={13} className="crumb-chevron"/><span className="crumb-active">{PAGE_LABELS[tab]}</span></div>
        <div className="topbar-right">
          <span className={"system-indicator "+(gisStatus === "online" ? "system-online" : "system-offline")}><i /> {gisStatus === "online" ? "GIS ENGINE CONNECTED" : gisStatus === "checking" ? "CHECKING GIS ENGINE" : "GIS ENGINE OFFLINE"}</span>
          <span className="version-pill">DESIGN 02 <span>/</span> TERRAIN V1</span>
          <span className="account-label" title={user.email}>{user.display_name}</span>
          <button type="button" className="account-logout" aria-label="Logout" onClick={onLogout}><ShieldCheck size={14}/> Logout</button>
        </div>
      </header>

      <div className="layout">
        <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
          <div className="sidebar-inner-title"><span className="sidebar-studio-icon"><NexusMark size={18}/></span><div><strong>Planner Studio</strong><small>GEOSPATIAL WORKSPACE</small></div></div>
          <div className="sidebar-section-title">OPERATIONAL MODULES <span>01 — 07</span></div>
          <nav className="nav-list" aria-label="Modul PLANEXUS">
            <button className={"nav-item "+(tab === "projects" ? "selected" : "")} onClick={() => { setTab("projects"); setMobileNav(false); }}><span className="nav-index">01</span><Database size={18}/><span>Project Workspace</span>{projects.length > 0 && <span className="nav-count">{projects.length}</span>}</button>
            <button className={"nav-item "+(tab === "workspace" ? "selected" : "")} onClick={() => { setTab("workspace"); setMobileNav(false); }}><span className="nav-index">02</span><Mountain size={18}/><span>Terrain Intelligence</span><span className="nav-on-dot"/></button>
            <button className={"nav-item "+(tab === "sources" ? "selected" : "")} onClick={() => { setTab("sources"); setMobileNav(false); }}><span className="nav-index">03</span><Database size={18}/><span>Data Registry</span></button>
            <button className={"nav-item "+(tab === "history" ? "selected" : "")} onClick={() => { setTab("history"); setMobileNav(false); }}><span className="nav-index">04</span><FolderOpen size={18}/><span>Saved Analyses</span>{displayedAnalyses.length > 0 && <span className="nav-count">{displayedAnalyses.length}</span>}</button>
            <button className={"nav-item "+(tab === "proposals" ? "selected" : "")} onClick={() => { setTab("proposals"); setMobileNav(false); }}><span className="nav-index">05</span><BarChart3 size={18}/><span>Development Studio</span><span className="nav-on-dot"/></button>
            <button className={"nav-item "+(tab === "policy" ? "selected" : "")} onClick={() => { setTab("policy"); setMobileNav(false); }}><span className="nav-index">06</span><FileText size={18}/><span>GPP Knowledge Registry</span><span className="nav-on-dot"/></button>
            <button className={"nav-item "+(tab === "layout" ? "selected" : "")} onClick={() => { setTab("layout"); setMobileNav(false); }}><span className="nav-index">07</span><Route size={18}/><span>Smart Layout Studio</span><span className="nav-on-dot"/></button>
          </nav>
          <div className="sidebar-section-title secondary-title">FUTURE INTELLIGENCE <span>ROADMAP</span></div>
          <div className="nav-list locked-modules">
            <div className="nav-item locked"><Globe2 size={17}/><span>Site Context</span><span>SOON</span></div>
            <div className="nav-item locked"><FileText size={17}/><span>Planning Policy</span><span>SOON</span></div>
            <div className="nav-item locked"><Orbit size={17}/><span>Scenario Studio</span><span>SOON</span></div>
          </div>
          <div className="sidebar-rule-graphic" aria-hidden="true"><span>PX</span><i/><i/><i/></div>
          <div className="sidebar-bottom">
            <div className="sidebar-principle"><ShieldCheck size={18} /><div><strong>Evidence-first analysis</strong><span>No verified data, no unsupported conclusion.</span></div></div>
            <div className="sidebar-version"><span>PLANEXUS · TERRAIN ENGINE</span><span>0.6.0 LOCAL</span></div>
          </div>
        </aside>

        <main className="main-area">
          {tab === "workspace" && <>
            <div className="page-head page-head-v2">
              <div className="hero-copy">
                <div className="eyebrow"><span className="eyebrow-dot"/> INTELLIGENCE WORKSPACE <span className="eyebrow-slash">//</span> MODULE 002</div>
                <h1>Terrain <span className="h1-accent">Intelligence</span><span className="hero-title-mark">/</span></h1>
                <p>The terrain tells a story. <span>Understand the site, question the evidence, plan with clarity.</span></p>
              </div>
              <div className="head-actions">
                <button className="btn btn-subtle" disabled={projectBusy||pending!==null} onClick={() => geojsonInput.current?.click()}><UploadCloud size={16}/> Import GeoJSON</button>
                <button className="btn btn-accent" disabled={projectBusy||pending!==null} onClick={startDraw}><Crosshair size={17}/> {geometry ? "Redraw site" : "Define site"} <ArrowRight size={15}/></button>
              </div>
            </div>
            <div className="active-project-strip">
              <span className="active-project-icon"><FolderOpen size={21}/></span>
              <div className="active-project-text">
                <small>ACTIVE PROJECT / LOCAL SQLITE</small>
                <strong>{activeProject ? activeProject.name : "No project selected"}</strong>
                <span>{activeProject ? projectBusy ? "Saving project..." : activeProject.has_site ? "Boundary stored · revision "+activeProject.revision : "Empty project · define a site" : "Browser-only site mode · create a project to keep analyses together"}</span>
              </div>
              <button className="btn btn-outline" onClick={()=>setTab("projects")} disabled={projectBusy||pending!==null}>
                <Database size={15}/>{activeProject?"Manage projects":"Create project"}<ChevronRight size={15}/>
              </button>
            </div>
            {projectError && <div className="project-error" role="alert">{projectError}</div>}
            {gisStatus==="online"&&!persistentBackend&&<div className="project-error" role="alert">GIS API connected, but permanent storage is NOT verified by its health check. Back up project and raster data; do not assume the site will survive a server replacement.</div>}
            <section className="site-ribbon" aria-label="Snapshot geospatial tapak">
              <div className="ribbon-context"><span className="ribbon-context-icon"><Radar size={24}/></span><div><small>PROJECT TELEMETRY</small><strong>{activeProject ? activeProject.name : geometry ? "Browser draft / Active boundary" : "Awaiting site definition"}</strong><span>{geometry ? activeProject ? "Project boundary · WGS84" : "Browser backup · WGS84" : "Start by drawing a real site polygon"}</span></div></div>
              <div className="ribbon-data featured"><small>01 / SITE AREA</small><div className="ribbon-value">{geometry && !report ? "≈ " : ""}{footprintDisplay}<em>ha</em></div><span>{report ? "GIS-calculated" : geometry ? "Spherical estimate · not surveyed" : "No boundary selected"}</span></div>
              <div className="ribbon-data"><small>02 / PERIMETER</small><div className="ribbon-value">{geometry ? "≈ " : ""}{perimeterDisplay}<em>km</em></div><span>{geometry ? "Spherical estimate" : "Awaiting geometry"}</span></div>
              <div className="ribbon-data"><small>03 / MEAN SLOPE</small><div className="ribbon-value">{report ? formattedNumber(report.metrics.slope_mean_deg, 1) : "—"}<em>°</em></div><span>{report ? "From valid DEM pixels" : "DEM analysis required"}</span></div>
              <div className="ribbon-data"><small>04 / ELEVATION</small><div className="ribbon-value">{report ? formattedNumber(report.metrics.elevation_mean_m, 1) : "—"}<em>m</em></div><span>{report ? "Mean of valid pixels" : "Awaiting GIS evidence"}</span></div>
            </section>
            <div className="workspace-grid">
              <section className="work-column">
                <div className="workspace-card map-card">
                  <div className="card-topline">
                    <div className="card-title-row"><span className="card-icon"><Layers3 size={18}/></span><div className="map-heading"><strong>Geospatial Canvas <span> / 01</span></strong><small>EXPLORE & DEFINE YOUR SITE</small></div></div>
                    <div className="map-topline-right"><span className="card-meta">EPSG:4326 · WGS 84</span><span className="map-status"><i className={report ? "active" : ""}/>{report ? "TERRAIN ANALYSED" : drawing ? "DEFINING BOUNDARY" : geometry ? "SITE SELECTED" : "NO ACTIVE SITE"}</span></div>
                  </div>
                  <div className="map-layer-controls" aria-label="Terrain data layers"><button className={terrainLayer==="slope"?"active":""} type="button" disabled={!report?.slope_geojson?.features?.length} onClick={()=>setTerrainLayer("slope")} aria-pressed={terrainLayer==="slope"}>Slope</button><button className={terrainLayer==="elevation"?"active":""} type="button" disabled={!report?.elevation_geojson?.features?.length} onClick={()=>setTerrainLayer("elevation")} aria-pressed={terrainLayer==="elevation"}>Elevation</button><button className={terrainLayer==="suitability"?"active":""} type="button" disabled={!report?.suitability_geojson?.features?.length} aria-pressed={terrainLayer==="suitability"} onClick={()=>setTerrainLayer("suitability")}>Suitability</button><label><input type="checkbox" checked={showContours&&Boolean(report?.contours_geojson?.features?.length)} disabled={!report?.contours_geojson?.features?.length} onChange={event=>setShowContours(event.target.checked)} /> Contours</label></div>{!report&&<div role="status" className="inline-notice notice-error"><CircleAlert size={16}/><span>Slope dan Elevation memerlukan analisis DEM sebenar. Sempadan tapak bukan peta cerun. {gisStatus!=="online"?"GIS backend offline: paparan terrain belum tersedia secara online.":geometry?"Jalankan DEM dalam projek aktif.":"Sediakan projek dan sempadan tapak dahulu."}</span></div>}<div className="map-wrapper"><TerrainMap geometry={geometry} report={report} drawing={drawing} onSiteDrawn={onSiteDrawn} onPointCount={setDrawPoints} resetCounter={resetCounter} terrainLayer={terrainLayer} showContours={showContours} />
                    {!geometry && !drawing && <div className="map-empty"><div className="map-empty-icon"><ScanSearch size={26}/></div><strong>Start with your site boundary</strong><span>Draw a polygon on the map or import a GeoJSON file. No sample data is invented.</span><button className="btn btn-accent" onClick={startDraw}><Plus size={15} /> Draw site polygon</button></div>}
                    {drawing && <div className="drawing-notice"><MapPin size={16} /><span>Click vertices · Double-click to finish · <strong>{drawPoints} points</strong></span><button onClick={() => { setDrawing(false); setResetCounter(n=>n+1); setStatus(""); }}>Cancel</button></div>}
                    <div className="map-corner-badge"><CircleDot size={14}/><span>{report ? "TERRAIN LAYERS" : "VECTOR BASEMAP"}</span><i/></div>
                    <div className="map-compass-mark" aria-hidden="true"><span>N</span><span>↑</span></div>
                    <div className="map-overlay-lines" aria-hidden="true"><i/><i/><i/><i/></div>
                    <div className="map-info-hud">
                      <div className="hud-icon"><Crosshair size={19}/></div>
                      <div><small>CURRENT SELECTION</small><strong>{geometry ? "Defined site boundary" : "No active selection"}</strong><span>{geometry ? "Polygon · WGS84" : "Select an area to begin"}</span></div>
                      <div className="hud-readout">{geometry ? <><strong>{footprintDisplay}</strong><small>HA {report ? "GIS" : "EST."}</small></> : <><strong>—</strong><small>HA</small></>}</div>
                    </div>
                    <div className="map-coordinate-hud">03° - 07° N <span>/</span> 100° - 120° E <span>·</span> EXPLORE</div>
                  </div>
                  <div className="site-preservation-bar">
<div className={"save-indicator "+(saveState==="saved"?"save-indicator-ready":saveState==="error"?"save-indicator-error":"")}>
<span className="save-indicator-mark">{saveState==="saved"?<CheckCircle2 size={17}/>:saveState==="error"?<CircleAlert size={17}/>:<ShieldCheck size={17}/>}</span>
<div><strong>{saveState==="saved"?(activeProject?"PROJECT SAVED":"SITE AUTOSAVED"):saveState==="error"?"SITE NOT SAVED":saveState==="checking"?"SAVING / CHECKING":"NO SAVED SITE"}</strong><small>{saveState==="saved"&&savedAt?(activeProject?"SQLite backend · ":"Browser ini · ")+shortDate(savedAt):saveState==="error"?"Export GeoJSON for backup":"Draw/import a site boundary"}</small></div></div>
<div className="site-preservation-actions"><button className="btn btn-outline site-action-button" disabled={!geometry} onClick={()=>geometry&&downloadSiteGeoJSON(geometry)}><ArrowDownToLine size={15}/> Export GeoJSON</button><button className="btn btn-outline site-action-button destructive" disabled={!geometry} onClick={clearSite}><Trash2 size={15}/> Clear site</button></div></div>
{saveState==="error"&&<div className="save-warning" role="alert"><CircleAlert size={16}/>{saveMessage}</div>}
<div className="map-bottom"><div><span className="legend-title">TERRAIN LEGEND <span>//</span> {terrainLayer === "suitability" ? "PRELIMINARY TERRAIN CONSTRAINTS" : terrainLayer === "slope" ? "INDICATIVE SLOPE CLASSES" : "ELEVATION BANDS"} {report ? "" : "· AWAITING ANALYSIS"}</span>{terrainLayer === "suitability" ? <div className="legend-row">{report?.suitability?.bands.map(band=><span key={band.id}><i style={{background:band.color}}/>{band.id===4?"No slope data":band.min_deg+"°"+(band.max_deg===null?"+":"–<"+band.max_deg+"°")}</span>)}</div> : terrainLayer === "slope" ? <div className="legend-row"><span><i style={{ background: "#4cc9a3" }} />0–15°</span><span><i style={{ background: "#e5c46d" }} />15–25°</span><span><i style={{ background: "#eb8c64" }} />25–35°</span><span><i style={{ background: "#cb626f" }} />≥35°</span></div> : <div className="legend-row">{report?.metrics.elevation_legend?.length ? report.metrics.elevation_legend.map(band=><span key={band.class_id}><i style={{background:band.color}}/>{formattedNumber(band.min_m,0)}–{formattedNumber(band.max_m,0)} m</span>) : <span>No verified elevation classes yet</span>}</div>}{showContours && report?.metrics.contour_interval_m && <span className="terrain-legend-note">Contour preview at {report.metrics.contour_interval_m} m intervals · not surveyed</span>}</div><span className="map-credit"><ShieldCheck size={13}/> GIS screening only · Not planning approval</span></div>
                </div>
                <SuitabilityPanel report={report} activeOnMap={terrainLayer==="suitability"} onShowMap={()=>setTerrainLayer("suitability")}/>
                <section className="site-intel-card">
                  <div className="site-intel-main"><span className="section-overline"><ScanSearch size={13}/> SITE INTELLIGENCE / LIVE SNAPSHOT</span><h2>From site to <em>insight.</em></h2><p>Tapak sebenar dahulu, analisis kemudian. Kami tidak akan memaparkan keputusan cerun atau ketinggian sebelum GIS memproses DEM.</p></div>
                  <div className="intel-points">
                    <div><span>BOUNDARY</span><strong className={geometry ? "intel-ready" : ""}>{geometry ? "Defined" : "Not defined"}</strong><small>{geometry ? "Real polygon selected" : "Draw / import geometry"}</small></div>
                    <div><span>ELEVATION DATA</span><strong>{report ? "Available" : "Pending"}</strong><small>{report ? report.source.data_type : "Awaiting DEM"}</small></div>
                    <div><span>GIS ANALYSIS</span><strong>{report ? "Completed" : "Not run"}</strong><small>{report ? "Review provenance" : "No measured results yet"}</small></div>
                  </div>
                </section>
                <div className="workflow-card">
                  <div className="section-line"><div><h2>Analysis Workflow</h2><p>Mulakan dengan sempadan tapak yang sah</p></div><span className="section-tag"><Activity size={13} /> TERRAIN V1</span></div>
                  <div className="workflow-steps" aria-label="Progress kerja analisis">
                    {[
                      { number: "01", name: "Define site", done: Boolean(geometry), now: !geometry },
                      { number: "02", name: "Acquire DEM", done: Boolean(report), now: Boolean(geometry && !report) },
                      { number: "03", name: "GIS analysis", done: Boolean(report), now: false },
                      { number: "04", name: "Planning insight", done: chat.some(m => m.role === "assistant"), now: Boolean(report && chat.length === 0) },
                    ].map(step => <div className={"workflow-step"+(step.done ? " is-complete" : step.now ? " is-current" : "")} key={step.number}><span className="workflow-step-number">{step.done ? <Check size={13}/> : step.number}</span><span>{step.name}</span></div>)}
                  </div>
                  <div className="workflow-actions">
                    <div className={`workflow-option ${geometry ? "available" : ""}`}>
                      <div className="workflow-option-head"><span className="option-icon"><CloudDownload size={19}/></span><div><h3>Automatic DEM Retrieval</h3><p>Copernicus GLO-30 · Public DSM · ~30 m</p></div></div>
                      <p className="option-detail">Ambil COG rasmi mengikut koordinat tapak, semak liputan dan kira kelas kecerunan. Untuk saringan awal sahaja.</p>
                      <button className="btn btn-primary wide" disabled={!geometry || !activeProject || gisStatus!=="online" || pending !== null || projectBusy} onClick={() => void analyzeAuto()}>{pending === "auto" ? <LoaderCircle size={17} className="spin" /> : <ArrowRight size={16} />} {pending === "auto" ? "Retrieving & analysing…" : "Get DEM & Run Analysis"}</button>
                    </div>
                    <div className="workflow-option">
                      <div className="workflow-option-head"><span className="option-icon secondary"><UploadCloud size={19}/></span><div><h3>Professional Raster Upload</h3><p>GeoTIFF DTM / DSM · Max 60 MB</p></div></div>
                      <p className="option-detail">Ada data ukur lebih terperinci? Gunakan raster sendiri, dengan unit ketinggian yang disahkan.</p>
                      <button className="btn btn-outline wide" onClick={() => setUploadExpanded(v => !v)} aria-expanded={uploadExpanded}><Settings2 size={16}/> Configure Upload <ChevronDown size={16} className={uploadExpanded ? "rotate" : ""}/></button>
                    </div>
                  </div>
                  {uploadExpanded && <div className="upload-form"><div className="upload-form-head"><strong>GeoTIFF Input</strong><span>Source declaration is required</span></div>
                    <button className="drop-input" onClick={() => tiffInput.current?.click()}><UploadCloud size={20}/><span>{demFile ? demFile.name : "Choose a .tif / .tiff elevation raster"}</span><small>{demFile ? `${(demFile.size / 1024 / 1024).toFixed(2)} MB` : "60 MB maximum"}</small></button>
                    <div className="fields-row"><label>Dataset / provider<input placeholder="e.g. JUPEM site survey, 2025" value={sourceName} onChange={e => setSourceName(e.target.value)} /></label><label>Height model<select value={heightModel} onChange={e => setHeightModel(e.target.value)}><option value="DTM">DTM (bare-earth)</option><option value="DSM">DSM (surface)</option><option value="DEM-unknown">DEM (type unknown)</option></select></label></div>
                    <label className="full-label">Vertical datum (if known)<input placeholder="e.g. source documentation / unknown" value={datum} onChange={e => setDatum(e.target.value)}/></label>
                    <label className="checkbox-line"><input type="checkbox" checked={confirmedUnits} onChange={e => setConfirmedUnits(e.target.checked)} /> Saya sahkan nilai ketinggian raster dalam unit meter; ketepatan ukur perlu disemak secara berasingan.</label>
                    <button className="btn btn-primary" disabled={!geometry || !activeProject || gisStatus!=="online" || !demFile || !sourceName.trim() || !confirmedUnits || pending !== null || projectBusy} onClick={() => void analyzeUploaded()}>{pending === "upload" ? <LoaderCircle className="spin" size={16} /> : <Activity size={16}/>} Analyse Uploaded GeoTIFF</button>
                  </div>}
                </div>
                {(status || error) && <div role="status" className={`inline-notice ${error ? "notice-error" : ""}`}>{error ? <CircleAlert size={16}/> : <CheckCircle2 size={16}/>}<span>{error || status}</span>{error && <button onClick={() => setError("")} aria-label="Tutup ralat"><X size={15}/></button>}</div>}
                {report && <div className="results-card"><div className="section-line"><div><h2>Verified Terrain Outputs</h2><p>Calculated from raster data · {shortDate(report.created_at_utc)}</p></div><span className="verified-chip"><Check size={13}/> GIS CALCULATED</span></div>
                  <div className="metric-grid"><div className="metric"><span>SITE AREA</span><strong>{formattedNumber(report.metrics.site_area_ha)}</strong><small>hectares</small></div><div className="metric"><span>MEAN ELEVATION</span><strong>{formattedNumber(report.metrics.elevation_mean_m)}</strong><small>metres</small></div><div className="metric"><span>MEAN SLOPE</span><strong>{formattedNumber(report.metrics.slope_mean_deg)}°</strong><small>degrees</small></div><div className="metric"><span>DATA COVERAGE</span><strong>{formattedNumber(report.metrics.coverage_percent_est,1)}%</strong><small>estimated</small></div></div>
                  <div className="subsection-head"><strong>Slope distribution</strong><span>% of valid slope pixels</span></div>
                  <div className="slope-bar">{report.metrics.slope_classes.map(c => <div key={c.id} style={{ width: `${c.percent_of_valid_slope}%`, background: c.color }} title={`${c.name}: ${c.percent_of_valid_slope}%`} />)}</div>
                  <div className="class-results">{report.metrics.slope_classes.map(c => <div key={c.id}><span><i style={{ background: c.color }} />{c.name}</span><strong>{formattedNumber(c.percent_of_valid_slope)}%</strong><small>{formattedNumber(c.area_ha_est,3)} ha</small></div>)}</div>
                  <section className="terrain-qa" role="region" aria-label="GIS Data Quality Review" data-qa-status={report.quality?.status??"legacy"}>
                    <div className="terrain-qa-title">
                      <div><strong><ShieldCheck size={16}/> GIS DATA QUALITY</strong>
                        <p>Keputusan automatik ini bukan pengesahan ketepatan ukur atau kelulusan PBT.</p>
                      </div>
                      <span className="terrain-qa-status">{report.quality?.status?.toUpperCase()??"LEGACY — NOT REVIEWED"}</span>
                    </div>
                    {report.quality ? <>
                      <div className="terrain-qa-metrics">
                        <div><small>Elevation coverage</small><strong>{formattedNumber(report.quality.elevation_site_cell_coverage_pct,1)}%</strong></div>
                        <div><small>Slope coverage (Horn 3×3)</small><strong>{formattedNumber(report.quality.slope_site_cell_coverage_pct,1)}%</strong></div>
                        <div><small>Contour lines</small><strong>{report.metrics.contour_features??0}</strong></div>
                        <div><small>Processing CRS</small><strong>{report.metrics.horizontal_crs.replace("EPSG:","EPSG ")}</strong></div>
                      </div>
                      <p className="terrain-qa-method">{report.quality.method}</p>
                      {report.quality.flags.length>0 && <div className="terrain-qa-flags">{report.quality.flags.map((flag,i)=><p key={i}><CircleAlert size={13}/>{flag}</p>)}</div>}
                      {report.source_file && <div className="terrain-qa-provenance"><small>Input raster SHA-256</small><code title={report.source_file.sha256}>{report.source_file.sha256}</code></div>}
                      <p className="terrain-qa-pending">QGIS site-specific comparison: NOT YET VERIFIED. Source accuracy is not certified.</p>
                    </> : <p className="terrain-qa-pending">Laporan lama belum melalui audit B3.3. Jalankan semula DEM dan simpan laporan baharu.</p>}
                    <div className="terrain-qa-downloads">
                      {report.quality&&<a href={`${browserApiBase()}/api/analyses/${report.analysis_id}/verification.md`} className="btn btn-outline"><ArrowDownToLine size={14}/> GIS QA Report (.md)</a>}
                      {report.qa_artifacts&&<a href={`${browserApiBase()}/api/analyses/${report.analysis_id}/elevation-utm.tif`} className="btn btn-outline"><ArrowDownToLine size={14}/> Elevation UTM (.tif)</a>}
                      {report.qa_artifacts&&<a href={`${browserApiBase()}/api/analyses/${report.analysis_id}/slope-utm.tif`} className="btn btn-outline"><ArrowDownToLine size={14}/> Slope UTM (.tif)</a>}
                      {activeProject?.geometry&&<a href={`${browserApiBase()}/api/projects/${activeProject.id}/exports/gis-package.zip`} className="btn btn-outline"><ArrowDownToLine size={14}/> Complete GIS Package (.zip)</a>}
                      {activeProject?.geometry&&<a href={`${browserApiBase()}/api/projects/${activeProject.id}/exports/layers.gpkg`} className="btn btn-outline"><ArrowDownToLine size={14}/> GIS Layers (.gpkg)</a>}
                    </div>
                  </section>
                  <div className="source-card"><div className="source-icon"><ShieldCheck size={18}/></div><div><strong>Data Provenance</strong><p>{report.source.name} · {report.source.data_type}</p><span>{report.source.verified}</span>{report.source.reference && <a href={report.source.reference} target="_blank" rel="noopener noreferrer">Official dataset reference ↗</a>}</div></div>
                  <div className="limitations"><strong><CircleAlert size={16}/> Quality & scope warnings</strong>{report.warnings.map((warning,i) => <p key={i}>{warning}</p>)}</div>
                  <a className="btn btn-outline report-download" href={`${browserApiBase()}/api/analyses/${report.analysis_id}/report.md`}><ArrowDownToLine size={17}/> Download Evidence Report (.md)</a>
                </div>}
              </section>
              <aside className="copilot-card">
                <div className="copilot-header">
                  <div className="ai-avatar"><NexusMark size={27}/></div>
                  <div><small>THE INTELLIGENCE LAYER</small><h2>PLANEXUS <em>Copilot</em></h2><p>{gisStatus === "online" ? llmConfigured ? "LLM configured · GIS evidence required" : "Rule-based guidance · AI key not configured" : "Connect GIS backend to enable Copilot"}</p></div>
                  <span className="sparkle-dot"><WandSparkles size={19}/></span>
                </div>
                <div className="copilot-stream" aria-live="polite">
                  {chat.length === 0 && <div className="copilot-welcome">
                    <div className="copilot-orb" aria-hidden="true">
                      <span className="orb-orbit orbit-one"/><span className="orb-orbit orbit-two"/><span className="orb-orbit orbit-three"/>
                      <div className="orb-center"><BrainCircuit size={37} strokeWidth={1.3}/></div>
                      <span className="orb-satellite sat-a"/><span className="orb-satellite sat-b"/>
                    </div>
                    <div className="copilot-welcome-copy"><span className="section-overline">A SECOND MIND FOR PLANNERS</span><h3>Think beyond<br/><em>the map.</em></h3><p>{report ? "Copilot akan mentafsir cerun dan elevasi menggunakan hasil GIS yang disahkan." : "Tanya tentang aliran kerja sekarang. Penilaian khusus tapak memerlukan DEM dan analisis GIS."}</p></div>
                    <div className="copilot-checklist">
                      <div><span className={geometry ? "is-ready" : ""}>{geometry ? <Check size={12}/> : "01"}</span> Site boundary <strong>{geometry ? "READY" : "PENDING"}</strong></div>
                      <div><span className={report ? "is-ready" : ""}>{report ? <Check size={12}/> : "02"}</span> GIS evidence <strong>{report ? "READY" : "PENDING"}</strong></div>
                      <div><span className={gisStatus === "online" ? "is-ready" : ""}>03</span> Copilot <strong>{gisStatus !== "online" ? "OFFLINE" : report ? llmConfigured ? "LLM CONFIGURED" : "GIS GUIDANCE" : "GUIDANCE ONLY"}</strong></div>
                    </div>
                    <div className="prompt-library">
                      <div className="prompt-label"><Sparkles size={13}/> EXPLORE QUESTIONS</div>
                      <button type="button" disabled={gisStatus !== "online"} onClick={()=>setQuestion(report ? "Adakah tapak ini sesuai untuk rumah teres berdasarkan cerun dan elevasi?" : "Apakah data diperlukan untuk menilai kesesuaian rumah teres?")}><span>Housing suitability</span><MoveUpRight size={15}/></button>
                      <button type="button" disabled={gisStatus !== "online"} onClick={()=>setQuestion(report ? "Apakah taburan kelas cerun di tapak dan implikasinya?" : "Bagaimana cara mendapatkan DEM dan mengira slope?")}><span>Identify terrain constraints</span><MoveUpRight size={15}/></button>
                      <button type="button" disabled={gisStatus !== "online"} onClick={()=>setQuestion("Apakah saiz minimum lot rumah teres mengikut GPP PLANMalaysia dan GPP Perak?")}><span>Semak GPP perumahan</span><MoveUpRight size={15}/></button>
                    </div>
                  </div>}
                  {chat.map((message,i) => <div key={i} className={"message "+(message.role === "user" ? "message-user" : "message-assistant")}><div className="message-author">{message.role === "assistant" ? <><BrainCircuit size={14}/> PLANEXUS {message.mode === "llm_grounded" ? "AI" : message.mode === "workflow_guidance" ? "GUIDE" : message.mode === "verified_policy_registry_summary" ? "GPP SOURCE" : "GIS SUMMARY"}</> : <>PLANNER</>}</div>{message.role === "assistant" ? <MarkdownParagraph text={message.text}/> : <p>{message.text}</p>}{message.policy_sources?.length ? <div className="gpp-chat-citations">{message.policy_sources.map((source,i)=><a key={i} target="_blank" rel="noopener noreferrer" href={source.url}><FileText size={13}/>{source.title} · {source.evidence}</a>)}</div> : null}{message.evidence && <div className="copilot-evidence-line"><ShieldCheck size={13}/><span>{message.evidence.source_name} · {formattedNumber(message.evidence.coverage_percent_est,1)}% coverage · {message.evidence.nominal_resolution_m ? `~${message.evidence.nominal_resolution_m}m DSM` : message.evidence.data_type}</span></div>}{message.notice && <div className="response-note"><Info size={13}/>{message.notice}</div>}</div>)}
                  {pending === "copilot" && <div className="thinking"><LoaderCircle className="spin" size={15}/> Analysing GIS evidence…</div>}
                </div>
                <div className="copilot-compose">
                  <div className="copilot-preset"><span><span className={"compose-led "+(gisStatus === "online" ? "lit" : "")}/> COPILOT STATUS</span><span className={gisStatus === "online" ? "ready" : "unavailable"}>{gisStatus !== "online" ? "GIS server not connected" : report ? llmConfigured ? "Measured GIS · LLM configured" : "Measured GIS · rule-based" : "Workflow guidance only"}</span></div>
                  <div className="copilot-input-wrap"><textarea value={question} onChange={e=>setQuestion(e.target.value)} maxLength={800} placeholder={gisStatus !== "online" ? "Connect GIS backend to ask questions…" : report ? "Ask about measured slope, elevation or limitations…" : "Ask how to define site or retrieve DEM…"} rows={3} disabled={gisStatus !== "online"} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void askCopilot(); } }} /><button className="send-button" disabled={gisStatus !== "online" || pending !== null || question.trim().length < 3} onClick={() => void askCopilot()} aria-label="Hantar soalan"><ArrowRight size={19}/></button></div>
                  <div className="compose-bottom"><span><ShieldCheck size={13}/> NO DATA, NO CLAIMS</span><span>POWERED BY GIS EVIDENCE</span></div>
                </div>
              </aside>
            </div>
          </>}
          {tab === "layout" && <LayoutStudio key={activeProject?.id??"no-project"} project={activeProject} report={report}
            backendConnected={gisStatus==="online"} onOpenProjects={()=>setTab("projects")}
            onOpenTerrain={()=>setTab("workspace")} />}
          {tab === "policy" && <GppLibrary backendConnected={gisStatus==="online"} onOpenStudio={()=>setTab("proposals")}/>}
          {tab === "proposals" && <ProposalStudio key={activeProject?.id??"no-project"} project={activeProject} backendConnected={gisStatus==="online"} onOpenProjects={()=>setTab("projects")}/>}
          {tab === "projects" && <>{gisStatus!=="online"&&<div className="project-error" role="alert">GIS backend offline. Project creation, server storage, and project retrieval are unavailable on this deployment. Browser boundary backups are not saved projects.</div>}{gisStatus==="online"&&!persistentBackend&&<div className="project-error" role="alert">GIS API connected, but durable storage has not been verified. Do not rely on this server for cloud persistence until a mounted volume is confirmed.</div>}{activeProject?.geometry&&gisStatus==="online"&&<div className="project-gis-export" role="region" aria-label="Project GIS Export">
            <div><strong>Project GIS Export</strong><p>GeoPackage EPSG:4326, GeoJSON lapisan, raster UTM sebenar jika analisis sudah tersedia. Vektor peta mungkin dipotong untuk prestasi; semak manifest eksport.</p></div>
            <a href={`${browserApiBase()}/api/projects/${activeProject.id}/exports/gis-package.zip`} className="btn btn-primary"><ArrowDownToLine size={15}/> Download GIS Package (.zip)</a>
            <a href={`${browserApiBase()}/api/projects/${activeProject.id}/exports/site_boundary.geojson`} className="btn btn-outline"><ArrowDownToLine size={14}/> Site Boundary (.geojson)</a>
          </div>}<ProjectWorkspace projects={projects} backendConnected={gisStatus==="online"} activeId={activeProject?.id??null}
            geometry={geometry} busy={projectBusy || pending !== null} error={projectError}
            onCreate={createProject} onOpen={openProject} onRename={renameProject} onDelete={deleteProject}/></>}
          {tab === "sources" && <div className="secondary-page"><div className="eyebrow"><span className="eyebrow-dot"/> SOURCE TRANSPARENCY</div><h1>Data Source Registry <span className="h1-accent">.</span></h1><p>Setiap sumber mempunyai identiti, keupayaan dan had penggunaan. Tiada dataset geospatial yang direka oleh AI.</p><div className="info-panel"><div className="info-panel-head"><span className="info-icon"><Database size={22}/></span><div><strong>Copernicus DEM GLO-30 Public</strong><span>Primary automatic retrieval source · Public Cloud Optimized GeoTIFF</span></div><span className="registry-state">{gisStatus==="online"?"GIS ADAPTER CONNECTED":"SOURCE REFERENCE ONLY"}</span></div><div className="detail-table"><div><span>Publisher</span><strong>Copernicus Programme / ESA</strong></div><div><span>Approx. spatial resolution</span><strong>30 m</strong></div><div><span>Raster type</span><strong>DSM (buildings and vegetation included)</strong></div><div><span>Acquisition</span><strong>Direct public AWS COG tiles, no API key</strong></div><div><span>Primary purpose</span><strong>Preliminary terrain screening</strong></div></div><a href="https://registry.opendata.aws/copernicus-dem/" target="_blank" rel="noopener noreferrer" className="source-link">Official dataset documentation <ArrowRight size={16}/></a></div><div className="quality-panel"><CircleAlert size={19}/><div><strong>Important boundary</strong><p>Satellite-derived DSM is not equivalent to surveyed bare-earth DTM. Analysis outcomes do not certify zoning, flood safety, land title, slope stability or development approval. Public coverage may differ by country and tile availability.</p></div></div><div className="workflow-card"><h2>Additional data paths</h2><p>Users can upload GeoTIFF from authorized survey providers. PLANEXUS will inspect raster CRS and available cells but cannot independently authenticate the original survey or vertical datum without its documentation.</p></div></div>}
          {tab === "history" && <div className="secondary-page"><div className="eyebrow"><span className="eyebrow-dot"/> REPRODUCIBLE OUTPUTS</div><h1>Saved Analyses <span className="h1-accent">.</span></h1><div className="saved-site-history"><div className="saved-site-history-icon"><MapPin size={22}/></div><div><span className="section-overline">SAVED SITE / ACTIVE WORKSPACE</span><strong>{geometry?"Active site boundary":"No saved site"}</strong><small>{geometry?"≈ "+footprintDisplay+" ha · "+(saveState==="saved"?"Saved on this device":"Not backed up"):"Draw or import a site first."}</small></div><button className="btn btn-outline" onClick={()=>setTab("workspace")}>Open map</button>{geometry&&<button className="btn btn-outline" onClick={()=>downloadSiteGeoJSON(geometry)}>Export</button>}</div><p>Analisis aktif dipautkan kepada projek dipilih. Fail laporan/GeoTIFF berada pada storan backend lokal; cloud sync belum tersedia.</p><div className="history-list">{displayedAnalyses.length === 0 ? <div className="history-empty"><FolderOpen size={29}/><strong>No analyses saved yet</strong><span>Jalankan analisis pertama di Terrain Workspace.</span><button className="btn btn-primary" onClick={()=>setTab("workspace")}>Open workspace <ArrowRight size={15}/></button></div> : displayedAnalyses.map(item=><button key={item.analysis_id} className="history-item" onClick={()=>void reopenAnalysis(item.analysis_id)}><div className="history-icon"><BarChart3 size={19}/></div><div><strong>{item.source_name}</strong><span>{formattedNumber(item.site_area_ha,3)} ha · {shortDate(item.created_at_utc)}</span><small>{item.analysis_id}</small></div><ArrowRight size={18}/></button>)}</div></div>}
        </main>
      </div>
      <input ref={geojsonInput} hidden type="file" accept=".geojson,.json,application/geo+json,application/json" onChange={event=>void loadGeoJson(event.target.files?.[0])} />
      <input ref={tiffInput} hidden type="file" accept=".tif,.tiff,image/tiff" onChange={event=>setDemFile(event.target.files?.[0] || null)} />
    </div>
  );
}


// Authentication gates the entire GIS workspace. No project or raster API
// effect mounts until /api/auth/me has validated the HttpOnly cookie session.
export default function Home() {
  const [account,setAccount]=useState<AuthUser|null>(null);
  const [checking,setChecking]=useState(true);
  const [busy,setBusy]=useState(false);
  const [mode,setMode]=useState<"login"|"register">("login");
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [displayName,setDisplayName]=useState("");
  const [invitation,setInvitation]=useState("");
  const [authError,setAuthError]=useState("");

  const resetBrowserProject=useCallback(()=>{
    // Browser backups from another session must not reveal the previous
    // user's boundary. Durable project data remain in the owner's SQLite.
    try{
      window.localStorage.removeItem(ACTIVE_PROJECT_KEY);
      window.localStorage.removeItem(SITE_STORAGE_KEY);
    }catch{/* Private mode may block browser storage. */}
  },[]);

  useEffect(()=>{
    let mounted=true;
    const bootstrap=async()=>{
      if(!API_BASE){if(mounted){setChecking(false);setAuthError("GIS backend belum disambungkan. Login dan projek tidak tersedia pada website ini.");}return;}
      try{
        const result=await api<AuthResponse>("/api/auth/me");
        if(mounted){setAuthCsrf(result.csrf_token);setAccount(result.user);}
      }catch{/* 401 is expected before the first login; don't render workspace. */}
      finally{if(mounted)setChecking(false);}
    };
    void bootstrap();
    const expired=()=>{
      setAuthCsrf(null);setAccount(null);resetBrowserProject();
      setAuthError("Sesi telah tamat. Login semula untuk melindungi data projek.");
    };
    window.addEventListener("planexus:auth-expired",expired);
    return()=>{mounted=false;window.removeEventListener("planexus:auth-expired",expired);};
  },[resetBrowserProject]);

  const signIn=async()=>{
    setBusy(true);setAuthError("");
    try{
      if(mode==="register"){
        await api("/api/auth/register",{
          method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({email,password,display_name:displayName,invite_token:invitation})
        });
      }
      const result=await api<AuthResponse>("/api/auth/login",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({email,password})
      });
      resetBrowserProject();
      setAuthCsrf(result.csrf_token);setAccount(result.user);setPassword("");
      setInvitation("");
    }catch(e){setAuthError(e instanceof Error?e.message:"Login tidak berjaya.");}
    finally{setBusy(false);}
  };
  const signOut=async()=>{
    setBusy(true);setAuthError("");
    try{
      await api<void>("/api/auth/logout",{method:"POST"});
      setAuthCsrf(null);resetBrowserProject();setAccount(null);
      setPassword("");setMode("login");
    }catch(e){
      // Do not falsely announce logout if revocation failed on the server.
      setAuthError(e instanceof Error?e.message:"Tidak dapat menamatkan sesi. Cuba lagi.");
    }finally{setBusy(false);}
  };
  if(checking){
    return <main className="auth-root"><div className="auth-card"><h1>PLANEXUS AI</h1><p>Memeriksa sesi dan sambungan GIS…</p></div></main>;
  }
  if(account){
    return <>
      {authError&&<div role="alert" className="auth-alert">{authError}</div>}
      <Workspace key={account.id} user={account} onLogout={()=>void signOut()}/>
    </>;
  }
  return <main className="auth-root">
    <form className="auth-card" onSubmit={e=>{e.preventDefault();void signIn();}}>
      <div className="auth-mark"><ShieldCheck size={26}/> PRIVATE PLANNER WORKSPACE</div>
      <h1>PLANEXUS <span>AI</span></h1>
      <p>Akses GIS dan data projek hanya untuk akaun yang dibenarkan.</p>
      <div className="auth-choice">
        <button type="button" aria-pressed={mode==="login"} className={mode==="login"?"active":""} onClick={()=>{setMode("login");setAuthError("");}}>Login</button>
        <button type="button" aria-pressed={mode==="register"} className={mode==="register"?"active":""} onClick={()=>{setMode("register");setAuthError("");}}>Daftar dengan jemputan</button>
      </div>
      {mode==="register"&&<>
        <label htmlFor="planexus-display-name">Nama paparan</label>
        <input id="planexus-display-name" value={displayName} onChange={e=>setDisplayName(e.target.value)} autoComplete="name" required minLength={2}/>
      </>}
      <label htmlFor="planexus-email">E-mel</label>
      <input id="planexus-email" type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="username" required/>
      <label htmlFor="planexus-password">Kata laluan</label>
      <input id="planexus-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete={mode==="login"?"current-password":"new-password"} required minLength={mode==="register"?12:1}/>
      {mode==="register"&&<>
        <label htmlFor="planexus-invite">Kod jemputan sekali guna</label>
        <input id="planexus-invite" value={invitation} onChange={e=>setInvitation(e.target.value)} required autoComplete="off"/>
      </>}
      {authError&&<p className="auth-error" role="alert">{authError}</p>}
      <button type="submit" className="auth-submit" disabled={busy||!API_BASE}>
        {busy?"Memproses…":mode==="login"?"Login ke Workspace":"Daftar & Login"}
      </button>
      <p className="auth-help">Akaun pertama diwujudkan melalui arahan pentadbir pada backend. Pendaftaran seterusnya memerlukan jemputan rasmi. Sesi dilindungi oleh cookie HttpOnly dan semakan akses pelayan.</p>
    </form>
  </main>;
}
