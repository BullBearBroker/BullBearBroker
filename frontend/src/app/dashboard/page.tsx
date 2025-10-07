import type { Metadata } from "next";

import { DashboardPage } from "@/components/dashboard/dashboard-page";

const description =
  "Accede a indicadores técnicos, noticias relevantes y el estado de tu portafolio desde un único panel optimizado.";

export const metadata: Metadata = {
  title: "Dashboard",
  description,
  alternates: {
    canonical: "/dashboard",
  },
  openGraph: {
    title: "BullBearBroker · Panel del inversor",
    description,
    url: "/dashboard",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "BullBearBroker · Panel del inversor",
    description,
  },
};

export default function DashboardRoutePage() {
  return <DashboardPage />;
}
