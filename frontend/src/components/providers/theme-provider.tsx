"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ThemeProviderProps } from "next-themes"; // ✅ corregido

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      defaultTheme="system"
      attribute="class"
      enableSystem
      enableColorScheme
      disableTransitionOnChange
      themes={props.themes ?? ["light", "dark"]}
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
