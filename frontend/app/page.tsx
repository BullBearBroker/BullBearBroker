import type { Metadata } from "next";

import { DashboardPage } from "@/components/dashboard/dashboard-page";

const description =
  "Panel financiero impulsado por IA para monitorear indicadores, noticias y tu portafolio en tiempo real.";

export const metadata: Metadata = {
  title: "Inicio",
  description,
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "BullBearBroker · Dashboard en tiempo real",
    description,
    url: "/",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "BullBearBroker · Dashboard en tiempo real",
    description,
  },
};

export default function HomePage() {
  return <DashboardPage />;
}
