import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  agentRules: false,
  // Cloud Run deploy (Dockerfile): a standalone build bundles only the
  // production dependencies a request actually needs into .next/standalone,
  // instead of shipping the full node_modules tree in the runtime image.
  output: "standalone",
};

export default nextConfig;
