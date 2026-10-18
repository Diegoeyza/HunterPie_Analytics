import type { NextConfig } from "next";

// Static export is opt-in (NEXT_OUTPUT=export) so the default `next build` +
// `next start` (Docker, preview) keeps working. The packaged desktop build
// sets it and is served by FastAPI on the same origin, so it must not define
// rewrites — the relative API base in lib/api.ts handles routing there.
const isExport = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = {
  // Export mode and custom routes are mutually exclusive, so the rewrites
  // (dev server / Docker proxy to FastAPI) are simply omitted when exporting.
  ...(isExport
    ? { output: "export" as const, images: { unoptimized: true } }
    : {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: "http://localhost:8000/api/:path*",
            },
          ];
        },
      }),
};

export default nextConfig;
