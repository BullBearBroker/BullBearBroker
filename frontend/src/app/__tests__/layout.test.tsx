import { render, screen } from "@testing-library/react";

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
    const layout = RootLayout({ children: <span>Contenido</span> });

    expect(layout.props.lang).toBe("es");

    const children = Array.isArray(layout.props.children)
      ? layout.props.children
      : [layout.props.children];
    const body = children.find((child: any) => child?.type === "body") as React.ReactElement;

    render(body.props.children);

    expect(screen.getByTestId("theme-provider")).toBeInTheDocument();
    expect(screen.getByTestId("auth-provider")).toBeInTheDocument();
    expect(screen.getByTestId("app-chrome")).toHaveTextContent("Contenido");
  });
});
