import { expect, test } from "@playwright/test";
import path from "node:path";

// @live-api is excluded from mock-only Playwright suite.
// All requests hit a real FastAPI + Rasterio + SQLite backend.
test("actual GIS API: create/site/raster/layers/GPP/scenario/layout/reopen @live-api",async({page})=>{
  test.setTimeout(180000);
  const fixture=path.resolve(process.cwd(),"tests/fixtures/generated");
  const site="Integration Test Alpha";
  const other="Integration Test Bravo";
  await page.goto("/");
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
  await layers.getByRole("button",{name:"Slope",exact:true}).click();
  await expect(page.locator(".terrain-map[data-slope-rendered='true']")).toBeVisible({timeout:30000});
  await layers.getByRole("button",{name:"Elevation",exact:true}).click();
  await expect(page.locator(".terrain-map[data-elevation-rendered='true']")).toBeVisible({timeout:30000});
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
  await page.getByRole("button",{name:/Project Workspace/}).click();
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
  await page.getByRole("button",{name:/Project Workspace/}).click();
  await page.locator(".project-entry").filter({hasText:site}).getByRole("button",{name:/Open/}).click();
  await expect(page.locator(".active-project-text strong")).toHaveText(site,{timeout:20000});
  await expect(page.getByText("Verified Terrain Outputs")).toBeVisible({timeout:30000});
});
