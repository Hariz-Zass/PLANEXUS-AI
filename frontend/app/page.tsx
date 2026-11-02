"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, ArrowDownToLine, ArrowRight, BarChart3, BrainCircuit, Check, CheckCircle2, ChevronDown,
  CircleAlert, CloudDownload, Compass, Database, FileCode2, FileText, FolderOpen, GitBranch,
  Globe2, Info, Layers3, LoaderCircle, Map as MapIcon, MapPin, Menu, Mountain,
  Plus, ScanSearch, Send, Settings2, ShieldCheck, Sparkles, Trash2, UploadCloud, X, Radar, Ruler, Crosshair, Orbit, ChevronRight, WandSparkles, CircleDot, MoveUpRight
} from "lucide-react";
import { API_BASE, api, type FeatureGeometry, type SavedSummary, type TerrainReport } from "@/lib/api";

const TerrainMap = dynamic(() => import("@/components/TerrainMap"), { ssr: false });
type SidebarTab = "workspace" | "sources" | "history";
type ChatMessage = { role: "user" | "assistant"; text: string; mode?: string; notice?: string };

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
  return geometry as FeatureGeometry;
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

export default function Home() {
  const [tab, setTab] = useState<SidebarTab>("workspace");
  const [mobileNav, setMobileNav] = useState(false);
  const [drawing, setDrawing] = useState(false);
  const [drawPoints, setDrawPoints] = useState(0);
  const [resetCounter, setResetCounter] = useState(0);
  const [geometry, setGeometry] = useState<FeatureGeometry | null>(null);
  const [report, setReport] = useState<TerrainReport | null>(null);
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
  const [question, setQuestion] = useState("Adakah tapak ini berpotensi untuk pembangunan rumah teres kos rendah berdasarkan topografi?");
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const geojsonInput = useRef<HTMLInputElement>(null);
  const tiffInput = useRef<HTMLInputElement>(null);
  const footprint = useMemo(() => geometry ? getFootprint(geometry) : null, [geometry]);
  const isHostedWithoutGIS = process.env.NODE_ENV === "production" && !process.env.NEXT_PUBLIC_API_BASE_URL;
  const footprintDisplay = geometry ? formattedNumber(report?.metrics.site_area_ha ?? footprint?.areaHa, 3) : "—";
  const perimeterDisplay = geometry ? formattedNumber(footprint?.perimeterKm, 2) : "—";

  const refreshRecent = useCallback(async () => {
    try { const results = await api<{ analyses: SavedSummary[] }>("/api/analyses"); setRecent(results.analyses); }
    catch { /* backend may be offline; shown when the user requests analysis */ }
  }, []);
  useEffect(() => { void refreshRecent(); }, [refreshRecent]);

  const onSiteDrawn = useCallback((geo: FeatureGeometry) => {
    setGeometry(geo); setReport(null); setError(""); setStatus("Sempadan tapak dilukis. Sedia untuk mendapatkan DEM."); setChat([]); setDrawing(false);
  }, []);

  function startDraw() {
    setDrawing(true); setGeometry(null); setReport(null); setChat([]); setError(""); setStatus("Klik pada peta untuk menanda sempadan, kemudian klik dua kali untuk selesai."); setResetCounter(n => n + 1);
  }

  function clearSite() {
    setDrawing(false); setGeometry(null); setReport(null); setChat([]); setError(""); setStatus(""); setResetCounter(n => n + 1);
  }

  async function loadGeoJson(file?: File) {
    if (!file) return;
    setError("");
    try {
      if (file.size > 3_000_000) throw new Error("Fail GeoJSON melebihi had 3 MB pada V1.");
      const data = JSON.parse(await file.text()) as unknown;
      const geo = normalizeGeoJSON(data);
      const inspected = await api<{ geometry: FeatureGeometry; area_ha: number }>("/api/site/inspect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ geometry: geo }) });
      setGeometry(inspected.geometry); setDrawing(false); setReport(null); setChat([]); setStatus(`Polygon diterima. Luas geodesik: ${formattedNumber(inspected.area_ha, 3)} ha.`);
    } catch (ex) { setError(ex instanceof Error ? ex.message : "Tidak dapat membaca fail GeoJSON."); }
    finally { if (geojsonInput.current) geojsonInput.current.value = ""; }
  }

  async function analyzeAuto() {
    if (!geometry || pending) return;
    setPending("auto"); setError(""); setStatus("Mendapatkan data Copernicus GLO-30 Public daripada sumber rasmi dan mengira analisis…");
    try {
      const result = await api<TerrainReport>("/api/terrain/auto", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ geometry }) });
      setReport(result); setChat([]); setStatus("Analisis GIS selesai dan disimpan. Baca amaran kualiti data sebelum menggunakan hasil.");
      void refreshRecent();
    } catch (ex) { setError(ex instanceof Error ? ex.message : "Gagal mengambil DEM. Tiada data rekaan digunakan."); setStatus(""); }
    finally { setPending(null); }
  }

  async function analyzeUploaded() {
    if (!geometry || !demFile || !sourceName.trim() || !confirmedUnits || pending) return;
    setPending("upload"); setError(""); setStatus("Memproses GeoTIFF pengguna dan mengesahkan CRS, liputan serta statistik cerun…");
    try {
      const form = new FormData();
      form.append("geometry", JSON.stringify(geometry));
      form.append("file", demFile);
      form.append("source_name", sourceName);
      form.append("vertical_unit", "metres");
      form.append("height_model", heightModel);
      form.append("vertical_datum", datum || "unknown");
      const result = await api<TerrainReport>("/api/terrain/upload", { method: "POST", body: form });
      setReport(result); setChat([]); setStatus("GeoTIFF diproses dan analisis disimpan secara lokal.");
      void refreshRecent();
    } catch (ex) { setError(ex instanceof Error ? ex.message : "Analisis GeoTIFF gagal."); setStatus(""); }
    finally { setPending(null); }
  }

  async function reopenAnalysis(id: string) {
    setPending("auto"); setError("");
    try {
      const result = await api<TerrainReport>(`/api/analyses/${id}`);
      setReport(result); setGeometry(result.geometry); setDrawing(false); setChat([]);
      setStatus(`Analisis ${id.slice(0, 8)} dibuka daripada storan lokal.`);
      setTab("workspace"); setMobileNav(false);
    } catch (ex) { setError(ex instanceof Error ? ex.message : "Tidak dapat memuatkan analisis."); }
    finally { setPending(null); }
  }

  async function askCopilot() {
    if (!report || question.trim().length < 3 || pending) return;
    const prompt = question.trim();
    setChat(messages => [...messages, { role: "user", text: prompt }]); setQuestion(""); setPending("copilot"); setError("");
    try {
      const answer = await api<{ response: string; mode: string; notice: string }>("/api/copilot/assess", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ analysis_id: report.analysis_id, question: prompt }) });
      setChat(messages => [...messages, { role: "assistant", text: answer.response, mode: answer.mode, notice: answer.notice }]);
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
        <div className="topbar-middle"><span className="topbar-separator" /><span className="crumb"><Crosshair size={13}/> COMMAND CENTER</span><ChevronRight size={13} className="crumb-chevron"/><span className="crumb-active">Terrain / Workspace</span></div>
        <div className="topbar-right">
          <span className={"system-indicator "+(isHostedWithoutGIS ? "system-offline" : "system-online")}><i /> {isHostedWithoutGIS ? "GIS ENGINE NOT CONNECTED" : "LOCAL GIS CONFIGURED"}</span>
          <span className="version-pill">DESIGN 02 <span>/</span> TERRAIN V1</span>
          <div className="user-avatar" aria-label="PLANEXUS workspace">PX</div>
        </div>
      </header>

      <div className="layout">
        <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
          <div className="sidebar-inner-title"><span className="sidebar-studio-icon"><NexusMark size={18}/></span><div><strong>Planner Studio</strong><small>GEOSPATIAL WORKSPACE</small></div></div>
          <div className="sidebar-section-title">OPERATIONAL MODULES <span>01 — 03</span></div>
          <nav className="nav-list" aria-label="Modul PLANEXUS">
            <button className={"nav-item "+(tab === "workspace" ? "selected" : "")} onClick={() => { setTab("workspace"); setMobileNav(false); }}><span className="nav-index">01</span><Mountain size={18}/><span>Terrain Intelligence</span><span className="nav-on-dot"/></button>
            <button className={"nav-item "+(tab === "sources" ? "selected" : "")} onClick={() => { setTab("sources"); setMobileNav(false); }}><span className="nav-index">02</span><Database size={18}/><span>Data Registry</span></button>
            <button className={"nav-item "+(tab === "history" ? "selected" : "")} onClick={() => { setTab("history"); setMobileNav(false); }}><span className="nav-index">03</span><FolderOpen size={18}/><span>Saved Analyses</span>{recent.length > 0 && <span className="nav-count">{recent.length}</span>}</button>
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
            <div className="sidebar-version"><span>PLANEXUS · TERRAIN ENGINE</span><span>0.1.0</span></div>
          </div>
        </aside>

        <main className="main-area">
          {tab === "workspace" && <>
            <div className="page-head page-head-v2">
              <div className="hero-copy">
                <div className="eyebrow"><span className="eyebrow-dot"/> INTELLIGENCE WORKSPACE <span className="eyebrow-slash">//</span> MODULE 001</div>
                <h1>Terrain <span className="h1-accent">Intelligence</span><span className="hero-title-mark">/</span></h1>
                <p>The terrain tells a story. <span>Understand the site, question the evidence, plan with clarity.</span></p>
              </div>
              <div className="head-actions">
                <button className="btn btn-subtle" onClick={() => geojsonInput.current?.click()}><UploadCloud size={16}/> Import GeoJSON</button>
                <button className="btn btn-accent" onClick={startDraw}><Crosshair size={17}/> Define site <ArrowRight size={15}/></button>
              </div>
            </div>
            <section className="site-ribbon" aria-label="Snapshot geospatial tapak">
              <div className="ribbon-context"><span className="ribbon-context-icon"><Radar size={24}/></span><div><small>PROJECT TELEMETRY</small><strong>{geometry ? "Site 01 / Active boundary" : "Awaiting site definition"}</strong><span>{geometry ? "Boundary available · WGS84" : "Start by drawing a real site polygon"}</span></div></div>
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
                  <div className="map-wrapper"><TerrainMap geometry={geometry} report={report} drawing={drawing} onSiteDrawn={onSiteDrawn} onPointCount={setDrawPoints} resetCounter={resetCounter} />
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
                  <div className="map-bottom"><div><span className="legend-title">TERRAIN LEGEND <span>//</span> SLOPE CLASSIFICATION {report ? "" : "· AWAITING ANALYSIS"}</span><div className="legend-row"><span><i style={{ background: "#4cc9a3" }} />0–15°</span><span><i style={{ background: "#e5c46d" }} />15–25°</span><span><i style={{ background: "#eb8c64" }} />25–35°</span><span><i style={{ background: "#cb626f" }} />≥35°</span></div></div><span className="map-credit"><ShieldCheck size={13}/> Evidence-based only · Screening, not approval</span></div>
                </div>
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
                      <button className="btn btn-primary wide" disabled={!geometry || pending !== null} onClick={() => void analyzeAuto()}>{pending === "auto" ? <LoaderCircle size={17} className="spin" /> : <ArrowRight size={16} />} {pending === "auto" ? "Retrieving & analysing…" : "Get DEM & Run Analysis"}</button>
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
                    <button className="btn btn-primary" disabled={!geometry || !demFile || !sourceName.trim() || !confirmedUnits || pending !== null} onClick={() => void analyzeUploaded()}>{pending === "upload" ? <LoaderCircle className="spin" size={16} /> : <Activity size={16}/>} Analyse Uploaded GeoTIFF</button>
                  </div>}
                </div>
                {(status || error) && <div role="status" className={`inline-notice ${error ? "notice-error" : ""}`}>{error ? <CircleAlert size={16}/> : <CheckCircle2 size={16}/>}<span>{error || status}</span>{error && <button onClick={() => setError("")} aria-label="Tutup ralat"><X size={15}/></button>}</div>}
                {report && <div className="results-card"><div className="section-line"><div><h2>Verified Terrain Outputs</h2><p>Calculated from raster data · {shortDate(report.created_at_utc)}</p></div><span className="verified-chip"><Check size={13}/> GIS CALCULATED</span></div>
                  <div className="metric-grid"><div className="metric"><span>SITE AREA</span><strong>{formattedNumber(report.metrics.site_area_ha)}</strong><small>hectares</small></div><div className="metric"><span>MEAN ELEVATION</span><strong>{formattedNumber(report.metrics.elevation_mean_m)}</strong><small>metres</small></div><div className="metric"><span>MEAN SLOPE</span><strong>{formattedNumber(report.metrics.slope_mean_deg)}°</strong><small>degrees</small></div><div className="metric"><span>DATA COVERAGE</span><strong>{formattedNumber(report.metrics.coverage_percent_est,1)}%</strong><small>estimated</small></div></div>
                  <div className="subsection-head"><strong>Slope distribution</strong><span>% of valid slope pixels</span></div>
                  <div className="slope-bar">{report.metrics.slope_classes.map(c => <div key={c.id} style={{ width: `${c.percent_of_valid_slope}%`, background: c.color }} title={`${c.name}: ${c.percent_of_valid_slope}%`} />)}</div>
                  <div className="class-results">{report.metrics.slope_classes.map(c => <div key={c.id}><span><i style={{ background: c.color }} />{c.name}</span><strong>{formattedNumber(c.percent_of_valid_slope)}%</strong><small>{formattedNumber(c.area_ha_est,3)} ha</small></div>)}</div>
                  <div className="source-card"><div className="source-icon"><ShieldCheck size={18}/></div><div><strong>Data Provenance</strong><p>{report.source.name} · {report.source.data_type}</p><span>{report.source.verified}</span>{report.source.reference && <a href={report.source.reference} target="_blank" rel="noopener noreferrer">Official dataset reference ↗</a>}</div></div>
                  <div className="limitations"><strong><CircleAlert size={16}/> Quality & scope warnings</strong>{report.warnings.map((warning,i) => <p key={i}>{warning}</p>)}</div>
                  <a className="btn btn-outline report-download" href={`${API_BASE}/api/analyses/${report.analysis_id}/report.md`}><ArrowDownToLine size={17}/> Download Evidence Report (.md)</a>
                </div>}
              </section>
              <aside className="copilot-card">
                <div className="copilot-header">
                  <div className="ai-avatar"><NexusMark size={27}/></div>
                  <div><small>THE INTELLIGENCE LAYER</small><h2>PLANEXUS <em>Copilot</em></h2><p>Spatial reasoning, grounded in GIS evidence.</p></div>
                  <span className="sparkle-dot"><WandSparkles size={19}/></span>
                </div>
                <div className="copilot-stream" aria-live="polite">
                  {chat.length === 0 && <div className="copilot-welcome">
                    <div className="copilot-orb" aria-hidden="true">
                      <span className="orb-orbit orbit-one"/><span className="orb-orbit orbit-two"/><span className="orb-orbit orbit-three"/>
                      <div className="orb-center"><BrainCircuit size={37} strokeWidth={1.3}/></div>
                      <span className="orb-satellite sat-a"/><span className="orb-satellite sat-b"/>
                    </div>
                    <div className="copilot-welcome-copy"><span className="section-overline">A SECOND MIND FOR PLANNERS</span><h3>Think beyond<br/><em>the map.</em></h3><p>Mulakan dengan data tapak yang disahkan. Copilot akan membaca hasil GIS dan membantu mentafsir implikasi topografi untuk cadangan pembangunan.</p></div>
                    <div className="copilot-checklist">
                      <div><span className={geometry ? "is-ready" : ""}>{geometry ? <Check size={12}/> : "01"}</span> Site boundary <strong>{geometry ? "READY" : "PENDING"}</strong></div>
                      <div><span className={report ? "is-ready" : ""}>{report ? <Check size={12}/> : "02"}</span> GIS evidence <strong>{report ? "READY" : "PENDING"}</strong></div>
                      <div><span className={report && !isHostedWithoutGIS ? "is-ready" : ""}>03</span> Planning response <strong>{report ? "AVAILABLE" : "LOCKED"}</strong></div>
                    </div>
                    <div className="prompt-library">
                      <div className="prompt-label"><Sparkles size={13}/> EXPLORE QUESTIONS</div>
                      <button type="button" disabled={!report} onClick={()=>setQuestion("Adakah tapak ini sesuai untuk pembangunan rumah teres berdasarkan kecerunan dan ketinggian?")}><span>Housing suitability</span><MoveUpRight size={15}/></button>
                      <button type="button" disabled={!report} onClick={()=>setQuestion("Di bahagian mana tapak ini mempunyai kekangan topografi paling ketara?")}><span>Identify terrain constraints</span><MoveUpRight size={15}/></button>
                    </div>
                  </div>}
                  {chat.map((message,i) => <div key={i} className={"message "+(message.role === "user" ? "message-user" : "message-assistant")}><div className="message-author">{message.role === "assistant" ? <><BrainCircuit size={14}/> PLANEXUS {message.mode === "llm_grounded" ? "AI" : "EVIDENCE SUMMARY"}</> : <>PLANNER</>}</div>{message.role === "assistant" ? <MarkdownParagraph text={message.text}/> : <p>{message.text}</p>}{message.notice && <div className="response-note"><Info size={13}/>{message.notice}</div>}</div>)}
                  {pending === "copilot" && <div className="thinking"><LoaderCircle className="spin" size={15}/> Analysing GIS evidence…</div>}
                </div>
                <div className="copilot-compose">
                  <div className="copilot-preset"><span><span className={"compose-led "+(report ? "lit" : "")}/> EVIDENCE STATUS</span><span className={report ? "ready" : "unavailable"}>{report ? "GIS context ready" : "Awaiting terrain analysis"}</span></div>
                  <div className="copilot-input-wrap"><textarea value={question} onChange={e=>setQuestion(e.target.value)} maxLength={800} placeholder={report ? "Ask PLANEXUS about this site…" : "Run terrain analysis to unlock Copilot…"} rows={3} disabled={!report} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void askCopilot(); } }} /><button className="send-button" disabled={!report || pending !== null || question.trim().length < 3} onClick={() => void askCopilot()} aria-label="Hantar soalan"><ArrowRight size={19}/></button></div>
                  <div className="compose-bottom"><span><ShieldCheck size={13}/> NO DATA, NO CLAIMS</span><span>POWERED BY GIS EVIDENCE</span></div>
                </div>
              </aside>
            </div>
          </>}
          {tab === "sources" && <div className="secondary-page"><div className="eyebrow"><span className="eyebrow-dot"/> SOURCE TRANSPARENCY</div><h1>Data Source Registry <span className="h1-accent">.</span></h1><p>Setiap sumber mempunyai identiti, keupayaan dan had penggunaan. Tiada dataset geospatial yang direka oleh AI.</p><div className="info-panel"><div className="info-panel-head"><span className="info-icon"><Database size={22}/></span><div><strong>Copernicus DEM GLO-30 Public</strong><span>Primary automatic retrieval source · Public Cloud Optimized GeoTIFF</span></div><span className="registry-state">ACTIVE ADAPTER</span></div><div className="detail-table"><div><span>Publisher</span><strong>Copernicus Programme / ESA</strong></div><div><span>Approx. spatial resolution</span><strong>30 m</strong></div><div><span>Raster type</span><strong>DSM (buildings and vegetation included)</strong></div><div><span>Acquisition</span><strong>Direct public AWS COG tiles, no API key</strong></div><div><span>Primary purpose</span><strong>Preliminary terrain screening</strong></div></div><a href="https://registry.opendata.aws/copernicus-dem/" target="_blank" rel="noopener noreferrer" className="source-link">Official dataset documentation <ArrowRight size={16}/></a></div><div className="quality-panel"><CircleAlert size={19}/><div><strong>Important boundary</strong><p>Satellite-derived DSM is not equivalent to surveyed bare-earth DTM. Analysis outcomes do not certify zoning, flood safety, land title, slope stability or development approval. Public coverage may differ by country and tile availability.</p></div></div><div className="workflow-card"><h2>Additional data paths</h2><p>Users can upload GeoTIFF from authorized survey providers. PLANEXUS will inspect raster CRS and available cells but cannot independently authenticate the original survey or vertical datum without its documentation.</p></div></div>}
          {tab === "history" && <div className="secondary-page"><div className="eyebrow"><span className="eyebrow-dot"/> REPRODUCIBLE OUTPUTS</div><h1>Saved Analyses <span className="h1-accent">.</span></h1><p>Hasil analisis disimpan pada direktori backend lokal. Untuk production, sambungkan persistent object storage dan authentication dahulu.</p><div className="history-list">{recent.length === 0 ? <div className="history-empty"><FolderOpen size={29}/><strong>No analyses saved yet</strong><span>Jalankan analisis pertama di Terrain Workspace.</span><button className="btn btn-primary" onClick={()=>setTab("workspace")}>Open workspace <ArrowRight size={15}/></button></div> : recent.map(item=><button key={item.analysis_id} className="history-item" onClick={()=>void reopenAnalysis(item.analysis_id)}><div className="history-icon"><BarChart3 size={19}/></div><div><strong>{item.source_name}</strong><span>{formattedNumber(item.site_area_ha,3)} ha · {shortDate(item.created_at_utc)}</span><small>{item.analysis_id}</small></div><ArrowRight size={18}/></button>)}</div></div>}
        </main>
      </div>
      <input ref={geojsonInput} hidden type="file" accept=".geojson,.json,application/geo+json,application/json" onChange={event=>void loadGeoJson(event.target.files?.[0])} />
      <input ref={tiffInput} hidden type="file" accept=".tif,.tiff,image/tiff" onChange={event=>setDemFile(event.target.files?.[0] || null)} />
    </div>
  );
}
