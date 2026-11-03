import { expect, test } from "@playwright/test";
import path from "node:path";
import { readFileSync } from "node:fs";

// @live-api is excluded from mock-only Playwright suite.
// All requests hit a real FastAPI + Rasterio + SQLite backend.
test("actual GIS API: create/site/raster/layers/GPP/scenario/layout/reopen @live-api",async({page})=>{
  test.setTimeout(180000);
  const fixture=path.resolve(process.cwd(),"tests/fixtures/generated");
  const site="Integration Test Alpha";
  const other="Integration Test Bravo";
  await page.goto("/");
  await page.getByLabel("E-mel").fill("ci-planner@planexus.test");
  await page.getByLabel("Kata laluan").fill("Synthetic-CI-2026-Private!");
  await page.getByRole("button",{name:"Login ke Workspace"}).click();
  await expect(page.getByText("GIS ENGINE CONNECTED")).toBeVisible({timeout:30000});
  await expect(page.getByRole("button",{name:"New project"})).toBeEnabled();
  await page.getByRole("button",{name:"New project"}).click();
  await page.getByPlaceholder("e.g. Meru Raya — Development Site A").fill(site);
  await page.getByRole("button",{name:"Create & open"}).click();
  await expect(page.locator(".active-project-text strong")).toHaveText(site,{timeout:20000});
  await page.locator('input[type="file"][accept*=".geojson"]').setInputFiles(path.join(fixture,"site.geojson"));
  await expect(page.getByText("PROJECT SAVED")).toBeVisible({timeout:20000});
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({timeout:30000});

  // Actual GeoTIFF, deliberately synthetic elevation values. No API mocks.
  await page.getByRole("button",{name:/Configure Upload/}).click();
  await page.locator('input[type="file"][accept*=".tif"]').setInputFiles(path.join(fixture,"synthetic-elevation-ci.tif"));
  await page.getByPlaceholder("e.g. JUPEM site survey, 2025").fill("SYNTHETIC CI - NOT A SURVEY");
  await page.getByRole("checkbox",{name:/Saya sahkan nilai ketinggian raster/}).check();
  await page.getByRole("button",{name:"Analyse Uploaded GeoTIFF"}).click();
  await expect(page.getByText("Verified Terrain Outputs")).toBeVisible({timeout:60000});
  await expect(page.locator(".results-card")).toContainText("SYNTHETIC CI - NOT A SURVEY");
  // Site-level computation QA, SHA-256 and actual downloadable UTM rasters.
  await expect(page.getByRole("region",{name:"GIS Data Quality Review"})).toBeVisible();
  await expect(page.locator(".terrain-qa")).toContainText("Slope coverage (Horn 3×3)");
  await expect(page.locator(".terrain-qa")).toContainText("NOT YET VERIFIED");
  await expect(page.locator(".terrain-qa-provenance code")).toHaveText(/^[a-f0-9]{64}$/);
  for(const label of ["GIS QA Report (.md)","Elevation UTM (.tif)","Slope UTM (.tif)"]){
    await expect(page.getByRole("link",{name:label})).toBeVisible();
  }
  const storedQualityHref=await page.getByRole("link",{name:"GIS QA Report (.md)"}).getAttribute("href");
  expect(storedQualityHref).toContain("/api/analyses/");
  const apiResponse=await page.request.get(storedQualityHref!);
  expect(apiResponse.status()).toBe(200);
  expect(await apiResponse.text()).toContain("NOT performed");
  await expect(page.locator(".terrain-map[data-slope-features]")).toBeVisible();
  // Copilot must read the saved, actual GIS result; without an AI key it must
  // label its deterministic fallback, never fabricate measured values.
  const composer=page.locator(".copilot-compose textarea");
  await composer.fill("Apakah purata cerun tapak ini berdasarkan laporan GIS?");
  await page.getByRole("button",{name:"Hantar soalan"}).click();
  await expect(page.locator(".message-assistant").first()).toContainText("Ringkasan GIS",{timeout:20000});
  await expect(page.locator(".copilot-evidence-line")).toContainText("SYNTHETIC CI");
  // GPP Q&A is sourced from the real policy registry, not model invention.
  await composer.fill("Apakah saiz minimum rumah teres kos sederhana mengikut GPP?");
  await page.getByRole("button",{name:"Hantar soalan"}).click();
  await expect(page.locator(".gpp-chat-citations a").first()).toBeVisible({timeout:20000});
  const layers=page.locator(".map-layer-controls");
  // Measured synthetic elevation variation produces real contour lines.
  const contours=page.getByRole("checkbox",{name:"Contours"});
  await expect(contours).toBeEnabled();
  await expect(page.locator(".terrain-map[data-contours-rendered='true']")).toBeVisible({timeout:30000});
  await contours.uncheck();
  await expect(page.locator(".terrain-map[data-contours-rendered='false']")).toBeVisible({timeout:30000});
  await contours.check();
  await expect(page.locator(".terrain-map[data-contours-rendered='true']")).toBeVisible({timeout:30000});
  await layers.getByRole("button",{name:"Slope",exact:true}).click();
  await expect(page.locator(".terrain-map[data-slope-rendered='true']")).toBeVisible({timeout:30000});
  expect(Number(await page.locator(".terrain-map").getAttribute("data-slope-features"))).toBeGreaterThan(0);
  await layers.getByRole("button",{name:"Elevation",exact:true}).click();
  await expect(page.locator(".terrain-map[data-elevation-rendered='true']")).toBeVisible({timeout:30000});
  expect(Number(await page.locator(".terrain-map").getAttribute("data-elevation-features"))).toBeGreaterThan(0);
  await expect(page.locator(".terrain-map[data-slope-rendered='false']")).toBeVisible();
  await layers.getByRole("button",{name:"Suitability",exact:true}).click();
  await expect(page.locator(".terrain-map[data-suitability-rendered='true']")).toBeVisible({timeout:30000});

  await page.reload();
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.locator(".active-project-text strong")).toHaveText(site,{timeout:30000});
  await expect(page.getByText("Verified Terrain Outputs")).toBeVisible({timeout:30000});
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({timeout:30000});
  await page.getByRole("button",{name:/GPP Knowledge Registry/}).click();
  await expect(page.locator(".gpp-library-source").first()).toBeVisible({timeout:20000});

  await page.getByRole("button",{name:/Development Studio/}).click();
  await expect(page.locator(".proposal-editor")).toBeVisible({timeout:20000});
  await page.locator(".proposal-editor").getByRole("button",{name:/Save scenario/}).click();
  await expect(page.locator(".proposal-scenario")).toHaveCount(1,{timeout:20000});

  await page.getByRole("button",{name:/Smart Layout Studio/}).click();
  await expect(page.locator(".layout-map[data-layout-rendered='true']")).toBeVisible({timeout:30000});
  await page.locator('.layout-map-card input[type="file"]').setInputFiles(path.join(fixture,"road.geojson"));
  await page.getByRole("button",{name:"Preview layout"}).click();
  await expect(page.locator(".layout-map[data-road-count='1']")).toBeVisible({timeout:30000});
  await page.getByRole("button",{name:"Save layout"}).click();
  await expect(page.locator(".layout-persistence-note")).toContainText("revision 1",{timeout:20000});

  await page.reload();
  await page.getByRole("button",{name:/Development Studio/}).click();
  await expect(page.locator(".proposal-scenario")).toHaveCount(1,{timeout:20000});
  await page.getByRole("button",{name:/Smart Layout Studio/}).click();
  await expect(page.locator(".layout-map[data-road-count='1']")).toBeVisible({timeout:30000});

  // Independent project must have zero inherited layers, analyses or layouts.
  await page.getByRole("navigation",{name:"Modul PLANEXUS"}).getByRole("button",{name:/Project Workspace/}).click();
  await page.getByRole("button",{name:"New project"}).click();
  await page.getByPlaceholder("e.g. Meru Raya — Development Site A").fill(other);
  await page.getByRole("button",{name:"Create & open"}).click();
  await expect(page.locator(".active-project-text strong")).toHaveText(other,{timeout:20000});
  await expect(page.locator(".terrain-map[data-site-polygon='absent']")).toBeVisible({timeout:30000});
  await expect(page.locator(".map-layer-controls").getByRole("button",{name:"Slope",exact:true})).toBeDisabled();
  await page.getByRole("button",{name:/Development Studio/}).click();
  await expect(page.locator(".proposal-scenario")).toHaveCount(0,{timeout:20000});
  await page.getByRole("button",{name:/Smart Layout Studio/}).click();
  await expect(page.locator(".layout-studio .proposal-empty")).toContainText("Open a project with a saved site boundary",{timeout:30000});
  await page.getByRole("navigation",{name:"Modul PLANEXUS"}).getByRole("button",{name:/Project Workspace/}).click();
  await page.locator(".project-entry").filter({hasText:site}).getByRole("button",{name:/Open/}).click();
  await expect(page.locator(".active-project-text strong")).toHaveText(site,{timeout:20000});
  await expect(page.getByText("Verified Terrain Outputs")).toBeVisible({timeout:30000});
});


test("project-first navigation fits a phone @live-api",async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto("/");
  await page.getByLabel("E-mel").fill("ci-planner@planexus.test");
  await page.getByLabel("Kata laluan").fill("Synthetic-CI-2026-Private!");
  await page.getByRole("button",{name:"Login ke Workspace"}).click();
  // Mobile hides the desktop status text; actual New Project readiness
  // verifies that the API health probe has succeeded on this viewport.
  await expect(page.getByRole("button",{name:"New project"})).toBeEnabled({timeout:30000});
  await expect(page.getByRole("heading",{name:/Project Workspace/})).toBeVisible({timeout:20000});
  const openNav=page.getByRole("button",{name:"Buka navigasi"});
  await expect(openNav).toBeVisible();
  await openNav.click();
  await expect(page.getByRole("navigation",{name:"Modul PLANEXUS"})).toBeVisible();
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.locator(".terrain-map")).toBeVisible({timeout:30000});
  await openNav.click();
  await page.getByRole("button",{name:/GPP Knowledge Registry/}).click();
  await expect(page.locator(".gpp-library-source").first()).toBeVisible({timeout:30000});
});


test("invite registration, logout and different accounts cannot view each other's projects @live-api",async({page},testInfo)=>{
  test.setTimeout(90000);
  const fixture=path.resolve(process.cwd(),"tests/fixtures/generated");
  const invitations=readFileSync(path.join(fixture,"ci-invites.txt"),"utf8").trim().split(/\r?\n/);
  const invite=invitations[Math.min(testInfo.retry,invitations.length-1)];
  const invitedEmail="ci-invited-"+testInfo.retry+"@planexus.test";
  const invitedPassword="Invited-Private-CI-2026-Password!";
  const projectName="Private invited planner site "+testInfo.retry;
  await page.goto("/");
  await expect(page.getByRole("button",{name:"Login ke Workspace"})).toBeVisible();
  await page.getByRole("button",{name:"Daftar dengan jemputan"}).click();
  await page.getByLabel("Nama paparan").fill("Invited Browser Planner");
  await page.getByLabel("E-mel").fill(invitedEmail);
  await page.getByLabel("Kata laluan").fill(invitedPassword);
  await page.getByLabel("Kod jemputan sekali guna").fill(invite);
  await page.getByRole("button",{name:"Daftar & Login"}).click();
  await expect(page.getByRole("button",{name:"New project"})).toBeEnabled({timeout:30000});
  await page.getByRole("button",{name:"New project"}).click();
  await page.getByPlaceholder("e.g. Meru Raya — Development Site A").fill(projectName);
  const createdResponse=page.waitForResponse(response=>
    response.url().endsWith("/api/projects") && response.request().method()==="POST"
  );
  await page.getByRole("button",{name:"Create & open"}).click();
  const privateProject=await (await createdResponse).json() as {id:string;name:string};
  expect(privateProject.name).toBe(projectName);
  await expect(page.locator(".active-project-text strong")).toHaveText(projectName,{timeout:20000});
  await page.getByRole("button",{name:"Logout"}).click();
  await expect(page.getByRole("button",{name:"Login ke Workspace"})).toBeVisible({timeout:20000});
  await page.reload();
  await expect(page.getByRole("button",{name:"Login ke Workspace"})).toBeVisible();
  await expect(page.locator(".project-entry")).toHaveCount(0);

  // A second account must see neither the private project nor its direct ID.
  await page.getByLabel("E-mel").fill("ci-planner@planexus.test");
  await page.getByLabel("Kata laluan").fill("Synthetic-CI-2026-Private!");
  await page.getByRole("button",{name:"Login ke Workspace"}).click();
  await expect(page.getByRole("button",{name:"New project"})).toBeEnabled({timeout:30000});
  // BrowserContext's API client shares the currently logged-in user's
  // cookies; directly test ownership without relying on cross-site fetch.
  const apiHost=new URL(page.url()).hostname;
  const unauthorized=await page.request.get("http://"+apiHost+":8000/api/projects/"+privateProject.id);
  expect(unauthorized.status()).toBe(404);
  await expect(page.locator(".project-entry").filter({hasText:projectName})).toHaveCount(0);
  await page.getByRole("button",{name:"Logout"}).click();

  // Original invited owner can login again and restore the project.
  await page.getByLabel("E-mel").fill(invitedEmail);
  await page.getByLabel("Kata laluan").fill(invitedPassword);
  await page.getByRole("button",{name:"Login ke Workspace"}).click();
  await expect(page.locator(".project-entry").filter({hasText:projectName})).toBeVisible({timeout:25000});
});
