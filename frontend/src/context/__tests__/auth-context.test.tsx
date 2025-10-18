import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { withAct, flushPromisesAndTimers } from "@/tests/utils/act-helpers";

import { ErrorBoundary } from "@/tests/utils/ErrorBoundary";
import { login as loginUser, refreshToken as refreshTokenRequest, getProfile } from "@/lib/api";

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return {
    ...actual,
    login: jest.fn(),
    refreshToken: jest.fn(),
    getProfile: jest.fn(),
  };
});

type AuthModule = typeof import("../auth-context");
type AuthContextType = ReturnType<AuthModule["useAuth"]>;

let AuthProvider: AuthModule["AuthProvider"];
let useAuth: AuthModule["useAuth"];
let AuthContext: React.Context<AuthContextType | undefined>;

describe("auth context", () => {
  const mockedLogin = loginUser as jest.MockedFunction<typeof loginUser>;
  const mockedRefreshToken = refreshTokenRequest as jest.MockedFunction<typeof refreshTokenRequest>;
  const mockedGetProfile = getProfile as jest.MockedFunction<typeof getProfile>;

  beforeAll(async () => {
    const authModule = await import("../auth-context");
    AuthProvider = authModule.AuthProvider;
    useAuth = authModule.useAuth;
    AuthContext = (authModule as any).AuthContext as React.Context<AuthContextType | undefined>;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  it("provides the mocked context value to consumers", () => {
    expect(typeof AuthProvider).toBe("function");

    const mockValue: AuthContextType = {
      user: {
        id: "user-1",
        email: "user@example.com",
        name: "Test User",
      },
      accessToken: "access-token",
      refreshToken: "refresh-token",
      login: jest.fn(),
      logout: jest.fn(),
      loading: false,
    };

    const TestConsumer = () => {
      const auth = useAuth();
      return <span data-testid="user-name">{auth.user?.name ?? "no-user"}</span>;
    };

    render(
      <AuthContext.Provider value={mockValue}>
        <TestConsumer />
      </AuthContext.Provider>,
    );

    expect(screen.getByTestId("user-name")).toHaveTextContent("Test User");
    expect(mockValue.login).not.toHaveBeenCalled();
    expect(mockValue.logout).not.toHaveBeenCalled();
  });

  it("muestra el fallback del ErrorBoundary cuando useAuth se usa fuera del provider", () => {
    const WithoutProvider = () => {
      useAuth();
      return null;
    };

    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    try {
      expect(() =>
        render(
          <ErrorBoundary fallback={<span>Error capturado</span>}>
            <WithoutProvider />
          </ErrorBoundary>,
        ),
      ).not.toThrow();

      expect(screen.getByText("Error capturado")).toBeInTheDocument();
    } finally {
      consoleSpy.mockRestore();
    }
  });

  it("permite un login exitoso y persiste los tokens", async () => {
    mockedLogin.mockResolvedValue({
      access_token: "access-123",
      refresh_token: "refresh-456",
    });
    mockedGetProfile.mockResolvedValue({
      id: "user-1",
      email: "user@example.com",
      name: "Test User",
    });

    const user = userEvent.setup();

    const TestComponent = () => {
      const auth = useAuth();
      return (
        <div>
          <span data-testid="user-email">{auth.user?.email ?? "no-user"}</span>
          <span data-testid="loading">{auth.loading ? "loading" : "idle"}</span>
          <button onClick={() => auth.login("user@example.com", "secret")} disabled={auth.loading}>
            Ejecutar login
          </button>
        </div>
      );
    };

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    expect(screen.getByTestId("user-email")).toHaveTextContent("no-user");

    await withAct(async () => {
      await user.click(screen.getByRole("button", { name: /ejecutar login/i }));
    });
    await flushPromisesAndTimers();

    await waitFor(() => {
      expect(screen.getByTestId("user-email")).toHaveTextContent("user@example.com");
    });

    expect(mockedLogin).toHaveBeenCalledWith({
      email: "user@example.com",
      password: "secret",
    });
    expect(mockedGetProfile).toHaveBeenCalledWith("access-123");
    expect(localStorage.getItem("access_token")).toBe("access-123");
    expect(localStorage.getItem("refresh_token")).toBe("refresh-456");
    expect(screen.getByTestId("loading")).toHaveTextContent("idle");
  });

  it("limpia los datos al hacer logout", async () => {
    mockedLogin.mockResolvedValue({
      access_token: "token-a",
      refresh_token: "token-b",
    });
    mockedGetProfile.mockResolvedValue({
      id: "user-99",
      email: "logout@example.com",
    });

    const user = userEvent.setup();

    const TestComponent = () => {
      const auth = useAuth();
      return (
        <div>
          <span data-testid="user-email">{auth.user?.email ?? "no-user"}</span>
          <button onClick={() => auth.login("logout@example.com", "pwd")}>Login</button>
          <button onClick={() => auth.logout()}>Logout</button>
        </div>
      );
    };

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await withAct(async () => {
      await user.click(screen.getByRole("button", { name: /login/i }));
    });
    await flushPromisesAndTimers();

    await waitFor(() => {
      expect(screen.getByTestId("user-email")).toHaveTextContent("logout@example.com");
    });

    await withAct(async () => {
      await user.click(screen.getByRole("button", { name: /logout/i }));
    });
    await flushPromisesAndTimers();

    expect(screen.getByTestId("user-email")).toHaveTextContent("no-user");
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("refresca la sesión al montar si existen tokens", async () => {
    localStorage.setItem("access_token", "stored-access");
    localStorage.setItem("refresh_token", "stored-refresh");

    mockedRefreshToken.mockResolvedValue({
      access_token: "new-access",
      refresh_token: "new-refresh",
    });
    mockedGetProfile.mockResolvedValue({
      id: "user-2",
      email: "refreshed@example.com",
    });

    const TestComponent = () => {
      const auth = useAuth();
      return (
        <>
          <span data-testid="loading">{auth.loading ? "loading" : "idle"}</span>
          <span data-testid="user-email">{auth.user?.email ?? "no-user"}</span>
        </>
      );
    };

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    expect(screen.getByTestId("loading")).toHaveTextContent("loading");

    await waitFor(() => {
      expect(mockedRefreshToken).toHaveBeenCalledWith("stored-refresh");
      expect(screen.getByTestId("user-email")).toHaveTextContent("refreshed@example.com");
    });

    expect(localStorage.getItem("access_token")).toBe("new-access");
    expect(localStorage.getItem("refresh_token")).toBe("new-refresh");
    expect(screen.getByTestId("loading")).toHaveTextContent("idle");
  });

  it("propaga el error de login y mantiene el estado consistente", async () => {
    mockedLogin.mockRejectedValue(new Error("Credenciales inválidas"));

    const user = userEvent.setup();

    const TestComponent = () => {
      const auth = useAuth();
      const [error, setError] = React.useState<string | null>(null);

      const handleLogin = async () => {
        try {
          await auth.login("fail@example.com", "wrong");
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        }
      };

      return (
        <div>
          <span data-testid="loading">{auth.loading ? "loading" : "idle"}</span>
          <span data-testid="error">{error ?? "sin-error"}</span>
          <button onClick={handleLogin}>Login fallido</button>
        </div>
      );
    };

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await withAct(async () => {
      await user.click(screen.getByRole("button", { name: /login fallido/i }));
    });
    await flushPromisesAndTimers();

    await waitFor(() => {
      expect(screen.getByTestId("error")).toHaveTextContent("Credenciales inválidas");
    });

    expect(screen.getByTestId("loading")).toHaveTextContent("idle");
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });
});
