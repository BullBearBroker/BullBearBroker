// [Codex] nuevo - Ajustes para los placeholders y mock de Auth
import {
  customRender,
  screen,
  fireEvent,
  waitFor,
} from "@/tests/utils/renderWithProviders";
import { axe } from "jest-axe";
import LoginForm from "../login-form";
import { authMessages } from "@/lib/i18n/auth";
import { HttpError } from "@/lib/api";

// Mock de useAuth
jest.mock("@/components/providers/auth-provider", () => {
  (global as any).loginUserMock = jest.fn().mockResolvedValue(undefined);

  return {
    __esModule: true,
    useAuth: () => ({
      loginUser: (global as any).loginUserMock,
    }),
  };
});

jest.mock("@/lib/analytics", () => ({
  trackEvent: jest.fn(),
}));

const getTrackEventMock = () =>
  jest.requireMock("@/lib/analytics").trackEvent as jest.Mock;

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
}); // [Codex] nuevo - mock de router para componentes de Next

describe("LoginForm", () => {
  beforeEach(() => {
    (global as any).loginUserMock.mockClear();
    (global as any).pushMock.mockClear();
    getTrackEventMock().mockClear();
  });

  it("muestra mensajes de validación cuando el formulario está vacío", async () => {
    customRender(<LoginForm />);

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(
      await screen.findByText(authMessages.validation.email)
    ).toBeInTheDocument();
    expect((global as any).loginUserMock).not.toHaveBeenCalled();
  });

  it("valida longitud mínima de la contraseña", async () => {
    customRender(<LoginForm />);

    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(screen.getByPlaceholderText(/contraseña/i), {
      target: { value: "123" },
    });

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(
      await screen.findByText(authMessages.validation.password)
    ).toBeInTheDocument();
    expect((global as any).loginUserMock).not.toHaveBeenCalled();
  });

  it("envía los datos correctamente", async () => {
    customRender(<LoginForm />);

    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(screen.getByPlaceholderText(/contraseña/i), {
      target: { value: "secret123" },
    });

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    await waitFor(() =>
      expect((global as any).loginUserMock).toHaveBeenCalledWith(
        "user@example.com",
        "secret123",
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      )
    );
    expect((global as any).pushMock).toHaveBeenCalledWith("/");

    // No hay validación de UI en este form; validamos que NO haya mensaje de error inmediato
    expect(
      screen.queryByText(/error al iniciar sesión/i)
    ).not.toBeInTheDocument();
  });

  it("muestra mensaje de error cuando la autenticación falla", async () => {
    (global as any).loginUserMock.mockRejectedValueOnce(
      new HttpError(authMessages.errors.invalidCredentials, { status: 401 })
    );

    customRender(<LoginForm />);

    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(screen.getByPlaceholderText(/contraseña/i), {
      target: { value: "secret123" },
    });

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(
      await screen.findByText(authMessages.errors.invalidCredentials)
    ).toBeInTheDocument();
    expect((global as any).pushMock).not.toHaveBeenCalled();
  });

  it("limpia los errores del formulario al corregir los campos", async () => {
    (global as any).loginUserMock.mockRejectedValueOnce(
      new HttpError(authMessages.errors.invalidCredentials, { status: 401 })
    );

    customRender(<LoginForm />);

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

    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "nuevo@example.com" },
    });

    await waitFor(() => {
      expect(
        screen.queryByText(authMessages.errors.invalidCredentials)
      ).not.toBeInTheDocument();
    });
  });

  it("usa credenciales normalizadas y muestra mensaje genérico por defecto", async () => {
    (global as any).loginUserMock.mockRejectedValueOnce("falló");

    customRender(<LoginForm />);

    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "  user@example.com  " },
    });
    fireEvent.input(screen.getByPlaceholderText(/contraseña/i), {
      target: { value: "  secret123  " },
    });

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    await waitFor(() => {
      expect((global as any).loginUserMock).toHaveBeenCalledWith(
        "user@example.com",
        "secret123",
        expect.objectContaining({ signal: expect.any(Object) })
      );
    });

    expect(
      await screen.findByText(authMessages.errors.generic)
    ).toBeInTheDocument();
  });

  it("deshabilita el botón mientras se envían las credenciales", async () => {
    let resolvePromise: () => void = () => undefined;
    const pendingPromise = new Promise<void>((resolve) => {
      resolvePromise = resolve;
    });
    (global as any).loginUserMock.mockReturnValueOnce(pendingPromise);

    customRender(<LoginForm />);

    fireEvent.input(screen.getByPlaceholderText(/correo electrónico/i), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(screen.getByPlaceholderText(/contraseña/i), {
      target: { value: "secret123" },
    });

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(
      screen.getByRole("button", { name: authMessages.actions.submitting })
    ).toBeDisabled();

    resolvePromise();

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /iniciar sesión/i })
      ).toBeEnabled()
    );
  });

  it("no presenta violaciones de accesibilidad básicas", async () => {
    const { container } = customRender(<LoginForm />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("muestra mensaje de 429 y bloquea reintentos", async () => {
    const rateError = new HttpError("rate limited", { status: 429, retryAfter: 8 });
    (global as any).loginUserMock.mockRejectedValueOnce(rateError);

    customRender(<LoginForm />);

    fireEvent.input(screen.getByPlaceholderText(authMessages.placeholders.email), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(
      screen.getByPlaceholderText(authMessages.placeholders.password),
      {
        target: { value: "secret123" },
      }
    );

    fireEvent.click(screen.getByRole("button", { name: authMessages.actions.submit }));

    const messages = await screen.findAllByText(
      authMessages.errors.rateLimited({ seconds: 8 })
    );
    expect(messages.length).toBeGreaterThanOrEqual(1);

    expect(
      screen.getByRole("button", {
        name: authMessages.errors.rateLimited({ seconds: 8 }),
      })
    ).toBeDisabled();
    const trackEvent = getTrackEventMock();
    expect(trackEvent).toHaveBeenCalledTimes(1);
    expect(trackEvent).toHaveBeenCalledWith("login_rate_limited_ui", {
      reason: "http_429",
      retry_after_seconds: 8,
    });
  });

  it("aplica throttle para evitar envíos repetidos", async () => {
    let resolvePromise: () => void = () => undefined;
    const pendingPromise = new Promise<void>((resolve) => {
      resolvePromise = resolve;
    });
    (global as any).loginUserMock.mockReturnValueOnce(pendingPromise);

    customRender(<LoginForm />);

    fireEvent.input(screen.getByPlaceholderText(authMessages.placeholders.email), {
      target: { value: "user@example.com" },
    });
    fireEvent.input(
      screen.getByPlaceholderText(authMessages.placeholders.password),
      {
        target: { value: "secret123" },
      }
    );

    fireEvent.click(screen.getByRole("button", { name: authMessages.actions.submit }));
    fireEvent.click(screen.getByRole("button", { name: authMessages.actions.submitting }));

    expect((global as any).loginUserMock).toHaveBeenCalledTimes(1);

    resolvePromise();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: authMessages.actions.submit })).toBeEnabled()
    );
  });
});
