import { expect, test } from "@playwright/test";

// External-source acceptance test against real FastAPI, MapLibre, and a public
// Copernicus COG. This is NEVER mocked and must never use synthetic elevations.
// A remote source outage is a failure of the live availability gate, not a
// successful site report or a reason to substitute fictional raster values.
test("real public Copernicus DEM reaches visible slope and elevation layers @live-api", async ({page}) => {
  test.setTimeout(240000);
  const boundary = {
    type:"Polygon",
    coordinates:[[
      [101.066,4.664],[101.083,4.664],
      [101.083,4.679],[101.066,4.679],[101.066,4.664]
    ]]
  };
  await page.goto("/");
  await page.getByLabel("E-mel").fill("ci-planner@planexus.test");
  await page.getByLabel("Kata laluan").fill("Synthetic-CI-2026-Private!");
  await page.getByRole("button",{name:"Login ke Workspace"}).click();
  await expect(page.getByRole("button",{name:"New project"})).toBeEnabled({timeout:30000});
  await page.getByRole("button",{name:"New project"}).click();
  await page.getByPlaceholder("e.g. Meru Raya — Development Site A")
    .fill("Live public Meru Raya COG browser acceptance");
  await page.getByRole("button",{name:"Create & open"}).click();
  await expect(page.locator(".active-project-text strong"))
    .toContainText("Live public Meru Raya",{timeout:30000});
  await page.locator('input[type="file"][accept*=".geojson"]').setInputFiles({
    name:"meru-public-reference.geojson",
    mimeType:"application/geo+json",
    buffer:Buffer.from(JSON.stringify({type:"Feature",properties:{},geometry:boundary}))
  });
  await expect(page.getByText("PROJECT SAVED")).toBeVisible({timeout:30000});
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  const responsePromise=page.waitForResponse(r=>
    r.url().includes("/api/terrain/auto") && r.request().method()==="POST",
    {timeout:180000});
  await page.getByRole("button",{name:/Get DEM & Run Analysis/}).click();
  const response=await responsePromise;
  expect(response.status(), "Actual Copernicus endpoint must complete").toBe(200);
  const report=await response.json() as {
    source:{id:string;data_type?:string;source_tile_urls?:string[]};
    slope_geojson:{features:unknown[]};
    elevation_geojson:{features:unknown[]};
    metrics:{slope_mean_deg:number;coverage_percent_est:number}
  };
  expect(report.source.id).toMatch(/^copernicus-glo(30|90)-public$/);
  expect(report.source.source_tile_urls?.length).toBeGreaterThan(0);
  expect(report.slope_geojson.features.length).toBeGreaterThan(0);
  expect(report.elevation_geojson.features.length).toBeGreaterThan(0);
  expect(report.metrics.coverage_percent_est).toBeGreaterThan(90);
  expect(Number.isFinite(report.metrics.slope_mean_deg)).toBe(true);
  await expect(page.getByText("Raster-Calculated Terrain Outputs")).toBeVisible({timeout:30000});
  const controls=page.locator(".map-layer-controls");
  await expect(controls.getByRole("button",{name:"Slope",exact:true}))
    .toHaveAttribute("aria-pressed","true");
  await expect(page.locator(".terrain-map[data-slope-rendered='true']"))
    .toBeVisible({timeout:30000});
  await controls.getByRole("button",{name:"Elevation",exact:true}).click();
  await expect(page.locator(".terrain-map[data-elevation-rendered='true']"))
    .toBeVisible({timeout:30000});
  await page.reload();
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.getByText("Raster-Calculated Terrain Outputs"))
    .toBeVisible({timeout:30000});
  await expect(page.locator(".terrain-map[data-slope-rendered='true']"))
    .toBeVisible({timeout:30000});
});