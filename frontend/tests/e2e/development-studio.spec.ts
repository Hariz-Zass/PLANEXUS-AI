import { test, expect } from "@playwright/test";
import type { ProjectDetail, ProposalInputs, SavedProposal, ProposalCalculation } from "../../lib/api";

const PROJECT_ID="11111111-1111-4111-8111-000000000001";
const SITE={type:"Polygon" as const,coordinates:[[[101.07,4.66],[101.08,4.66],[101.08,4.67],[101.07,4.67],[101.07,4.66]]]};
const DATE="2026-11-02T05:00:00Z";

test("development scenarios are user-defined, saved, restored and visibly stale after GIS change",async({page})=>{
  test.setTimeout(120000);
  const project:ProjectDetail={
    id:PROJECT_ID,name:"Planning Sample (E2E fixture)",description:"Synthetic browser test",
    geometry:SITE,has_site:true,site_area_ha:12,active_analysis_id:null,
    analyses:[],revision:2,created_at_utc:DATE,updated_at_utc:DATE
  };
  const records=new Map<string,SavedProposal>();
  let changed=false;
  const cors={
    "access-control-allow-origin":"http://127.0.0.1:3000",
    "access-control-allow-methods":"GET,POST,PUT,DELETE,PATCH,OPTIONS",
    "access-control-allow-headers":"Content-Type",
  };

  function calculation(input:ProposalInputs):ProposalCalculation{
    const reserves=input.roads_pct+input.open_space_pct+input.facilities_pct+input.other_reserve_pct;
    const plots=input.units*input.lot_width_m*input.lot_depth_m/10000;
    const gross=plots/(1-reserves/100);
    return {
      method:"E2E mocked arithmetic only (not a GIS or planning result).",
      inputs:input,site_area_ha:12,lot_area_m2:input.lot_width_m*input.lot_depth_m,
      required_plot_area_ha:plots,reserve_total_pct:reserves,net_plots_share_pct:100-reserves,
      required_gross_area_ha:gross,
      allocations_ha:{roads_ha:gross*input.roads_pct/100,open_space_ha:gross*input.open_space_pct/100,
        facilities_ha:gross*input.facilities_pct/100,other_reserve_ha:gross*input.other_reserve_pct/100,building_plots_ha:plots},
      gross_site_density_units_per_ha:input.units/12,gross_site_area_margin_ha:12-gross,
      gross_site_area_check:gross<=12?"arithmetic_area_envelope":"gross_area_shortfall",
      screening_status:changed?"context_changed":"no_active_analysis",analysis_id:null,
      lower_constraint_cell_area_ha_est:null,lower_constraint_area_margin_ha_est:null,
      terrain_screening_cell_area_check:null,quality_warnings:["TEST FIXTURE - NOT REAL DATA"],
      conclusion:"Arithmetic scenario only; no GIS source connected.",
      not_approval:true
    };
  }
  await page.addInitScript(id=>localStorage.setItem("planexus:active-project:v1",id),PROJECT_ID);
  await page.route("http://localhost:8000/api/**",async route=>{
    const request=route.request();
    const method=request.method();
    const path=new URL(request.url()).pathname;
    const respond=async(status:number,data:unknown)=>route.fulfill({status,headers:cors,json:data});
    if(method==="OPTIONS"){await route.fulfill({status:204,headers:cors});return;}
    if(path==="/api/health"){await respond(200,{status:"ok"});return;}
    if(path==="/api/copilot/capabilities"){await respond(200,{generative_ai_configured:false});return;}
    if(path==="/api/analyses"){await respond(200,{analyses:[]});return;}
    if(path==="/api/projects"&&method==="GET"){await respond(200,{projects:[project]});return;}
    if(path==="/api/projects/"+PROJECT_ID&&method==="GET"){await respond(200,project);return;}
    const base="/api/projects/"+PROJECT_ID+"/proposals";
    if(path===base&&method==="GET"){
      await respond(200,{project_id:PROJECT_ID,project_active_analysis_id:null,storage:"mock test",proposals:[...records.values()].map(record=>({
        ...record,context_changed:changed,result:{...calculation(record.inputs),screening_status:changed?"context_changed":"no_active_analysis"}
      }))});
      return;
    }
    if(path===base&&method==="POST"){
      const input=request.postDataJSON() as ProposalInputs;
      const id="88888888-8888-4888-8888-000000000001";
      const scenario:SavedProposal={
        id,project_id:PROJECT_ID,inputs:input,revision:1,
        created_at_utc:DATE,updated_at_utc:DATE,analysis_id_at_save:null,
        context_changed:false,result:calculation(input),
      };
      records.set(id,scenario);await respond(201,scenario);return;
    }
    if(path.startsWith(base+"/")&&method==="PUT"){
      const id=path.slice(base.length+1);
      const record=records.get(id);
      if(!record){await respond(404,{detail:"No scenario"});return;}
      const payload=request.postDataJSON() as {expected_revision:number;proposal:ProposalInputs};
      if(record.revision!==payload.expected_revision){await respond(409,{detail:"Stale proposal"});return;}
      changed=false;
      const updated={...record,revision:record.revision+1,inputs:payload.proposal,
        context_changed:false,result:calculation(payload.proposal)};
      records.set(id,updated);
      await respond(200,updated);return;
    }
    if(path.startsWith(base+"/")&&method==="DELETE"){
      records.delete(path.slice(base.length+1));
      await route.fulfill({status:204,headers:cors});return;
    }
    await respond(404,{detail:"No E2E mock for "+method+" "+path});
  });

  await page.goto("/");
  await page.getByRole("button",{name:/Development Studio/}).click();
  await expect(page.getByRole("heading",{name:/Development Studio/})).toBeVisible();
  await expect(page.locator(".proposal-hero-number")).toContainText("6.000");
  await expect(page.locator(".proposal-hero-number")).toContainText("ha");
  await expect(page.locator(".proposal-insight")).toContainText("300");
  await expect(page.locator(".proposal-gis-evidence")).toContainText("Save this proposal");
  const form=page.locator(".proposal-editor");
  await form.getByRole("button",{name:/Save scenario/}).click();
  await expect(page.locator(".proposal-scenario")).toHaveCount(1);
  await expect(page.locator(".proposal-scenario")).toContainText("300");
  await expect(page.locator(".proposal-success")).toContainText("Scenario saved");
  await page.reload();
  await page.getByRole("button",{name:/Development Studio/}).click();
  await expect(page.locator(".proposal-scenario")).toHaveCount(1,{timeout:15000});
  await page.locator(".proposal-scenario").click();
  await expect(page.locator(".proposal-hero-number")).toContainText("6.000");
  await expect(form.getByRole("button",{name:/Update scenario/})).toBeEnabled();
  await form.getByRole("spinbutton",{name:/Proposed units/}).fill("1");
  await expect(page.locator(".proposal-result-grid")).toContainText("0.083");
  await expect(page.locator(".proposal-gis-evidence")).toContainText("Save this proposal");
  await form.getByRole("spinbutton",{name:/Proposed units/}).fill("330");
  await form.getByRole("button",{name:/Update scenario/}).click();
  await expect(page.locator(".proposal-scenario")).toContainText("330");
  await expect(page.locator(".proposal-hero-number")).toContainText("6.600");
  changed=true;
  await page.reload();
  await page.getByRole("button",{name:/Development Studio/}).click();
  await expect(page.locator(".proposal-scenario")).toContainText("REVIEW GIS",{timeout:15000});
  await page.locator(".proposal-scenario").click();
  await expect(page.locator(".proposal-gis-evidence")).toContainText("Site boundary or GIS analysis changed");
  await form.getByRole("button",{name:/Update scenario/}).click();
  await expect(page.locator(".proposal-scenario")).not.toContainText("REVIEW GIS");
  await expect(page.locator(".proposal-scenario")).toContainText("330");
  // Illegal allocation is blocked at the UI layer, independently of backend validation.
  await form.getByRole("spinbutton",{name:/Roads and access/}).fill("70");
  await expect(page.locator(".proposal-validation")).toContainText("less than 85%");
  await expect(form.getByRole("button",{name:/Update scenario/})).toBeDisabled();
});
