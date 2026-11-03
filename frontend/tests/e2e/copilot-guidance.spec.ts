import { test, expect } from "@playwright/test";

test("Copilot gives honest workflow help before DEM analysis when GIS is connected", async ({ page }) => {
  const cors = {
    "access-control-allow-origin": "http://127.0.0.1:3000",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "Content-Type",
  };
  await page.route("http://localhost:8000/api/**", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") {
      await route.fulfill({status: 204, headers: cors});
      return;
    }
    const path = new URL(request.url()).pathname;
    if (path === "/api/health") {
      await route.fulfill({status:200,headers:cors,json:{status:"ok",production_ready:false}});
    } else if (path === "/api/copilot/capabilities") {
      await route.fulfill({status:200,headers:cors,json:{available:true,generative_ai_configured:false,guidance_without_analysis:true}});
    } else if (path === "/api/analyses") {
      await route.fulfill({status:200,headers:cors,json:{analyses:[]}});
    } else if (path === "/api/copilot/assess") {
      const body=request.postDataJSON() as { analysis_id: string | null; question: string };
      expect(body.analysis_id).toBeNull();
      expect(body.question.toLowerCase()).toContain("dem");
      await route.fulfill({status:200,headers:cors,json:{
        analysis_id:null,mode:"workflow_guidance",evidence:null,
        response:"**Panduan:** Belum ada analisis GIS. Lukis polygon, kemudian dapatkan DEM. Tiada fakta tapak direka.",
        notice:"Panduan sahaja, bukan AI generatif."
      }});
    } else {
      await route.fulfill({status:404,headers:cors,json:{detail:"Not mocked"}});
    }
  });

  await page.goto("/");
  await page.getByRole("button",{name:/Terrain Intelligence/}).click();
  await expect(page.getByText("GIS ENGINE CONNECTED")).toBeVisible({timeout:15000});
  await expect(page.getByText("Workflow guidance only")).toBeVisible();
  const composer = page.locator(".copilot-compose textarea");
  await expect(composer).toBeEnabled();
  await composer.fill("Bagaimana mendapatkan DEM untuk tapak saya?");
  await page.getByRole("button",{name:"Hantar soalan"}).click();
  await expect(page.getByText("PLANEXUS GUIDE")).toBeVisible({timeout:10000});
  await expect(page.getByText("Panduan sahaja, bukan AI generatif.")).toBeVisible();
  await expect(page.getByText("Lukis polygon, kemudian dapatkan DEM.",{exact:false})).toBeVisible();
});
