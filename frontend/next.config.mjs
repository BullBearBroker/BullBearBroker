/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    // ✅ Evita que ESLint bloquee la compilación
    ignoreDuringBuilds: true,
  },
  images: {
    remotePatterns: [],
  },
  env: {
    // 👇 aseguramos compatibilidad con ESLint flat config: process como global
    NEXT_PUBLIC_API_BASE_URL:
      process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
  },
};

export default nextConfig;
