import { test, expect } from "@playwright/test";

const SITE_KEY = "planexus:site-boundary:v1";
const geometry = {
  type: "Polygon",
  coordinates: [[[101.07,4.66],[101.08,4.66],[101.08,4.67],[101.07,4.67],[101.07,4.66]]]
};

test("restores the actual MapLibre site source after refresh and menu switch", async ({ page }) => {
  await page.route("**/api/auth/me",async route=>route.fulfill({
    status:200,headers:{"access-control-allow-origin":"http://127.0.0.1:3000","access-control-allow-credentials":"true"},
    json:{user:{id:"fixture-user",email:"fixture@planexus.test",display_name:"Fixture Planner",role:"planner"},csrf_token:"synthetic-ci-csrf"}
  }));
  await page.goto("/");
  await page.evaluate(({key,polygon})=>localStorage.setItem(key,JSON.stringify({
    version:1,savedAt:"2026-11-02T00:00:00.000Z",origin:"map-drawing",geometry:polygon
  })),{key:SITE_KEY,polygon:geometry});
  await page.reload();
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({ timeout: 30000 });
  await expect.poll(()=>page.locator(".terrain-map").evaluate(el=>el.clientHeight)).toBeGreaterThan(100);
  await expect(page.getByText("SITE AUTOSAVED")).toBeVisible();
  await page.reload();
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({ timeout: 30000 });
  await expect.poll(()=>page.locator(".terrain-map").evaluate(el=>el.clientHeight)).toBeGreaterThan(100);
  await page.getByRole("button", {name:/Data Registry/}).click();
  await page.getByRole("button", {name:/Terrain Intelligence/}).click();
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({ timeout: 30000 });
  await expect.poll(()=>page.locator(".terrain-map").evaluate(el=>el.clientHeight)).toBeGreaterThan(100);
  await expect(page.getByText("SITE AUTOSAVED")).toBeVisible();
});
test("saved geometry remains safe when a replacement drawing is cancelled", async ({ page }) => {
  await page.route("**/api/auth/me",async route=>route.fulfill({
    status:200,headers:{"access-control-allow-origin":"http://127.0.0.1:3000","access-control-allow-credentials":"true"},
    json:{user:{id:"fixture-user",email:"fixture@planexus.test",display_name:"Fixture Planner",role:"planner"},csrf_token:"synthetic-ci-csrf"}
  }));
  await page.goto("/");
  await page.evaluate(({key,polygon})=>localStorage.setItem(key,JSON.stringify({
    version:1,savedAt:"2026-11-02T00:00:00.000Z",origin:"map-drawing",geometry:polygon
  })),{key:SITE_KEY,polygon:geometry});
  await page.reload();
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({timeout:30000});
  await expect.poll(()=>page.locator(".terrain-map").evaluate(el=>el.clientHeight)).toBeGreaterThan(100);
  await page.getByRole("button", {name:/Redraw site/}).click();
  await page.getByRole("button",{name:"Cancel"}).click();
  await page.reload();
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({timeout:30000});
  await expect.poll(()=>page.locator(".terrain-map").evaluate(el=>el.clientHeight)).toBeGreaterThan(100);
});


test("never shows stale standalone browser boundary as a saved project when API is offline",async({page})=>{
  await page.addInitScript(()=>{
    localStorage.setItem("planexus:active-project:v1","aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
    localStorage.setItem("planexus:site-boundary:v1",JSON.stringify({
      version:1,origin:"geojson-import",savedAt:new Date().toISOString(),
      geometry:{type:"Polygon",coordinates:[[
        [101.07,4.66],[101.08,4.66],[101.08,4.67],[101.07,4.67],[101.07,4.66]
      ]]}
    }));
  });
  await page.route("**/api/**",async route=>{
    if(new URL(route.request().url()).pathname==="/api/auth/me"){
      await route.fulfill({status:200,headers:{
        "access-control-allow-origin":"http://127.0.0.1:3000",
        "access-control-allow-credentials":"true"
      },json:{user:{id:"fixture-user",email:"fixture@planexus.test",display_name:"Fixture Planner",role:"planner"},csrf_token:"synthetic-ci-csrf"}});
    }else{
      await route.abort("failed");
    }
  });
  await page.goto("/");
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.locator(".terrain-map[data-site-polygon='absent']")).toBeVisible({timeout:30000});
  await expect(page.locator(".terrain-map[data-site-rendered='false']")).toBeVisible({timeout:30000});
  await expect(page.getByText("GIS ENGINE OFFLINE")).toBeVisible({timeout:15000});
});
