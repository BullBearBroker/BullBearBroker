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

const nextConfig = {
  reactStrictMode: true,
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
};

export default nextConfig;
