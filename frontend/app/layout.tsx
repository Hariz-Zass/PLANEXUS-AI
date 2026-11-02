import type { Metadata } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import "./v2.css";
import "./site-persistence.css";
import "./workspace-projects.css";
import "./suitability.css";
import "./proposal-studio.css";
import "./gpp-library.css";
import "./smart-layout.css";

export const metadata: Metadata = {
  title: "PLANEXUS AI | Geospatial Planning Copilot",
  description: "Evidence-first terrain analysis and planning intelligence for planners.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ms"><body>{children}</body></html>;
}
