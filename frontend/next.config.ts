import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const API = process.env.JOB_BUTLER_API ?? "http://localhost:8000";

// Tailwind v4 is compiled by its Turbopack loader in every phase.
const tailwind: NextConfig["turbopack"] = {
  rules: { "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" } },
};

// Production: a static export (`out/`) served by FastAPI on one port, no Node server.
// Development: `next dev` on :3000 proxies /api to FastAPI. Static export and rewrites
// cannot be combined, so each is enabled only in its own phase.
export default function config(phase: string): NextConfig {
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    return {
      turbopack: tailwind,
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
      },
    };
  }
  return { turbopack: tailwind, output: "export", trailingSlash: true, images: { unoptimized: true } };
}
