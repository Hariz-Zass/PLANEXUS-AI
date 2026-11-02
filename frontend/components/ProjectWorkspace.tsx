"use client";
import { useState, type FormEvent } from "react";
import { Check, ChevronRight, Database, FolderOpen, FolderPlus, LoaderCircle, MapPin, Pencil, Save, ShieldCheck, Trash2, X } from "lucide-react";
import {getWorkspaceAccessKey,restoreWorkspaceAccessKey,type FeatureGeometry,type ProjectSummary} from "@/lib/api";

type Props = {
  projects: ProjectSummary[];
  activeId: string | null;
  geometry: FeatureGeometry | null;
  busy: boolean;
  error: string;
  storageMode:string;
  onCreate: (name:string, description:string, useCurrentBoundary:boolean)=>Promise<void>;
  onOpen: (id:string)=>Promise<void>;
  onRename: (id:string,name:string)=>Promise<void>;
  onDelete: (id:string)=>Promise<void>;
};

function projectDate(raw:string) {
  const date=new Date(raw);
  return Number.isNaN(date.getTime())?raw:new Intl.DateTimeFormat("ms-MY",{dateStyle:"medium"}).format(date);
}

export default function ProjectWorkspace({projects,activeId,geometry,busy,error,onCreate,onOpen,onRename,onDelete,storageMode}:Props) {
  const [name,setName]=useState("");
  const [description,setDescription]=useState("");
  const [includeBoundary,setIncludeBoundary]=useState(false);
  const [creating,setCreating]=useState(false);
  const [editingId,setEditingId]=useState<string|null>(null);
  const [editingName,setEditingName]=useState("");
  const [recoveryKey,setRecoveryKey]=useState("");
  const [recoveryError,setRecoveryError]=useState("");
  const [keyNotice,setKeyNotice]=useState("");
  const isCloud=storageMode==="private-blob-per-browser-key";

  async function create(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    if(name.trim().length<2||busy)return;
    try{await onCreate(name.trim(),description.trim(),includeBoundary);}
    catch{return;}
    setCreating(false);setName("");setDescription("");setIncludeBoundary(false);
  }
  async function rename(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    if(!editingId||editingName.trim().length<2||busy)return;
    try{await onRename(editingId,editingName.trim());}
    catch{return;}
    setEditingId(null);
  }

  return <section className="project-directory" aria-label="Manage PLANEXUS projects">
    <div className="eyebrow"><span className="eyebrow-dot"/> PROJECT REGISTRY <span className="eyebrow-slash">//</span> WORKSPACE 001</div>
    <div className="project-directory-heading">
      <div><h1>Project <span className="h1-accent">Workspace</span><span className="hero-title-mark">/</span></h1>
        <p>One boundary, multiple analyses. Reopen your work without drawing the same site twice.</p></div>
      <button className="btn btn-accent" disabled={busy} onClick={()=>setCreating(v=>!v)}>
        <FolderPlus size={17}/> {creating?"Hide form":"New project"}</button>
    </div>
    <div className="project-storage-status">
      <div className="project-storage-icon"><Database size={21}/></div>
      <div><strong>Persistent backend workspace</strong><span>Project records and boundaries are stored in local SQLite. Raster files and reports stay in this computer's backend data folder.</span></div>
      <span className="project-storage-local"><ShieldCheck size={13}/> {isCloud?"PRIVATE CLOUD":"LOCAL"}</span>
    </div>
    {isCloud&&<div className="workspace-recovery-panel">
      <strong>Private workspace recovery</strong>
      <p>Save your secret key securely to recover this workspace on another browser. This is not a login or team sharing system; losing the key may mean losing access.</p>
      <button type="button" className="btn btn-outline" onClick={()=>void navigator.clipboard.writeText(getWorkspaceAccessKey()).then(()=>setKeyNotice("Recovery key copied. Store it securely.")).catch(()=>setKeyNotice("Clipboard blocked. Use a secure browser context."))}>Copy workspace recovery key</button>
      <label>Restore an existing private workspace key
        <input value={recoveryKey} onChange={e=>setRecoveryKey(e.target.value)} placeholder="Paste your saved key" aria-label="Workspace recovery key"/>
      </label>
      <button type="button" className="btn btn-outline" disabled={!recoveryKey.trim()||busy} onClick={()=>{try{restoreWorkspaceAccessKey(recoveryKey);}catch(e){setRecoveryError(e instanceof Error?e.message:"Invalid key");}}}>Restore workspace</button>
      {keyNotice&&<small role="status">{keyNotice}</small>}{recoveryError&&<small role="alert">{recoveryError}</small>}
    </div>}
    {error&&<div className="project-error" role="alert">{error}</div>}
    {creating&&<form className="project-create" onSubmit={event=>{void create(event);}}>
      <div><span className="section-overline">CREATE A NEW WORKSPACE</span><h2>New terrain project</h2></div>
      <label>Project name<input value={name} minLength={2} maxLength={100} required autoFocus
        onChange={event=>setName(event.target.value)} placeholder="e.g. Meru Raya — Development Site A"/></label>
      <label>Short description (optional)<textarea rows={2} maxLength={500} value={description}
        onChange={event=>setDescription(event.target.value)} placeholder="Location or development proposal"/></label>
      {geometry&&<label className="project-check"><input type="checkbox" checked={includeBoundary}
        onChange={event=>setIncludeBoundary(event.target.checked)}/>Attach my currently displayed boundary to this project</label>}
      <div className="project-actions">
        <button type="button" className="btn btn-outline" onClick={()=>setCreating(false)}><X size={15}/> Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={busy||name.trim().length<2}>
          {busy?<LoaderCircle size={16} className="spin"/>:<Save size={16}/>} Create & open</button>
      </div>
    </form>}
    <div className="projects-title-row"><h2>Saved projects <span>({projects.length})</span></h2><small>Recently updated first</small></div>
    <div className="project-list">
      {!projects.length&&<div className="projects-empty"><FolderOpen size={33}/><h3>No saved projects yet</h3>
        <p>Create a workspace to keep your site boundary and terrain analyses together.</p>
        <button className="btn btn-primary" onClick={()=>setCreating(true)} disabled={busy}><FolderPlus size={16}/> Create first project</button></div>}
      {projects.map(project=><article className={"project-entry"+(project.id===activeId?" project-entry-active":"")} key={project.id}>
        <div className="project-entry-icon"><MapPin size={23}/></div>
        <div className="project-entry-body">
          {editingId===project.id?<form className="project-inline-edit" onSubmit={event=>{void rename(event);}}>
            <input aria-label={"Rename "+project.name} value={editingName} maxLength={100}
              onChange={event=>setEditingName(event.target.value)} minLength={2} required autoFocus/>
            <button type="submit" disabled={busy||editingName.trim().length<2} aria-label="Save project name"><Check size={16}/></button>
            <button type="button" onClick={()=>setEditingId(null)} aria-label="Cancel renaming"><X size={16}/></button>
          </form>:<h3>{project.name}{project.id===activeId&&<span className="project-current">OPEN</span>}</h3>}
          <p>{project.description||"No description supplied"}</p>
          <div className="project-entry-meta">
            <span><MapPin size={13}/>{project.has_site?(project.site_area_ha?.toFixed(3)??"—")+" ha · Site defined":"No site defined"}</span>
            <span>Updated {projectDate(project.updated_at_utc)}</span>
          </div>
        </div>
        <div className="project-entry-actions">
          <button className="btn btn-outline" disabled={busy||project.id===activeId}
            onClick={()=>{void onOpen(project.id);}}>{project.id===activeId?"Current":"Open"} <ChevronRight size={15}/></button>
          <button className="project-icon-action" disabled={busy} title="Rename project"
            aria-label={"Rename "+project.name} onClick={()=>{setEditingId(project.id);setEditingName(project.name);}}><Pencil size={15}/></button>
          <button className="project-icon-action project-delete" disabled={busy} title="Delete project record"
            aria-label={"Delete "+project.name} onClick={()=>{void onDelete(project.id);}}><Trash2 size={16}/></button>
        </div>
      </article>)}
    </div>
    <p className="project-footnote">Deleting a project removes its index and associations, not the archived raster/report files. This workspace does not yet support account sign-in or shared team permissions. Keep the recovery key private. Export important GIS reports and GeoJSON for independent backups.</p>
  </section>;
}
