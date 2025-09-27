import Link from "next/link";

export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t bg-card/60 py-4 text-sm text-muted-foreground">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center gap-2 px-4 text-center sm:flex-row sm:justify-between">
        <p>&copy; {year} BullBearBroker. Todos los derechos reservados.</p>
        <nav className="flex items-center gap-4">
          <Link href="/terminos" className="hover:text-foreground">
            Términos
          </Link>
          <Link href="/privacidad" className="hover:text-foreground">
            Privacidad
          </Link>
          <Link href="/contacto" className="hover:text-foreground">
            Contacto
          </Link>
        </nav>
      </div>
    </footer>
  );
}
