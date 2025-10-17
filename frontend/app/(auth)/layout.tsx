import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "BullBearBroker | Acceso",
  description: "Gestiona tu cuenta para acceder al panel inteligente",
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      {children}
    </div>
  );
}
