import { render, screen } from "@testing-library/react";

jest.mock("next/font/google", () => ({
  Inter: () => ({ className: "mock-font" }),
}));

jest.mock("@/components/providers/auth-provider", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="auth-provider">{children}</div>
  ),
}));

jest.mock("@/components/providers/theme-provider", () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="theme-provider">{children}</div>
  ),
}));

jest.mock("@/components/layout/app-chrome", () => ({
  AppChrome: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="app-chrome">{children}</div>
  ),
}));

import RootLayout from "../layout";

describe("RootLayout", () => {
  it("envuelve el contenido con proveedores globales", () => {
    render(
      <RootLayout>
        <span>Contenido</span>
      </RootLayout>
    );

    const html = document.querySelector("html");
    expect(html).toHaveAttribute("lang", "es");
    expect(screen.getByTestId("theme-provider")).toBeInTheDocument();
    expect(screen.getByTestId("auth-provider")).toBeInTheDocument();
    expect(screen.getByTestId("app-chrome")).toHaveTextContent("Contenido");
  });
});
