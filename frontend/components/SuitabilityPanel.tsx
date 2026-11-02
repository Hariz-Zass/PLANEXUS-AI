"use client";

import { ArrowUpRight, CircleAlert, Layers3, Mountain, ScanSearch, ShieldCheck } from "lucide-react";
import type { TerrainReport, TerrainSuitabilityBand } from "@/lib/api";

type Props={
  report:TerrainReport|null;
  activeOnMap:boolean;
  onShowMap:()=>void;
};

function area(value:number){return new Intl.NumberFormat("ms-MY",{maximumFractionDigits:3}).format(value);}
function percent(value:number){return new Intl.NumberFormat("ms-MY",{maximumFractionDigits:1}).format(value);}
function interval(band:TerrainSuitabilityBand){
  if(band.min_deg===null)return "No verified slope";
  if(band.max_deg===null)return band.min_deg+"° and above";
  return band.min_deg+"° to below "+band.max_deg+"°";
}

export default function SuitabilityPanel({report,activeOnMap,onShowMap}:Props){
  const screening=report?.suitability;
  const measured=screening?.bands.filter(band=>band.id<=3)??[];
  const unknown=screening?.bands.find(band=>band.id===4);
  return <section className="suitability-panel" aria-label="Terrain Suitability screening">
    <header className="suitability-heading">
      <div className="suitability-heading-copy">
        <div className="section-overline"><ScanSearch size={14}/> PHASE 05 / TERRAIN CONSTRAINTS</div>
        <h2>Terrain <em>Suitability.</em></h2>
        <p>Screen landform constraints from measured slope pixels. Not statutory suitability or building permission.</p>
      </div>
      <div className="suitability-heading-actions">
        <span className="suitability-scope-badge"><ShieldCheck size={13}/> PRELIMINARY GIS</span>
        <button className="btn btn-outline" type="button" onClick={onShowMap} disabled={!screening}
          aria-label="Show terrain suitability layer on map">
          <Layers3 size={15}/>{activeOnMap?"On map":"Show on map"}<ArrowUpRight size={13}/>
        </button>
      </div>
    </header>
    {!report ? <div className="suitability-awaiting">
      <div className="suitability-awaiting-icon"><Mountain size={27}/></div>
      <div><strong>Awaiting verified DEM analysis</strong>
        <p>Define your site and run terrain analysis. No site is classified until real raster cells have been processed.</p></div>
      <span>NO RASTER EVIDENCE</span>
    </div> : !screening ? <div className="suitability-awaiting">
      <div className="suitability-awaiting-icon"><CircleAlert size={24}/></div>
      <div><strong>Previous analysis — suitability not calculated</strong>
        <p>This stored report was generated before the Suitability Engine. Rerun DEM analysis to produce the new screening layers.</p></div>
      <span>RERUN REQUIRED</span>
    </div> : <>
      <div className="suitability-top-metrics">
        <div><small>RASTER SOURCE</small><strong>{report.source.name}</strong><span>{report.source.data_type}{screening.source_resolution_m?" · nominal "+screening.source_resolution_m+" m":""}</span></div>
        <div><small>ASSESSED CELLS</small><strong>{screening.assessed_pixels.toLocaleString("ms-MY")}</strong><span>{percent(screening.coverage_of_site_pct_est)}% estimated site coverage</span></div>
        <div><small>ASSESSMENT AREA</small><strong>{area(screening.assessed_area_ha_est)} <em>ha</em></strong><span>Full-cell raster estimate</span></div>
        <div><small>NOT ASSESSED / APPROX.</small><strong>{area(screening.unassessed_area_ha_est)} <em>ha</em></strong><span>Coverage and boundary-grid uncertainty</span></div>
      </div>
      <div className="suitability-chart-block">
        <div className="suitability-chart-head">
          <strong>Distribution of verified slope cells</strong><span>100% = assessed cells only</span>
        </div>
        <div className="suitability-stacked-bar" role="img" aria-label={"Lower terrain "+percent(measured[0]?.share_of_assessed_pct??0)+" percent; moderate "+percent(measured[1]?.share_of_assessed_pct??0)+" percent; higher "+percent(measured[2]?.share_of_assessed_pct??0)+" percent of assessed slope cells"}>
          {measured.map(band=><div key={band.id} style={{width:(band.share_of_assessed_pct??0)+"%",backgroundColor:band.color}}
            title={band.label+" — "+band.share_of_assessed_pct+"%"} />)}
        </div>
        <div className="suitability-class-grid">
          {screening.bands.map(band=><div key={band.id} className="suitability-class-item" style={{borderTopColor:band.color}}>
            <div className="suitability-class-name"><span style={{backgroundColor:band.color}}/>{band.label}</div>
            <div className="suitability-class-number">{area(band.area_ha_est)} <small>ha</small></div>
            <div className="suitability-class-caption">{interval(band)}</div>
            <div className="suitability-class-share">{band.share_of_assessed_pct===null?
              (unknown?.pixels??0)+" cells with unavailable slope" :
              percent(band.share_of_assessed_pct)+"% of assessed cells"}</div>
          </div>)}
        </div>
      </div>
      <div className="suitability-method">
        <div><ShieldCheck size={18}/><strong>Screening rule, not approval</strong></div>
        <p>0° to below 15° = lower constraint; 15° to below 25° = moderate constraint; 25° and above = higher constraint. These are provisional PLANEXUS bands, not statutory RT/GPP limits.</p>
        <p>{screening.disclaimer}</p>
        {(screening.area_exceeds_site_due_to_pixelization||screening.class_overlay_truncated||screening.coverage_of_site_pct_est<95)&&
          <p className="suitability-caution"><CircleAlert size={14}/> {screening.warnings.filter(w=>w.includes("site area")||w.includes("unassessed")||w.includes("truncated")).join(" ")||"Some cells are unassessed or the data resolution limits site-level conclusions."}</p>}
      </div>
    </>}
  </section>;
}
