import { fireEvent, render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

import { Navbar } from "../navbar";

declare global {
  // eslint-disable-next-line no-var
  var mockUseAuth: jest.Mock;
}

jest.mock("@/components/providers/auth-provider", () => {
  (globalThis as any).mockUseAuth = jest.fn();

  return {
    useAuth: () => globalThis.mockUseAuth(),
  };
});

describe("Navbar", () => {
  beforeEach(() => {
    globalThis.mockUseAuth.mockReset();
  });

  it("muestra enlace de ingreso cuando no hay sesión", async () => {
    globalThis.mockUseAuth.mockReturnValue({
      user: null,
      loading: false,
      logout: jest.fn(),
    });

    render(<Navbar />);

    expect(screen.getByText(/bullbearbroker/i)).toBeInTheDocument();
    const loginLink = screen.getByRole("link", { name: /ingresar/i });
    expect(loginLink).toHaveAttribute("href", "/login");
  });

  it("muestra información del usuario y permite cerrar sesión", async () => {
    const logout = jest.fn();
    globalThis.mockUseAuth.mockReturnValue({
      user: { email: "user@example.com", name: "Jane" },
      loading: false,
      logout,
    });

    render(<Navbar />);

    expect(screen.getByText(/jane/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /cerrar sesión/i }));
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("muestra estado de carga mientras se verifica la sesión", () => {
    globalThis.mockUseAuth.mockReturnValue({
      user: null,
      loading: true,
      logout: jest.fn(),
    });

    render(<Navbar />);

    expect(screen.getByText(/verificando sesión/i)).toBeInTheDocument();
  });

  it("cumple reglas básicas de accesibilidad", async () => {
    globalThis.mockUseAuth.mockReturnValue({
      user: null,
      loading: false,
      logout: jest.fn(),
    });

    const { container } = render(<Navbar />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
