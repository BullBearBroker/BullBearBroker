// [Codex] nuevo - Tests ajustados a placeholders y flujo de useAuth
import { customRender, screen, fireEvent, waitFor } from "@/tests/utils/renderWithProviders";
import { axe } from "jest-axe";
import RegisterForm from "../register-form";

// Mock de useAuth
jest.mock("@/components/providers/auth-provider", () => {
  (global as any).registerUserMock = jest
    .fn()
    .mockResolvedValue(undefined);

  return {
    __esModule: true,
    useAuth: () => ({
      registerUser: (global as any).registerUserMock,
    }),
    registerUser: (global as any).registerUserMock,
    registerUserMock: (global as any).registerUserMock,
  };
});

jest.mock("next/navigation", () => {
  (global as any).pushMock = jest.fn();

  return {
    useRouter: () => ({
      push: (global as any).pushMock,
      replace: jest.fn(),
      refresh: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
    }),
  };
}); // [Codex] nuevo - mock de router de Next

describe("RegisterForm", () => {
  beforeEach(() => {
    (global as any).registerUserMock.mockClear();
    (global as any).pushMock.mockClear();
  });

  it("valida campos obligatorios", async () => {
    customRender(<RegisterForm />);

    const submit = screen.getByRole("button", { name: /registrarse/i });
    const form = submit.closest("form");
    expect(form).toBeTruthy();
    fireEvent.submit(form!);

    expect(
      await screen.findByText(/el nombre es obligatorio/i)
    ).toBeInTheDocument();
    expect((global as any).registerUserMock).not.toHaveBeenCalled();
  });

  it("muestra error cuando el correo tiene formato inválido", async () => {
    customRender(<RegisterForm />);

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
    expect((global as any).registerUserMock).not.toHaveBeenCalled();
  });

  it("muestra error cuando las contraseñas no coinciden", () => {
    customRender(<RegisterForm />);

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
    customRender(<RegisterForm />);

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
      expect((global as any).registerUserMock).toHaveBeenCalledWith(
        "user@example.com",
        "secret123",
        "Jane",
        "agresivo"
      )
    );
    expect((global as any).pushMock).toHaveBeenCalledWith("/");
  });

  it("muestra mensaje de error cuando el registro falla", async () => {
    (global as any).registerUserMock.mockRejectedValueOnce(
      new Error("Duplicado")
    );

    customRender(<RegisterForm />);

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
    expect((global as any).pushMock).not.toHaveBeenCalled();
  });

  it("limpia los errores de validación al modificar los campos", async () => {
    customRender(<RegisterForm />);

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

    fireEvent.submit(screen.getByRole("button", { name: /registrarse/i }).closest("form")!);

    expect(
      await screen.findByText(/las contraseñas no coinciden/i)
    ).toBeInTheDocument();

    fireEvent.input(screen.getByPlaceholderText(/confirmar contraseña/i), {
      target: { value: "secret123" },
    });

    await waitFor(() => {
      expect(
        screen.queryByText(/las contraseñas no coinciden/i)
      ).not.toBeInTheDocument();
    });
  });

  it("normaliza espacios y utiliza mensaje genérico si el backend falla", async () => {
    (global as any).registerUserMock.mockRejectedValueOnce("falló");

    customRender(<RegisterForm />);

    fireEvent.input(screen.getByPlaceholderText(/nombre/i), {
      target: { value: "  Jane Doe  " },
    });
    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "  user@example.com  " },
    });
    fireEvent.input(screen.getByPlaceholderText(/^contraseña$/i), {
      target: { value: "  secret123  " },
    });
    fireEvent.input(screen.getByPlaceholderText(/confirmar contraseña/i), {
      target: { value: "  secret123  " },
    });

    fireEvent.submit(screen.getByRole("button", { name: /registrarse/i }).closest("form")!);

    await waitFor(() => {
      expect((global as any).registerUserMock).toHaveBeenCalledWith(
        "user@example.com",
        "secret123",
        "Jane Doe",
        "moderado"
      );
    });

    expect(
      await screen.findByText(/error al registrar la cuenta/i)
    ).toBeInTheDocument();
  });

  it("deshabilita el botón mientras se registra al usuario", async () => {
    let resolvePromise: () => void = () => undefined;
    const pending = new Promise<void>((resolve) => {
      resolvePromise = resolve;
    });
    (global as any).registerUserMock.mockReturnValueOnce(pending);

    customRender(<RegisterForm />);

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

    fireEvent.submit(screen.getByRole("button", { name: /registrarse/i }).closest("form")!);

    expect(screen.getByRole("button", { name: /registrando/i })).toBeDisabled();

    resolvePromise();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /registrarse/i })).toBeEnabled()
    );
  });

  it("no presenta violaciones de accesibilidad básicas", async () => {
    const { container } = customRender(<RegisterForm />);

    expect(await axe(container)).toHaveNoViolations();
  });
});
