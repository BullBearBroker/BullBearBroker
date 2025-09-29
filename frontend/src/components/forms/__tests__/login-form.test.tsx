// [Codex] nuevo - Ajustes para los placeholders y mock de Auth
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { axe } from "jest-axe";
import { LoginForm } from "../login-form";

// Mock de useAuth
jest.mock("@/components/providers/auth-provider", () => {
  (globalThis as any).loginUserMock = jest.fn().mockResolvedValue(undefined);

  return {
    __esModule: true,
    useAuth: () => ({
      loginUser: (globalThis as any).loginUserMock,
    }),
  };
});

jest.mock("next/navigation", () => {
  (globalThis as any).pushMock = jest.fn();

  return {
    useRouter: () => ({
      push: (globalThis as any).pushMock,
      replace: jest.fn(),
      refresh: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
    }),
  };
}); // [Codex] nuevo - mock de router para componentes de Next

describe("LoginForm", () => {
  beforeEach(() => {
    (globalThis as any).loginUserMock.mockClear();
    (globalThis as any).pushMock.mockClear();
  });

  it("muestra mensajes de validación cuando el formulario está vacío", async () => {
    render(<LoginForm />);

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(
      await screen.findByText(/debe ingresar un correo válido/i)
    ).toBeInTheDocument();
    expect((globalThis as any).loginUserMock).not.toHaveBeenCalled();
  });

  it("valida longitud mínima de la contraseña", async () => {
    render(<LoginForm />);

    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(screen.getByPlaceholderText(/contraseña/i), {
      target: { value: "123" },
    });

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(
      await screen.findByText(/la contraseña debe tener al menos 6 caracteres/i)
    ).toBeInTheDocument();
    expect((globalThis as any).loginUserMock).not.toHaveBeenCalled();
  });

  it("envía los datos correctamente", async () => {
    render(<LoginForm />);

    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(screen.getByPlaceholderText(/contraseña/i), {
      target: { value: "secret123" },
    });

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    await waitFor(() =>
      expect((globalThis as any).loginUserMock).toHaveBeenCalledWith(
        "user@example.com",
        "secret123"
      )
    );
    expect((globalThis as any).pushMock).toHaveBeenCalledWith("/");

    // No hay validación de UI en este form; validamos que NO haya mensaje de error inmediato
    expect(
      screen.queryByText(/error al iniciar sesión/i)
    ).not.toBeInTheDocument();
  });

  it("muestra mensaje de error cuando la autenticación falla", async () => {
    (globalThis as any).loginUserMock.mockRejectedValueOnce(
      new Error("Credenciales inválidas")
    );

    render(<LoginForm />);

    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(screen.getByPlaceholderText(/contraseña/i), {
      target: { value: "secret123" },
    });

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(
      await screen.findByText(/credenciales inválidas/i)
    ).toBeInTheDocument();
    expect((globalThis as any).pushMock).not.toHaveBeenCalled();
  });

  it("no presenta violaciones de accesibilidad básicas", async () => {
    const { container } = render(<LoginForm />);

    expect(await axe(container)).toHaveNoViolations();
  });
});
