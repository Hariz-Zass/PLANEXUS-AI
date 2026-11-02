import { test, expect } from "@playwright/test";

const SITE_KEY = "planexus:site-boundary:v1";
const geometry = {
  type: "Polygon",
  coordinates: [[[101.07,4.66],[101.08,4.66],[101.08,4.67],[101.07,4.67],[101.07,4.66]]]
};

test("restores the actual MapLibre site source after refresh and menu switch", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
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
  await page.goto("/");
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
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
