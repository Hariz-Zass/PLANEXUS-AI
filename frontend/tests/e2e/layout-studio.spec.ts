import { expect, test } from "@playwright/test";
import type { LayoutInputs, LayoutLine, LayoutPreview, SavedLayout, ProjectDetail } from "../../lib/api";

const ID="88888888-8888-4888-8888-000000000777";
const NOW="2026-11-02T12:00:00Z";
const SITE={
  type:"Polygon" as const,
  coordinates:[[[101.07,4.66],[101.073,4.66],[101.073,4.663],[101.07,4.663],[101.07,4.66]]],
};
const ROAD:LayoutLine={
  type:"LineString",coordinates:[[101.0715,4.6604],[101.0715,4.6626]],
};
const EMPTY:LayoutInputs={
  name:"Concept road and land envelope",
  road_centerlines:[],assumed_road_width_m:15.24,
  front_road_buffer_m:0,perimeter_offset_m:0,
  policy_profile:"none",perak_market_segment:null,
};
const NONE={type:"FeatureCollection" as const,features:[]};

function makePreview(input:LayoutInputs):LayoutPreview{
  // Intentionally synthetic UI test data. Actual UTM GIS calculations are
  // separately verified by Python integration tests.
  const roads=input.road_centerlines.length;
  const corridor=roads?+(roads*input.assumed_road_width_m*240/10000).toFixed(4):0;
  const front=roads?+(roads*2*input.front_road_buffer_m*240/10000).toFixed(4):0;
  const perimeter=input.perimeter_offset_m?0.45:0;
  const exclusions=corridor+front+perimeter;
  const layers={
    road_centerlines:{type:"FeatureCollection" as const,features:input.road_centerlines.map(line=>({
      type:"Feature" as const,properties:{kind:"mock line"},geometry:line
    }))},
    road_corridor:NONE,
    road_front_margin:NONE,
    perimeter_exclusion:NONE,
    gross_remaining:{type:"FeatureCollection" as const,features:[{
      type:"Feature" as const,properties:{label:"MOCK GIS - not real"},geometry:SITE
    }]},
    lower_slope_remaining:NONE,
  };
  const perak=input.policy_profile==="perak_2023";
  return {
    version:"1.0.0",method:"Synthetic E2E fixture, not real geometry",
    projected_crs:"EPSG:32647",site_area_ha:11.2,
    road_centerline_length_m:roads*240,road_corridor_ha:corridor,
    road_front_margin_ha:front,perimeter_exclusion_ha:perimeter,
    combined_exclusions_ha:exclusions,gross_unencumbered_ha:11.2-exclusions,
    road_count:roads,terrain_status:"no_active_suitability",terrain_source:null,
    lower_slope_overlap_ha:null,lower_slope_remaining_ha:null,
    largest_contiguous_lower_patch_ha:null,lower_patch_count:null,
    quality_status:"geometry_only",
    policy_checks:perak?[{
      key:"perak_pr1_service_road_width",
      label:"PR1 service road MINIMUM (reference)",
      document:"Perak 2023 PR1",
      source_url:"https://lphp.gov.my/index.php/pekeliling-lphp/35-gp-piawaian-perumahan-negeri-perak-2023-1/file",
      source_page:"PR1, printed p.5",minimum_m:15.24,
      entered_m:input.assumed_road_width_m,
      result:roads?(input.assumed_road_width_m<15.24?
        "entered_value_below_minimum" as const:"entered_value_meets_minimum" as const):"not_drawn" as const,
      verified_geometry:false as const,binding:false as const,
    }]:[],
    warnings:["Fixture only: no actual road widths or planning approval"],
    layers,
  };
}

test("Smart Layout saves imported road sketch, restores after refresh, and flags stale project boundaries",async({page})=>{
  test.setTimeout(130000);
  const project:ProjectDetail={
    id:ID,name:"Synthetic Layout Project (E2E)",description:"Browser fixture",
    has_site:true,geometry:SITE,site_area_ha:11.2,
    active_analysis_id:null,analyses:[],revision:1,
    created_at_utc:NOW,updated_at_utc:NOW,
  };
  let record:SavedLayout|null=null;
  let stale=false;
  const cors={
    "access-control-allow-origin":"http://127.0.0.1:3000",
    "access-control-allow-methods":"GET,POST,PATCH,PUT,DELETE,OPTIONS",
    "access-control-allow-headers":"Content-Type",
  };
  await page.addInitScript(id=>localStorage.setItem("planexus:active-project:v1",id),ID);
  await page.route("http://localhost:8000/api/**",async route=>{
    const request=route.request(),method=request.method();
    const path=new URL(request.url()).pathname;
    const respond=async(status:number,data:unknown)=>route.fulfill({status,headers:cors,json:data});
    if(method==="OPTIONS"){await route.fulfill({status:204,headers:cors});return;}
    if(path==="/api/health"){await respond(200,{status:"ok"});return;}
    if(path==="/api/copilot/capabilities"){await respond(200,{generative_ai_configured:false});return;}
    if(path==="/api/analyses"){await respond(200,{analyses:[]});return;}
    if(path==="/api/projects"&&method==="GET"){await respond(200,{projects:[project]});return;}
    if(path==="/api/projects/"+ID&&method==="GET"){await respond(200,project);return;}
    const base="/api/projects/"+ID+"/layout";
    if(path===base&&method==="GET"){
      await respond(200,record?
        {...record,site_changed:stale,preview:stale?null:makePreview(record.inputs)}:
        {project_id:ID,exists:false,revision:0,inputs:EMPTY,site_changed:false,
          analysis_changed:false,analysis_id_at_save:null,
          created_at_utc:null,updated_at_utc:null,preview:makePreview(EMPTY)});
      return;
    }
    if(path===base+"/preview"&&method==="POST"){
      const input=request.postDataJSON() as LayoutInputs;
      await respond(200,{project_id:ID,saved:false,preview:makePreview(input)});
      return;
    }
    if(path===base&&method==="PUT"){
      const body=request.postDataJSON() as {expected_revision:number;inputs:LayoutInputs};
      if(body.expected_revision!==(record?.revision??0)){
        await respond(409,{detail:"Conflict - stale revision"});return;
      }
      if(stale&&body.inputs.road_centerlines.length){
        await respond(422,{detail:"Sketch belongs to old site"});return;
      }
      stale=false;
      record={
        project_id:ID,exists:true,revision:(record?.revision??0)+1,
        inputs:body.inputs,site_changed:false,analysis_changed:false,
        analysis_id_at_save:null,created_at_utc:record?.created_at_utc??NOW,
        updated_at_utc:NOW,preview:makePreview(body.inputs),
      };
      await respond(200,record);return;
    }
    await respond(404,{detail:"No mock API handler for "+method+" "+path});
  });

  await page.goto("/");
  await page.getByRole("button",{name:/Smart Layout Studio/}).click();
  await expect(page.getByRole("heading",{name:/Smart Layout/})).toBeVisible();
  await expect(page.locator(".layout-map[data-layout-rendered='true']")).toBeVisible({timeout:30000});
  await expect(page.locator(".layout-stat-grid")).toContainText("11.200");
  await expect(page.locator(".layout-map-card")).toContainText("The road line is mapped");
  await expect(page.getByRole("button",{name:/Draw road centreline/})).toBeEnabled();
  await page.getByRole("button",{name:/Draw road centreline/}).click();
  await expect(page.locator(".layout-draw-notice")).toContainText("Double-click to finish");
  await page.locator(".layout-draw-notice").getByRole("button",{name:"Cancel"}).click();

  await page.locator('.layout-map-card input[type="file"]').setInputFiles({
    name:"road-centreline.geojson",mimeType:"application/geo+json",
    buffer:Buffer.from(JSON.stringify({
      type:"FeatureCollection",
      features:[{type:"Feature",properties:{},geometry:ROAD}]
    })),
  });
  await expect(page.locator(".layout-persistence-note")).toContainText("1 road(s)");
  await expect(page.locator(".layout-draft-flag")).toContainText("Unsaved changes");
  await page.getByRole("button",{name:"Preview layout"}).click();
  await expect(page.locator(".layout-stat-grid")).toContainText("0.366");
  await expect(page.locator(".layout-map[data-road-count='1']")).toBeVisible({timeout:30000});
  await page.getByRole("button",{name:"Save layout"}).click();
  await expect(page.locator(".proposal-success")).toContainText("Layout sketch saved");
  await expect(page.locator(".layout-persistence-note")).toContainText("revision 1");

  await page.reload();
  await page.getByRole("button",{name:/Smart Layout Studio/}).click();
  await expect(page.locator(".layout-map[data-road-count='1']")).toBeVisible({timeout:30000});
  await expect(page.locator(".layout-persistence-note")).toContainText("revision 1");
  const width=page.getByRole("spinbutton",{name:/Assumed road reservation width/});
  await width.fill("20");
  await expect(page.locator(".layout-draft-flag")).toContainText("Unsaved changes");
  await expect(page.locator(".layout-results")).toContainText("Click Preview layout");
  await page.getByRole("button",{name:"Preview layout"}).click();
  await expect(page.locator(".layout-stat-grid")).toContainText("0.480");
  await page.getByRole("combobox",{name:/GPP scope/}).selectOption("perak_2023");
  await page.getByRole("combobox",{name:/Terrace category under Perak PR1/}).selectOption("perak_middle");
  await page.getByRole("button",{name:"Preview layout"}).click();
  await expect(page.locator(".layout-policy-results")).toContainText("Perak PR1");
  await expect(page.locator(".layout-policy-results")).toContainText("Entered value meets reference");
  await expect(page.locator(".layout-policy-results a").first()).toHaveAttribute("href",/lphp.gov.my/);
  await page.getByRole("button",{name:"Save layout"}).click();
  await expect(page.locator(".layout-persistence-note")).toContainText("revision 2");

  stale=true;
  await page.reload();
  await page.getByRole("button",{name:/Smart Layout Studio/}).click();
  await expect(page.locator(".layout-blocker")).toContainText("Site boundary changed");
  await expect(page.locator(".layout-map[data-road-count='0']")).toBeVisible({timeout:30000});
  await expect(page.getByRole("button",{name:"Save layout"})).toBeDisabled();
  await page.getByRole("button",{name:/Start fresh for new boundary/}).click();
  await page.getByRole("button",{name:"Save layout"}).click();
  await expect(page.locator(".layout-persistence-note")).toContainText("revision 3");
  await expect(page.locator(".layout-persistence-note")).toContainText("0 road(s)");
});
