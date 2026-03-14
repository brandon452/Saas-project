import { PHASE_DEVELOPMENT_SERVER } from "next/constants.js"

/** @type {import("next").NextConfig} */
export default function nextConfig(phase) {
  return {
    ...(phase === PHASE_DEVELOPMENT_SERVER ? {} : {}),
    images: {
      unoptimized: true,
    },
    reactStrictMode: true,
    async rewrites() {
      return []
    },
  }
}
