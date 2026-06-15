import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    externalDir: true,
  },
  outputFileTracingRoot: path.resolve(__dirname, "..", ".."),
  async rewrites() {
    const apiOrigin = process.env.MIRRORQUANT_API_ORIGIN || "http://127.0.0.1:8000";

    return [
      {
        source: "/api/:path*",
        destination: `${apiOrigin}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${apiOrigin}/health`,
      },
    ];
  },
};

export default nextConfig;
