import { PHASE_DEVELOPMENT_SERVER } from "next/constants.js"

/** @type {import("next").NextConfig} */
export default function nextConfig(phase) {
  const backendUrl =
    process.env.BACKEND_URL ??
    (phase === PHASE_DEVELOPMENT_SERVER ? "http://127.0.0.1:8000" : "")

  return {
    ...(phase === PHASE_DEVELOPMENT_SERVER ? {} : {}),
    images: {
      unoptimized: true,
    },
    reactStrictMode: true,
    skipTrailingSlashRedirect: true,
    async rewrites() {
      if (!backendUrl) return []
      return [
        {
          source: "/api/:path*",
          destination: `${backendUrl}/api/:path*/`,
        },
      ]
    },
  }
}
