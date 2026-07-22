/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: { unoptimized: true },
  eslint: { ignoreDuringBuilds: true },
  experimental: { optimizePackageImports: ["lucide-react", "recharts"] },
  // PWA: Service Worker is registered manually via public/sw.js
};

// Bundle analysis: run `ANALYZE=true npm run build` to generate reports
if (process.env.ANALYZE) {
  try {
    const withBundleAnalyzer = require("@next/bundle-analyzer")({ enabled: true });
    module.exports = withBundleAnalyzer(nextConfig);
  } catch {}
}

module.exports = nextConfig;
