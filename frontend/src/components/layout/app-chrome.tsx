"use client";

import { ReactNode } from "react";

import { UIStateProvider } from "@/hooks/useUIState";

import { Navbar } from "./navbar";
import { SiteFooter } from "./footer";

interface AppChromeProps {
  children: ReactNode;
}

export function AppChrome({ children }: AppChromeProps) {
  return (
    <UIStateProvider>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground focus:shadow-lg"
      >
        Saltar al contenido
      </a>
      <div className="flex min-h-screen flex-col overflow-x-hidden bg-background text-foreground">
        <Navbar />
        <main id="main-content" className="flex-1 focus:outline-none">
          {children}
        </main>
        <SiteFooter />
      </div>
    </UIStateProvider>
  );
}
