"use client";

import Link from "next/link";
import { memo, useMemo } from "react";

export const SiteFooter = memo(function SiteFooter() {
  const year = useMemo(() => new Date().getFullYear(), []);
  return (
    <footer className="border-t bg-card/60 py-4 text-sm text-muted-foreground" role="contentinfo">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center gap-2 px-4 text-center sm:flex-row sm:justify-between">
        <p>&copy; {year} BullBearBroker. Todos los derechos reservados.</p>
        <nav className="flex items-center gap-4" aria-label="Enlaces legales">
          <Link
            href="/terminos"
            className="hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Términos
          </Link>
          <Link
            href="/privacidad"
            className="hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Privacidad
          </Link>
          <Link
            href="/contacto"
            className="hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Contacto
          </Link>
        </nav>
      </div>
    </footer>
  );
});
