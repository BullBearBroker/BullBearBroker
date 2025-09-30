import { fireEvent, customRender, screen } from "@/tests/utils/renderWithProviders";
import { axe } from "jest-axe";

import { Navbar } from "../navbar";

const mockUseAuth = jest.fn();

jest.mock("@/components/providers/auth-provider", () => ({
  useAuth: () => mockUseAuth(),
}));

describe("Navbar", () => {
  beforeEach(() => {
    mockUseAuth.mockReset();
  });

  it("muestra enlace de ingreso cuando no hay sesión", async () => {
    mockUseAuth.mockReturnValue({ user: null, loading: false, logout: jest.fn() });

    customRender(<Navbar />);

    expect(screen.getByText(/bullbearbroker/i)).toBeInTheDocument();
    const loginLink = screen.getByRole("link", { name: /ingresar/i });
    expect(loginLink).toHaveAttribute("href", "/login");
  });

  it("muestra información del usuario y permite cerrar sesión", async () => {
    const logout = jest.fn();
    mockUseAuth.mockReturnValue({
      user: { email: "user@example.com", name: "Jane" },
      loading: false,
      logout,
    });

    customRender(<Navbar />);

    expect(screen.getByText(/jane/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /cerrar sesión/i }));
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("muestra estado de carga mientras se verifica la sesión", () => {
    mockUseAuth.mockReturnValue({ user: null, loading: true, logout: jest.fn() });

    customRender(<Navbar />);

    expect(screen.getByText(/verificando sesión/i)).toBeInTheDocument();
  });

  it("cumple reglas básicas de accesibilidad", async () => {
    mockUseAuth.mockReturnValue({ user: null, loading: false, logout: jest.fn() });

    const { container } = customRender(<Navbar />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
