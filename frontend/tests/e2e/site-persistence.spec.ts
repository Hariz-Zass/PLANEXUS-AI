import { test, expect } from "@playwright/test";

const SITE_KEY = "planexus:site-boundary:v1";
const geometry = {
  type: "Polygon",
  coordinates: [[[101.07,4.66],[101.08,4.66],[101.08,4.67],[101.07,4.67],[101.07,4.66]]]
};

async function inspectMapLayout(page: import("@playwright/test").Page) {
  await page.waitForFunction(() => document.querySelector(".terrain-map[data-site-rendered='true']") !== null, null, { timeout: 20000 });
  const layout = await page.locator(".terrain-map").evaluate(el => {
    const elements = [];
    let current: HTMLElement | null = el as HTMLElement;
    while (current && elements.length < 9) {
      const style = window.getComputedStyle(current);
      const rect = current.getBoundingClientRect();
      elements.push({
        element: current.tagName.toLowerCase(),
        classes: current.className,
        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
        display: style.display,
        visibility: style.visibility,
        position: style.position,
        overflow: style.overflow,
        opacity: style.opacity,
        maxHeight: style.maxHeight
      });
      current = current.parentElement;
    }
    return elements;
  });
  console.log("MAP LAYOUT DEBUG", JSON.stringify(layout));
}

test("restores the actual MapLibre site source after refresh and menu switch", async ({ page }) => {
  await page.addInitScript(({ key, polygon }) => {
    localStorage.setItem(key, JSON.stringify({
      version: 1, savedAt: "2026-11-02T00:00:00.000Z",
      origin: "map-drawing", geometry: polygon
    }));
  }, { key: SITE_KEY, polygon: geometry });
  await page.goto("/");
  await inspectMapLayout(page);
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({ timeout: 30000 });
  await expect(page.getByText("SITE AUTOSAVED")).toBeVisible();
  await page.reload();
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", {name:/Data Registry/}).click();
  await page.getByRole("button", {name:/Terrain Intelligence/}).click();
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({ timeout: 30000 });
  await expect(page.getByText("SITE AUTOSAVED")).toBeVisible();
});
test("saved geometry remains safe when a replacement drawing is cancelled", async ({ page }) => {
  await page.addInitScript(({ key, polygon }) => localStorage.setItem(key, JSON.stringify({
    version: 1, savedAt:"2026-11-02T00:00:00.000Z", origin:"map-drawing", geometry:polygon
  })), {key:SITE_KEY,polygon:geometry});
  await page.goto("/");
  await inspectMapLayout(page);
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({timeout:30000});
  await page.getByRole("button", {name:/Redraw site/}).click();
  await page.getByRole("button",{name:"Cancel"}).click();
  await page.reload();
  await expect(page.locator(".terrain-map[data-site-rendered='true']")).toBeVisible({timeout:30000});
});
