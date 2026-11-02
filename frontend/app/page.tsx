"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity, ArrowDownToLine, ArrowRight, BarChart3, BrainCircuit, Check, CheckCircle2, ChevronDown,
  CircleAlert, CloudDownload, Compass, Database, FileCode2, FileText, FolderOpen, GitBranch,
  Globe2, Info, Layers3, LoaderCircle, Map as MapIcon, MapPin, Menu, Mountain,
  Plus, ScanSearch, Send, Settings2, ShieldCheck, Sparkles, Trash2, UploadCloud, X
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
    <div className="shell">
      <header className="topbar">
        <div className="brand-area">
          <button className="icon-button mobile-menu" onClick={() => setMobileNav(v => !v)} aria-label="Buka navigasi"><Menu size={21} /></button>
          <div className="brand-icon"><GitBranch size={24} strokeWidth={2.4} /></div>
          <div className="brand-text"><span className="brand-name">PLANEXUS <em>AI</em></span><span className="brand-sub">GEOSPATIAL PLANNING INTELLIGENCE</span></div>
        </div>
        <div className="topbar-middle"><span className="topbar-separator" /><span className="crumb">Workspace</span><span className="crumb-chevron">/</span><span className="crumb-active">Terrain Intelligence</span></div>
        <div className="topbar-right"><span className="system-indicator"><i /> Local development</span><span className="version-pill">V1 · BETA</span></div>
      </header>

      <div className="layout">
        <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
          <div className="sidebar-section-title">WORKSPACE</div>
          <nav className="nav-list" aria-label="Modul PLANEXUS">
            <button className={`nav-item ${tab === "workspace" ? "selected" : ""}`} onClick={() => { setTab("workspace"); setMobileNav(false); }}><Mountain size={18} /><span>Terrain Intelligence</span><span className="nav-on-dot" /></button>
            <button className={`nav-item ${tab === "sources" ? "selected" : ""}`} onClick={() => { setTab("sources"); setMobileNav(false); }}><Database size={18} /><span>Data Sources</span></button>
            <button className={`nav-item ${tab === "history" ? "selected" : ""}`} onClick={() => { setTab("history"); setMobileNav(false); }}><FolderOpen size={18} /><span>Saved Analyses</span>{recent.length > 0 && <span className="nav-count">{recent.length}</span>}</button>
          </nav>
          <div className="sidebar-section-title secondary-title">FUTURE MODULES</div>
          <div className="nav-list locked-modules"><div className="nav-item locked"><Globe2 size={17} /><span>Site Context</span><span>SOON</span></div><div className="nav-item locked"><FileText size={17} /><span>Planning Policy</span><span>SOON</span></div><div className="nav-item locked"><GitBranch size={17} /><span>Scenario Intelligence</span><span>SOON</span></div></div>
          <div className="sidebar-bottom">
            <div className="sidebar-principle"><ShieldCheck size={18} /><div><strong>Evidence-first analysis</strong><span>No verified data, no unsupported conclusion.</span></div></div>
            <div className="sidebar-version"><span>PLANEXUS · TERRAIN ENGINE</span><span>0.1.0</span></div>
          </div>
        </aside>

        <main className="main-area">
          {tab === "workspace" && <>
            <div className="page-head">
              <div><div className="eyebrow"><span className="eyebrow-dot" /> ACTIVE MODULE / 01</div><h1>Terrain Intelligence <span className="h1-accent">.</span></h1><p>Analisis topografi berasaskan data sebenar. Dapatkan DEM, nilai cerun, dan teroka implikasi perancangan bersama AI.</p></div>
              <div className="head-actions"><button className="btn btn-subtle" onClick={() => geojsonInput.current?.click()}><UploadCloud size={16} /> Import Site</button><button className="btn btn-accent" onClick={startDraw}><Plus size={17} /> Draw Site</button></div>
            </div>
            <div className="workspace-grid">
              <section className="work-column">
                <div className="workspace-card map-card">
                  <div className="card-topline"><div className="card-title-row"><span className="card-icon"><MapIcon size={17} /></span><strong>Spatial Workspace</strong><span className="card-meta">EPSG:4326 · WGS84</span></div><div className="map-status"><i className={report ? "active" : ""} />{report ? "ANALYSIS READY" : drawing ? "DRAWING SITE" : "AWAITING SITE"}</div></div>
                  <div className="map-wrapper"><TerrainMap geometry={geometry} report={report} drawing={drawing} onSiteDrawn={onSiteDrawn} onPointCount={setDrawPoints} resetCounter={resetCounter} />
                    {!geometry && !drawing && <div className="map-empty"><div className="map-empty-icon"><ScanSearch size={26}/></div><strong>Start with your site boundary</strong><span>Draw a polygon on the map or import a GeoJSON file. No sample data is invented.</span><button className="btn btn-accent" onClick={startDraw}><Plus size={15} /> Draw site polygon</button></div>}
                    {drawing && <div className="drawing-notice"><MapPin size={16} /><span>Click vertices · Double-click to finish · <strong>{drawPoints} points</strong></span><button onClick={() => { setDrawing(false); setResetCounter(n=>n+1); setStatus(""); }}>Cancel</button></div>}
                    <div className="map-corner-badge"><Layers3 size={14} /> {report ? "SLOPE CLASSES" : "BASEMAP"}</div>
                  </div>
                  <div className="map-bottom"><div><span className="legend-title">SLOPE CLASSIFICATION</span><div className="legend-row"><span><i style={{ background: "#4cc9a3" }} />0–15°</span><span><i style={{ background: "#e5c46d" }} />15–25°</span><span><i style={{ background: "#eb8c64" }} />25–35°</span><span><i style={{ background: "#cb626f" }} />≥35°</span></div></div><span className="map-credit">Indicative raster analysis · Not planning approval</span></div>
                </div>
                <div className="workflow-card">
                  <div className="section-line"><div><h2>Analysis Workflow</h2><p>Mulakan dengan sempadan tapak yang sah</p></div><span className="section-tag"><Activity size={13} /> TERRAIN V1</span></div>
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
              <aside className="copilot-card"><div className="copilot-header"><div className="ai-avatar"><BrainCircuit size={22}/></div><div><h2>Planning Copilot</h2><p>Terrain Intelligence · Evidence-grounded</p></div><span className="sparkle-dot"><Sparkles size={16}/></span></div>
                <div className="copilot-stream" aria-live="polite">{chat.length === 0 && <div className="copilot-welcome"><div className="welcome-graphic"><Compass size={31}/><span className="orbit o1"/><span className="orbit o2"/></div><h3>Ask spatial questions.<br/><span>Get grounded answers.</span></h3><p>AI boleh menafsirkan keputusan GIS yang telah dikira, menerangkan implikasi cerun dan mengenal pasti maklumat perancangan yang belum disahkan.</p><div className="example-query"><span>TRY ASKING</span><button disabled={!report} onClick={() => setQuestion("Adakah tapak ini berpotensi untuk pembangunan rumah teres kos rendah berdasarkan topografi? ")}>Is this site suitable for low-cost terraced housing? <ArrowRight size={14}/></button></div></div>}
                  {chat.map((message,i) => <div key={i} className={`message ${message.role === "user" ? "message-user" : "message-assistant"}`}><div className="message-author">{message.role === "assistant" ? <><BrainCircuit size={14}/> PLANEXUS {message.mode === "llm_grounded" ? "AI" : "EVIDENCE SUMMARY"}</> : <>PLANNER</>}</div>{message.role === "assistant" ? <MarkdownParagraph text={message.text} /> : <p>{message.text}</p>}{message.notice && <div className="response-note"><Info size={13}/>{message.notice}</div>}</div>)}
                  {pending === "copilot" && <div className="thinking"><LoaderCircle className="spin" size={15}/> Processing GIS evidence…</div>}
                </div>
                <div className="copilot-compose"><div className="copilot-preset"><span>STATUS</span><span className={report ? "ready" : "unavailable"}>{report ? "GIS results available" : "Awaiting terrain analysis"}</span></div><textarea value={question} onChange={e=>setQuestion(e.target.value)} maxLength={800} placeholder="Tanya PLANEXUS tentang tapak anda…" rows={3} disabled={!report} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void askCopilot(); } }} /><div className="compose-bottom"><span><ShieldCheck size={13}/> Evidence-first</span><button className="send-button" disabled={!report || pending !== null || question.trim().length < 3} onClick={() => void askCopilot()} aria-label="Hantar soalan"><Send size={17}/></button></div></div>
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
