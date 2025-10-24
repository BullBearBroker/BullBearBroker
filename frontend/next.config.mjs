let bundleAnalyzerModule;

try {
  bundleAnalyzerModule = await import("@next/bundle-analyzer");
} catch (error) {
  if (process.env.ANALYZE === "true") {
    console.warn("@next/bundle-analyzer no está disponible, usando implementación interna", error);
  }
  bundleAnalyzerModule = await import("./config/simple-bundle-analyzer.mjs"); // CODEx: fallback local cuando el paquete no está instalado
}

const bundleAnalyzer =
  bundleAnalyzerModule?.default ??
  bundleAnalyzerModule ??
  ((options = {}) =>
    () =>
      options);

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

const nextConfig = {
  reactStrictMode: true,
  experimental: {
    optimizeCss: true,
  }, // CODEx: mantenemos optimización de CSS solicitada en la rama previa
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
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://backend:8000",
    // 🧩 Bloque 8A
    NEXT_PUBLIC_VAPID_KEY: process.env.NEXT_PUBLIC_VAPID_KEY,
  },
  // QA: CSP example – habilitar cuando la infraestructura soporte cabeceras adicionales
  // async headers() {
  //   return [
  //     {
  //       source: "/(.*)",
  //       headers: [
  //         {
  //           key: "Content-Security-Policy",
  //           value:
  //             "default-src 'self'; script-src 'self'; connect-src 'self' https://your-api.example.com; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; frame-src 'self';",
  //         },
  //       ],
  //     },
  //   ];
  // },
};

export default withBundleAnalyzer(nextConfig);
