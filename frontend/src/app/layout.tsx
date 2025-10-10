import type { Metadata } from "next";
import "@/styles/globals.css";

import { AuthProvider } from "@/components/providers/auth-provider";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { ServiceWorkerProvider } from "@/components/providers/service-worker-provider";
import { AppChrome } from "@/components/layout/app-chrome";
import { cn } from "@/lib/utils";
import { inter as sharedInter } from "@/utils/fonts";

const fallbackAppUrl = "https://bullbearbroker.app";
const metadataBase = (() => {
  try {
    const configuredUrl = process.env.NEXT_PUBLIC_APP_URL ?? fallbackAppUrl;
    return new URL(configuredUrl);
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.error("Invalid NEXT_PUBLIC_APP_URL provided", error);
    }
    return new URL(fallbackAppUrl);
  }
})();

const inter = process.env.ANALYZE === "true" ? { className: "" } : sharedInter;

const apiPreconnectOrigin = (() => {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) return null;
  try {
    return new URL(apiUrl).origin;
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("Invalid NEXT_PUBLIC_API_URL provided for preconnect", error);
    }
    return null;
  }
})();

export const metadata: Metadata = {
  metadataBase,
  title: {
    default: "BullBearBroker Dashboard",
    template: "%s | BullBearBroker",
  },
  description: "Panel financiero inteligente impulsado por IA para monitorear mercados en tiempo real.",
  applicationName: "BullBearBroker",
  alternates: {
    canonical: "/",
  },
  keywords: [
    "trading",
    "finanzas",
    "criptomonedas",
    "acciones",
    "inversiones",
    "dashboard",
  ],
  category: "finance",
  openGraph: {
    title: "BullBearBroker Dashboard",
    description:
      "Supervisa indicadores clave, noticias y alertas inteligentes para tomar mejores decisiones de inversión.",
    url: "/",
    siteName: "BullBearBroker",
    type: "website",
    locale: "es_ES",
  },
  twitter: {
    card: "summary_large_image",
    title: "BullBearBroker Dashboard",
    description:
      "Supervisa indicadores clave, noticias y alertas inteligentes para tomar mejores decisiones de inversión.",
  },
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0f172a" },
  ],
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {process.env.NODE_ENV === "production" && apiPreconnectOrigin && (
          <link rel="preconnect" href={apiPreconnectOrigin} crossOrigin="anonymous" />
        )}
        <link rel="prefetch" href="/portfolio" as="document" />
        <link rel="prefetch" href="/test-indicators" as="document" />
      </head>
      <body
        className={cn(
          inter.className,
          "min-h-screen bg-background font-sans antialiased"
        )}
      >
        <ThemeProvider>
          <AuthProvider>
            <ServiceWorkerProvider />
            <AppChrome>{children}</AppChrome>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
