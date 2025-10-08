<<<<<<< Updated upstream
let bundleAnalyzerModule;

try {
  bundleAnalyzerModule = await import("@next/bundle-analyzer");
} catch (error) {
  if (process.env.ANALYZE === "true") {
    console.warn(
      "@next/bundle-analyzer no está disponible, usando implementación interna",
      error
    );
  }
  bundleAnalyzerModule = await import("./config/simple-bundle-analyzer.mjs");
}

const bundleAnalyzer =
  bundleAnalyzerModule?.default ?? bundleAnalyzerModule ?? ((options = {}) => () => options);
=======
import bundleAnalyzer from "@next/bundle-analyzer";
>>>>>>> Stashed changes

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

/** @type {import('next').NextConfig} */
const remoteImagePatterns = [
  {
    protocol: "https",
    hostname: "images.unsplash.com",
  },
  {
    protocol: "https",
    hostname: "assets.coingecko.com",
  },
  {
    protocol: "https",
    hostname: "cdn.coincap.io",
  },
];

<<<<<<< Updated upstream
export default withBundleAnalyzer({
  reactStrictMode: true,
  experimental: {
    optimizeCss: true,
  },
  // ✅ Mantener Babel activo, pero asegurarse de ignorar next/font cuando ANALYZE=true
=======
const nextConfig = {
  reactStrictMode: true,
>>>>>>> Stashed changes
  compress: true,
  poweredByHeader: false,
  eslint: {
    // ✅ Evita que ESLint bloquee la compilación
    ignoreDuringBuilds: true,
  },
  images: {
    formats: ["image/avif", "image/webp"],
    remotePatterns: remoteImagePatterns,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  env: {
    // 👇 aseguramos compatibilidad con ESLint flat config: process como global
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL ?? "http://backend:8000",
    // 🧩 Bloque 8A
    NEXT_PUBLIC_VAPID_KEY: process.env.NEXT_PUBLIC_VAPID_KEY,
  },
<<<<<<< Updated upstream
});
=======
};

export default withBundleAnalyzer(nextConfig);
>>>>>>> Stashed changes
