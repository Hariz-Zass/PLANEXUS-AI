import { test, expect } from "@playwright/test";
import type { ProjectDetail, ProposalInputs, SavedProposal, ProposalCalculation, PolicyCatalog, PolicyAssessment } from "../../lib/api";

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
    "access-control-allow-credentials":"true",
    "access-control-allow-methods":"GET,POST,PUT,DELETE,PATCH,OPTIONS",
    "access-control-allow-headers":"Content-Type,X-CSRF-Token",
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
  const policyCatalog:PolicyCatalog={
    registry_version:"2026-11-02-gpp-housing-v5",
    sources:[
      {id:"gp001a_2016",title:"GP001-A National Housing 2016",year:2016,issuer:"PLANMalaysia",
        jurisdiction:"Malaysia reference",url:"https://mytownnet.planmalaysia.gov.my/ver2/gp/GPP_PERUMAHAN.pdf",
        evidence:"Jadual 2 p44-45",scope:"Reference only",status:"curated_rules"},
      {id:"perak_housing_2023",title:"Perak Housing Guidelines 2023",year:2023,issuer:"PLANMalaysia Perak",
        jurisdiction:"Perak",url:"https://planmalaysia.perak.gov.my/index.php/icon-media/muat-turun-borang/2-garis-panduan-perancangan?download=109%3Agaris-panduan-piawan-perumahan-negeri-perak-2023",
        evidence:"PR1 p5",scope:"State reference only",status:"curated_rules"},
      {id:"parking_gp011a",title:"Parking GPP",year:null,issuer:"PLANMalaysia",jurisdiction:"Verify PBT",
        url:"https://www.planmalaysia.gov.my/main/garis-panduan-perancangan",
        evidence:"Official index only",scope:"Not indexed",status:"catalog_only"}
    ],
    profiles:[{id:"none",label:"Choose",details:"Unselected"},
      {id:"national_2016",label:"National",details:"Reference"},
      {id:"perak_2023",label:"Perak",details:"State"}],
    housing_categories:[
      {id:"terrace_low_cost",label:"Rumah teres kos rendah",development_type:"terrace_housing"},
      {id:"terrace_middle",label:"Rumah teres kos sederhana",development_type:"terrace_housing"},
      {id:"terrace_high",label:"Rumah teres High (no national min)",development_type:"terrace_housing"}
    ],
    terrace_design_presets:[
      {id:"low",category:"terrace_low_cost",label:"Low 20×55",
        width_ft:20,depth_ft:55,width_m:6.096,depth_m:16.764,storeys:1,
        status:"design_starting_point_not_approval",basis:"gpp001a_low_cost",
        source_url:"https://mytownnet.planmalaysia.gov.my/ver2/gp/GPP_PERUMAHAN.pdf",
        source_page:"Jadual 2 ms44",note:"Low: national one-storey reference."},
      {id:"mid",category:"terrace_middle",label:"Mid 20×70",
        width_ft:20,depth_ft:70,width_m:6.096,depth_m:21.336,storeys:1,
        status:"design_starting_point_not_approval",basis:"real_project_example",
        source_url:"https://hims.kpkt.gov.my/files/8502/8502-4/IKLAN_BROSUR_01.pdf",
        source_page:"KPKT project brochure",note:"Mid 20×70 is a project size, not the GP001-A minimum."},
      {id:"high",category:"terrace_high",label:"High example 22×75",
        width_ft:22,depth_ft:75,width_m:6.7056,depth_m:22.86,storeys:2,
        status:"design_starting_point_not_approval",basis:"project_example",
        source_url:"https://www.kejora.gov.my/perkhidmatan/hartanah/projek-penswastaan-dan-pembangunan-bercampur-3/",
        source_page:"KEJORA example",note:"High 22×75 is an example, no high national minimum."},
    ],
    national_lot_rules:[{category:"terrace_middle",storeys:[2,3],label:"Rumah teres kos sederhana, 2-3 tingkat",
      min_width_m:5.5,min_depth_m:19.8,min_width_ft:18,min_depth_ft:65,min_floor_area_m2:null,page:44,source_id:"gp001a_2016",
      url:"https://www.planmalaysia.gov.my/uploads/content-downloads/file_20251114202120.pdf",
      max_width_m:null,max_depth_m:null}],
    perak_floor_min_sqft:{perak_affordable:1000},
    perak_layout_references:[
      {id:"service_road_width",label:"Lebar jalan perkhidmatan",value_ft:50,
        value_type:"minimum",value_m:15.24,applicability:"PR1 terrace",
        source_id:"perak_housing_2023",source_url:"https://lphp.gov.my/index.php/pekeliling-lphp/35-gp-piawaian-perumahan-negeri-perak-2023-1/file",
        source_page:"PR1, halaman bercetak 5",automated_geometry_check:false},
      {id:"front_setback_low_cost",label:"Anjakan hadapan (kos rendah)",value_ft:15,
        value_type:"stated",value_m:4.572,applicability:"PR1 low-cost terrace",
        source_id:"perak_housing_2023",source_url:"https://lphp.gov.my/index.php/pekeliling-lphp/35-gp-piawaian-perumahan-negeri-perak-2023-1/file",
        source_page:"PR1, halaman bercetak 5",automated_geometry_check:false}
    ],
    perak_market_segments:[{id:"perak_affordable",label:"Mampu milik"}],
    not_indexed:["parking_gp011a"],
    disclaimer:"Only two housing rule sources are indexed; NOT all indexed."
  };
  function assessPolicy(inputs:ProposalInputs):PolicyAssessment{
    const profile=inputs.policy_profile??"none";
    const perak=profile==="perak_2023";
    const width=inputs.lot_width_m;
    const source=policyCatalog.sources[perak?1:0];
    const checks:PolicyAssessment["checks"]=[];
    if(profile!=="none"){
      if(inputs.housing_category!=="terrace_high") checks.push({
        key:"min_lot_frontage",title:"Lebar hadapan lot minimum",type:"min",value:5.5,observed:width,
        unit:"m",result:width<5.5?"below_min":"meets_number",
        source_id:"gp001a_2016",source_title:policyCatalog.sources[0].title,
        source_url:policyCatalog.sources[0].url,source_page:"Jadual 2, muka surat bercetak 44",
        role:perak?"supplementary_national_reference":"primary_reference",binding:false,
        published_equivalent_ft:18
      });
    }
    if(perak){
      checks.push({
        key:"min_floor_area_perak",title:"Luas ruang lantai minimum",type:"min",value:92.903,
        observed:inputs.floor_area_m2??null,unit:"m²",
        result:inputs.floor_area_m2==null?"not_supplied":inputs.floor_area_m2<92.903?"below_min":"meets_number",
        source_id:source.id,source_title:source.title,source_url:source.url,source_page:"PR1, halaman bercetak 5; 1000 kps",
        role:"primary_state_reference",binding:false
      });
    }
    return {
      registry_version:policyCatalog.registry_version,profile_id:profile,
      profile_label:perak?"Perak 2023":"National GP001-A",
      status:perak&&inputs.floor_area_m2!=null&&inputs.floor_area_m2<92.903?"outside_numeric_reference":
        !perak&&width<5.5&&inputs.housing_category!=="terrace_high"?"outside_numeric_reference":"more_inputs_needed",
      checks,reference_only:true,warnings:["Test fixtures; no approval"],
      max_lot_width_m:null,max_lot_depth_m:null,
      message:"Minimum reference sizes only; no statutory maximum lot dimensions entered."
    };
  }
  await page.addInitScript(id=>localStorage.setItem("planexus:active-project:v1",id),PROJECT_ID);
  await page.route("http://localhost:8000/api/**",async route=>{
    const request=route.request();
    const method=request.method();
    const path=new URL(request.url()).pathname;
    const respond=async(status:number,data:unknown)=>route.fulfill({status,headers:cors,json:data});
    if(method==="OPTIONS"){await route.fulfill({status:204,headers:cors});return;}
    if(path==="/api/auth/me"){await respond(200,{user:{id:"fixture-user",email:"fixture@planexus.test",display_name:"Fixture Planner",role:"planner"},csrf_token:"synthetic-ci-csrf"});return;}
    if(path==="/api/health"){await respond(200,{status:"ok"});return;}
    if(path==="/api/policy/catalog"&&method==="GET"){await respond(200,policyCatalog);return;}
    if(path==="/api/policy/assess"&&method==="POST"){
      await respond(200,assessPolicy(request.postDataJSON() as ProposalInputs));return;
    }
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
  await expect(page.locator(".proposal-hero-number")).toContainText("6.503");
  await expect(page.locator(".proposal-hero-number")).toContainText("ha");
  await expect(page.locator(".proposal-result-grid")).toContainText("3.902");
  await expect(page.locator(".proposal-gis-evidence")).toContainText("Save this proposal");
  const form=page.locator(".proposal-editor");
  await expect(form.getByRole("spinbutton",{name:/Lot frontage/})).toHaveValue("6.096");
  await expect(form.getByRole("spinbutton",{name:/Lot depth/})).toHaveValue("21.336");
  await expect(page.locator(".gpp-preset-card.is-active")).toContainText("20 × 70");
  await expect(page.locator(".gpp-preset-section")).toContainText("BUKAN HAD WAJIB GPP");
  await form.getByRole("button",{name:/Save scenario/}).click();
  await expect(page.locator(".proposal-scenario")).toHaveCount(1);
  await expect(page.locator(".proposal-scenario")).toContainText("300");
  await expect(page.locator(".proposal-success")).toContainText("Scenario saved");
  await page.reload();
  await page.getByRole("button",{name:/Development Studio/}).click();
  await expect(page.locator(".proposal-scenario")).toHaveCount(1,{timeout:15000});
  await page.locator(".proposal-scenario").click();
  await expect(page.locator(".proposal-hero-number")).toContainText("6.503");
  await expect(form.getByRole("button",{name:/Update scenario/})).toBeEnabled();
  await form.getByRole("spinbutton",{name:/Proposed units/}).fill("1");
  await expect(page.locator(".proposal-result-grid")).toContainText("0.083");
  await expect(page.locator(".proposal-gis-evidence")).toContainText("Save this proposal");
  await form.getByRole("spinbutton",{name:/Proposed units/}).fill("330");
  await form.getByRole("button",{name:/Update scenario/}).click();
  await expect(page.locator(".proposal-scenario")).toContainText("330");
  await expect(page.locator(".proposal-hero-number")).toContainText("7.154");
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

  // The curated official GPP catalog exposes a national reference with page provenance.
  await form.getByRole("spinbutton",{name:/Roads and access/}).fill("20");
  await form.getByRole("combobox",{name:"GPP jurisdiction"}).selectOption("national_2016");
  await form.getByRole("combobox",{name:"GPP house category"}).selectOption("terrace_middle");
  await form.getByRole("combobox",{name:"GPP number of storeys"}).selectOption("2");
  await expect(page.locator(".gpp-suggestion")).toContainText("5.5 × 19.8");
  await page.locator(".gpp-suggestion").getByRole("button",{name:/Use GPP minimum/}).click();
  await expect(form.getByRole("spinbutton",{name:/Lot frontage/})).toHaveValue("5.5");
  await form.getByRole("spinbutton",{name:/Lot frontage/}).fill("5.2");
  await page.locator(".gpp-action").getByRole("button",{name:/Semak GPP/}).click();
  await expect(page.locator(".gpp-results")).toContainText("BELOW / ABOVE NUMERIC LIMIT");
  await expect(page.locator(".gpp-results")).toContainText("Jadual 2");
  await expect(page.locator(".gpp-results a").first()).toHaveAttribute("href",/planmalaysia.gov.my/);

  // Perak state rule: 1,000 sq ft floor area for the selected cost segment,
  // independent of national supplementary lot-frontage dimensions.
  await form.getByRole("combobox",{name:"GPP jurisdiction"}).selectOption("perak_2023");
  await form.getByRole("combobox",{name:"Perak housing segment"}).selectOption("perak_affordable");
  await form.getByRole("spinbutton",{name:"GPP proposed floor area"}).fill("90");
  await page.locator(".gpp-action").getByRole("button",{name:/Semak GPP/}).click();
  await expect(page.locator(".gpp-results")).toContainText("Luas ruang lantai minimum");
  await expect(page.locator(".gpp-results")).toContainText("Outside range");
  await expect(page.locator(".gpp-manual-layout")).toContainText("Lebar jalan perkhidmatan");
  await expect(page.locator(".gpp-manual-layout")).toContainText("50′");
  await expect(page.locator(".gpp-manual-layout")).toContainText("NOT AUTOMATICALLY CHECKED");
  // The high cost choice is explicitly an assumption, not a fake national GPP limit.
  await page.locator(".gpp-preset-card").filter({hasText:"HIGH / PREMIUM"}).click();
  await expect(form.getByRole("spinbutton",{name:/Lot frontage/})).toHaveValue("6.7056");
  await expect(form.getByRole("spinbutton",{name:/Lot depth/})).toHaveValue("22.86");
  await expect(page.locator(".gpp-notice")).toContainText(["Saiz 22 × 75 kaki hanyalah contoh reka bentuk"]);
  await expect(page.locator(".gpp-suggestion")).toHaveCount(0);
  await page.locator(".gpp-preset-card").filter({hasText:"MID"}).click();
  await expect(form.getByRole("spinbutton",{name:/Lot frontage/})).toHaveValue("6.096");
  await expect(form.getByRole("spinbutton",{name:/Lot depth/})).toHaveValue("21.336");

  await page.getByRole("button",{name:/GPP Knowledge Registry/}).click();
  await expect(page.getByRole("heading",{name:/GPP Knowledge Registry/})).toBeVisible();
  await expect(page.locator(".gpp-library-source")).toHaveCount(3);
  await expect(page.locator(".gpp-library-source").filter({hasText:"Parking GPP"})).toContainText("SOURCE ONLY");
});
