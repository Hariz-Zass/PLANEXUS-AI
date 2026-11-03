import { expect, test } from "@playwright/test";
import type { ProjectDetail, TerrainReport } from "../../lib/api";

const SITE = {type:"Polygon" as const, coordinates:[[[101.07,4.66],[101.08,4.66],[101.08,4.67],[101.07,4.67],[101.07,4.66]]]};
const polygonFeature={type:"Feature" as const,properties:{class_id:1},geometry:SITE};
const contours={type:"FeatureCollection" as const,features:[]};
const now="2026-11-02T03:50:00Z";
const analysisId="44444444-4444-4444-8444-444444444444";
const report:TerrainReport={
  analysis_id:analysisId,created_at_utc:now,geometry:SITE,
  source:{id:"test-fixture",name:"E2E test DEM (mock, not real terrain)",publisher:"Test suite",
    data_type:"DSM",nominal_resolution_m:30,verified:"Synthetic fixture only"},
  metrics:{
    site_area_ha:1.23,elevation_min_m:10,elevation_mean_m:18.6,elevation_max_m:30,
    elevation_range_m:20,slope_mean_deg:4.2,slope_max_deg:10.3,
    coverage_percent_est:100,analysis_resolution_m_est:30,
    valid_elevation_pixels:120,valid_slope_pixels:120,
    slope_classes:[
      {id:1,name:"Class I",min_deg:0,max_deg:15,color:"#4cc9a3",area_ha_est:1.23,percent_of_valid_slope:100},
      {id:2,name:"Class II",min_deg:15,max_deg:25,color:"#e5c46d",area_ha_est:0,percent_of_valid_slope:0},
      {id:3,name:"Class III",min_deg:25,max_deg:35,color:"#eb8c64",area_ha_est:0,percent_of_valid_slope:0},
      {id:4,name:"Class IV",min_deg:35,max_deg:null,color:"#cb626f",area_ha_est:0,percent_of_valid_slope:0}
    ],
    contour_interval_m:5,contour_features:0,
    elevation_legend:[{class_id:1,color:"#38679B",min_m:10,max_m:30}],
    horizontal_crs:"EPSG:32647",method:"E2E fixture"
  },
  slope_geojson:{type:"FeatureCollection",features:[polygonFeature]},
  elevation_geojson:{type:"FeatureCollection",features:[polygonFeature]},
  contours_geojson:contours,
  suitability:{
    version:"1.0.0",method:"Synthetic slope-cell screening only",
    bands:[
      {id:1,key:"lower_constraint",label:"Lower terrain constraint",min_deg:0,max_deg:15,color:"#7bd99e",reason:"Fixture only",pixels:84,area_ha_est:0.861,share_of_assessed_pct:70},
      {id:2,key:"moderate_constraint",label:"Moderate terrain constraint",min_deg:15,max_deg:25,color:"#e7ca76",reason:"Fixture only",pixels:30,area_ha_est:0.307,share_of_assessed_pct:25},
      {id:3,key:"higher_constraint",label:"Higher terrain constraint",min_deg:25,max_deg:null,color:"#e78282",reason:"Fixture only",pixels:6,area_ha_est:0.062,share_of_assessed_pct:5},
      {id:4,key:"unassessed",label:"Not assessed",min_deg:null,max_deg:null,color:"#80919a",reason:"Fixture only",pixels:0,area_ha_est:0,share_of_assessed_pct:null}
    ],
    assessed_pixels:120,site_mask_pixels:120,assessed_area_ha_est:1.23,unassessed_area_ha_est:0,
    coverage_of_site_pct_est:100,area_exceeds_site_due_to_pixelization:false,source_resolution_m:30,
    class_overlay_truncated:false,
    disclaimer:"Provisional terrain screening only. Not planning permission.",
    warnings:["Synthetic fixture only, not an actual terrain determination."]
  },
  suitability_geojson:{type:"FeatureCollection",features:[{type:"Feature",properties:{class_id:1,screening_only:true},geometry:SITE}]},
  warnings:["TEST FIXTURE ONLY - NOT REAL TERRAIN."],assessment_scope:"CI UI test only"
};

test("project survives refresh, associates DEM and restores layers; site isolation after switching",async({page})=>{
  test.setTimeout(130000);
  const database=new Map<string,ProjectDetail>();
  let counter=0;
  const headers={
    "access-control-allow-origin":"http://127.0.0.1:3000",
    "access-control-allow-credentials":"true",
    "access-control-allow-methods":"GET,POST,PATCH,DELETE,OPTIONS",
    "access-control-allow-headers":"Content-Type,X-CSRF-Token"
  };
  await page.route("**/api/**",async route=>{
    const req=route.request(), method=req.method(), path=new URL(req.url()).pathname;
    const reply=async(status:number,body:unknown)=>route.fulfill({status,headers,json:body});
    if(method==="OPTIONS"){await route.fulfill({status:204,headers});return;}
    if(path==="/api/auth/me"){await reply(200,{user:{id:"fixture-user",email:"fixture@planexus.test",display_name:"Fixture Planner",role:"planner"},csrf_token:"synthetic-ci-csrf"});return;}
    if(path==="/api/health"){await reply(200,{status:"ok"});return;}
    if(path==="/api/copilot/capabilities"){await reply(200,{generative_ai_configured:false});return;}
    if(path==="/api/analyses"){await reply(200,{analyses:[]});return;}
    if(path==="/api/projects"&&method==="GET"){await reply(200,{projects:[...database.values()]});return;}
    if(path==="/api/projects"&&method==="POST"){
      const input=req.postDataJSON() as {name:string;description:string;geometry?:ProjectDetail["geometry"]};
      counter++;
      const id="11111111-1111-4111-8111-"+String(counter).padStart(12,"0");
      const value:ProjectDetail={
        id,name:input.name,description:input.description,geometry:input.geometry??null,
        has_site:Boolean(input.geometry),site_area_ha:input.geometry?1.23:null,
        active_analysis_id:null,analyses:[],revision:1,
        created_at_utc:now,updated_at_utc:now
      };
      database.set(id,value);
      await reply(201,value);
      return;
    }
    const match=path.match(/^\/api\/projects\/([^/]+)(?:\/(activate-analysis))?$/);
    if(match){
      const id=match[1], item=database.get(id);
      if(!item){await reply(404,{detail:"Project missing"});return;}
      if(method==="GET"){await reply(200,item);return;}
      if(method==="PATCH"){
        const input=req.postDataJSON() as {expected_revision:number;geometry?:ProjectDetail["geometry"];name?:string;description?:string};
        if(input.expected_revision!==item.revision){await reply(409,{detail:"Stale revision"});return;}
        if("geometry" in input) {
          item.geometry=input.geometry??null;
          item.has_site=Boolean(input.geometry);
          item.site_area_ha=input.geometry?1.23:null;
          item.active_analysis_id=null;
        }
        if(input.name)item.name=input.name;
        if(input.description!==undefined)item.description=input.description;
        item.revision++;
        item.updated_at_utc=now;
        await reply(200,item);return;
      }
      if(method==="POST"&&match[2]==="activate-analysis"){
        const {analysis_id}=req.postDataJSON() as {analysis_id:string};
        if(!item.analyses.some(a=>a.analysis_id===analysis_id)){await reply(404,{detail:"Not linked"});return;}
        item.geometry=SITE;item.has_site=true;item.active_analysis_id=analysisId;item.revision++;
        await reply(200,item);return;
      }
      if(method==="DELETE"){database.delete(id);await route.fulfill({status:204,headers});return;}
    }
    if(path==="/api/terrain/auto"&&method==="POST"){
      const input=req.postDataJSON() as {project_id?:string};
      const item=input.project_id?database.get(input.project_id):null;
      if(item){
        item.active_analysis_id=analysisId;item.revision++;
        item.analyses=[{analysis_id:analysisId,created_at_utc:now,site_area_ha:1.23,
          source_name:"E2E test DEM (mock, not real terrain)"}];
      }
      await reply(200,report);return;
    }
    if(path==="/api/analyses/"+analysisId&&method==="GET"){await reply(200,report);return;}
    await reply(404,{detail:"No mock handler for "+method+" "+path});
  });
  await page.goto("/");
  await page.getByRole("button",{name:/Project Workspace/}).click();
  await expect(page.getByText("No saved projects yet")).toBeVisible();
  await page.getByRole("button",{name:"New project"}).click();
  await page.getByPlaceholder("e.g. Meru Raya — Development Site A").fill("Terrain Site Alpha");
  await page.getByRole("button",{name:"Create & open"}).click();
  await expect(page.locator(".active-project-text strong")).toHaveText("Terrain Site Alpha");

  await page.locator('input[type="file"][accept*=".geojson"]').setInputFiles({
    name:"site.geojson",mimeType:"application/geo+json",
    buffer:Buffer.from(JSON.stringify({type:"Feature",properties:{},geometry:SITE}))
  });
  await expect(page.getByText("PROJECT SAVED")).toBeVisible({timeout:15000});
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({timeout:30000});
  await page.reload();
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.locator(".active-project-text strong")).toHaveText("Terrain Site Alpha",{timeout:15000});
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({timeout:30000});
  await expect(page.getByText("PROJECT SAVED")).toBeVisible();

  await page.getByRole("button",{name:/Get DEM & Run Analysis/}).click();
  await expect(page.getByText("Raster-Calculated Terrain Outputs")).toBeVisible({timeout:15000});
  await expect(page.getByText("4.20°")).toBeVisible();
  await expect(page.getByRole("heading",{name:/Terrain Suitability/})).toBeVisible();
  // A completed DEM starts on measured slope; suitability is opt-in.
  await expect(page.locator(".map-layer-controls").getByRole("button",{name:"Slope",exact:true})).toHaveAttribute("aria-pressed","true");
  await expect(page.locator(".terrain-map[data-slope-rendered='true']")).toBeVisible({timeout:30000});
  // A real, non-empty raster report is required: the map changes the actual
  // MapLibre visibility state, not just the highlighted toolbar button.
  await page.locator(".map-layer-controls").getByRole("button",{name:"Slope",exact:true}).click();
  await expect(page.locator(".terrain-map[data-slope-rendered='true']")).toBeVisible({timeout:30000});
  await expect(page.locator(".terrain-map[data-elevation-rendered='false']")).toBeVisible();
  await page.locator(".map-layer-controls").getByRole("button",{name:"Elevation",exact:true}).click();
  await expect(page.locator(".terrain-map[data-elevation-rendered='true']")).toBeVisible({timeout:30000});
  await expect(page.locator(".terrain-map[data-slope-rendered='false']")).toBeVisible();
  await page.locator(".map-layer-controls").getByRole("button",{name:"Suitability",exact:true}).click();
  await expect(page.locator(".terrain-map[data-suitability-rendered='true']")).toBeVisible();
  await expect(page.locator(".suitability-panel")).toContainText("Lower terrain constraint");
  await expect(page.locator(".suitability-panel")).toContainText("PRELIMINARY GIS");
  await page.reload();
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.getByText("Raster-Calculated Terrain Outputs")).toBeVisible({timeout:20000});
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({timeout:30000});
  await expect(page.locator(".terrain-map[data-slope-rendered='true']")).toBeVisible({timeout:30000});
  await page.getByRole("button",{name:/Saved Analyses/}).click();
  await expect(page.getByText("E2E test DEM (mock, not real terrain)")).toBeVisible();
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.getByText("Raster-Calculated Terrain Outputs")).toBeVisible();

  await page.getByRole("button",{name:/Project Workspace/}).click();
  await page.getByRole("button",{name:"New project"}).click();
  await page.getByPlaceholder("e.g. Meru Raya — Development Site A").fill("Terrain Site Bravo");
  await page.getByRole("button",{name:"Create & open"}).click();
  await expect(page.locator(".active-project-text strong")).toHaveText("Terrain Site Bravo");
  await expect(page.locator(".terrain-map[data-site-polygon='absent']")).toBeVisible({timeout:30000});
  await expect(page.locator(".suitability-panel")).toContainText("Awaiting verified DEM analysis");
  await expect(page.locator(".map-layer-controls").getByRole("button",{name:"Suitability",exact:true})).toBeDisabled();
  await page.reload();
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.locator(".active-project-text strong")).toHaveText("Terrain Site Bravo",{timeout:15000});
  await page.getByRole("button",{name:/Project Workspace/}).click();
  const alpha=page.locator(".project-entry").filter({hasText:"Terrain Site Alpha"});
  await alpha.getByRole("button",{name:/Open/}).click();
  await expect(page.locator(".active-project-text strong")).toHaveText("Terrain Site Alpha");
  await expect(page.getByText("Raster-Calculated Terrain Outputs")).toBeVisible({timeout:20000});
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({timeout:30000});
  await expect(page.locator(".terrain-map[data-slope-rendered='true']")).toBeVisible({timeout:30000});

  // Regression: a delayed saved-context GET must not overwrite a newer
  // live source scan, even when both belong to exactly the same project.
  let releaseOldGet=()=>{};
  let sawOldGet=false;
  const heldGet=new Promise<void>(resolve=>{releaseOldGet=()=>resolve();});
  const contextFixture=(name:string,osmId:string)=>({
    status:"retrieved",source_id:"openstreetmap-overpass-community",
    source_name:"OpenStreetMap test fixture, not official",
    source_url:"https://www.openstreetmap.org/copyright",licence:"ODbL",
    retrieved_at_utc:now,source_quality:"community_unverified_not_official",
    radius_m:1500,counts:{healthcare:1},
    named_places:[{name,category:"healthcare",distance_from_reference_point_m:200,
      osm_url:"https://www.openstreetmap.org/node/"+osmId,osm_feature_id:"node/"+osmId}],
    returned_feature_count:1,warnings:[]
  });
  await page.route("**/api/projects/*/context",async route=>{
    sawOldGet=true;
    await heldGet;
    await route.fulfill({status:200,headers,json:{
      exists:true,context:contextFixture("Old cached clinic","123")
    }});
  });
  await page.route("**/api/projects/*/context/refresh",async route=>{
    await route.fulfill({status:200,headers,json:{
      exists:true,stale_cache:false,source_refresh_failed:false,
      context:contextFixture("Fresh community clinic","456")
    }});
  });
  await page.getByRole("navigation",{name:"Modul PLANEXUS"})
    .getByRole("button",{name:/Site Context/}).click();
  await expect.poll(()=>sawOldGet).toBe(true);
  await page.getByRole("button",{name:"Imbas sekitar 1.5 km"}).click();
  await expect(page.getByText("Fresh community clinic")).toBeVisible({timeout:20000});
  releaseOldGet();
  await expect(page.getByText("Fresh community clinic")).toBeVisible();
  await expect(page.getByText("Old cached clinic")).toHaveCount(0);
});
