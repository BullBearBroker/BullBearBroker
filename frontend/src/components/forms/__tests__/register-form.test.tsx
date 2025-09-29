// [Codex] nuevo - Tests ajustados a placeholders y flujo de useAuth
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RegisterForm } from "../register-form";

// Mock de useAuth
jest.mock("@/components/providers/auth-provider", () => {
  const registerUserMock = jest.fn().mockResolvedValue(undefined);

  return {
    __esModule: true,
    useAuth: () => ({
      registerUser: registerUserMock,
    }),
    registerUserMock,
  };
});

const { registerUserMock } =
  jest.requireMock("@/components/providers/auth-provider") as {
    registerUserMock: jest.Mock;
  };

const pushMock = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: jest.fn(),
    refresh: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
  }),
})); // [Codex] nuevo - mock de router de Next

describe("RegisterForm", () => {
  beforeEach(() => {
    registerUserMock.mockClear();
    pushMock.mockClear();
  });

  it("valida campos obligatorios", async () => {
    render(<RegisterForm />);

    const submit = screen.getByRole("button", { name: /registrarse/i });
    const form = submit.closest("form");
    expect(form).toBeTruthy();
    fireEvent.submit(form!);

    expect(
      await screen.findByText(/el nombre es obligatorio/i)
    ).toBeInTheDocument();
    expect(registerUserMock).not.toHaveBeenCalled();
  });

  it("muestra error cuando el correo tiene formato inválido", async () => {
    render(<RegisterForm />);

    fireEvent.input(screen.getByPlaceholderText(/nombre/i), {
      target: { value: "Jane" },
    });
    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "usuario" },
    });
    fireEvent.input(screen.getByPlaceholderText(/^contraseña$/i), {
      target: { value: "secret123" },
    });
    fireEvent.input(screen.getByPlaceholderText(/confirmar contraseña/i), {
      target: { value: "secret123" },
    });

    const submit = screen.getByRole("button", { name: /registrarse/i });
    const form = submit.closest("form");
    expect(form).toBeTruthy();
    fireEvent.submit(form!);

    await waitFor(() => {
      expect(
        screen.getByText(/debe ingresar un correo válido/i)
      ).toBeInTheDocument();
    });
    expect(registerUserMock).not.toHaveBeenCalled();
  });

  it("muestra error cuando las contraseñas no coinciden", () => {
    render(<RegisterForm />);

    fireEvent.input(screen.getByPlaceholderText(/nombre/i), {
      target: { value: "Jane" },
    });
    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(screen.getByPlaceholderText(/^contraseña$/i), {
      target: { value: "secret123" },
    });
    fireEvent.input(screen.getByPlaceholderText(/confirmar contraseña/i), {
      target: { value: "otra" },
    });

    const submit = screen.getByRole("button", { name: /registrarse/i });
    const form = submit.closest("form");
    expect(form).toBeTruthy();
    fireEvent.submit(form!);

    expect(
      screen.getByText(/las contraseñas no coinciden/i)
    ).toBeInTheDocument();
  });

  it("envía los datos válidos", async () => {
    render(<RegisterForm />);

    fireEvent.input(screen.getByPlaceholderText(/nombre/i), {
      target: { value: "Jane" },
    });
    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(screen.getByPlaceholderText(/^contraseña$/i), {
      target: { value: "secret123" },
    });
    fireEvent.input(screen.getByPlaceholderText(/confirmar contraseña/i), {
      target: { value: "secret123" },
    });

    // Seleccionar perfil de riesgo (dejar "moderado" por defecto también es válido)
    fireEvent.change(screen.getByDisplayValue(/moderado/i), {
      target: { value: "agresivo" },
    });

    const submit = screen.getByRole("button", { name: /registrarse/i });
    const form = submit.closest("form");
    expect(form).toBeTruthy();
    fireEvent.submit(form!);

    await waitFor(() =>
      expect(registerUserMock).toHaveBeenCalledWith(
        "user@example.com",
        "secret123",
        "Jane",
        "agresivo"
      )
    );
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("muestra mensaje de error cuando el registro falla", async () => {
    registerUserMock.mockRejectedValueOnce(new Error("Duplicado"));

    render(<RegisterForm />);

    fireEvent.input(screen.getByPlaceholderText(/nombre/i), {
      target: { value: "Jane" },
    });
    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(screen.getByPlaceholderText(/^contraseña$/i), {
      target: { value: "secret123" },
    });
    fireEvent.input(screen.getByPlaceholderText(/confirmar contraseña/i), {
      target: { value: "secret123" },
    });

    const submit = screen.getByRole("button", { name: /registrarse/i });
    const form = submit.closest("form");
    expect(form).toBeTruthy();
    fireEvent.submit(form!);

    expect(await screen.findByText(/duplicado/i)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });
});
