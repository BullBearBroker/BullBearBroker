import React from "react";
import userEvent from "@testing-library/user-event";
import { act, customRender, render, screen, waitFor } from "@/tests/utils/renderWithProviders";

import { AuthProvider, useAuth } from "../auth-provider";
import * as AuthProviderModule from "../auth-provider";
import { getProfile, login, refreshToken, register } from "@/lib/api";

const MOCK_REFRESH_RESPONSE = {
  access_token: "refreshed-access-token",
  refresh_token: "next-refresh-token",
};

const MOCK_PROFILE = {
  id: "user-1",
  email: "user@example.com",
  name: "User",
};

const MOCK_AUTH_RESPONSE = {
  access_token: "auth-access-token",
  refresh_token: "auth-refresh-token",
};

jest.mock("@/lib/api", () => ({
  refreshToken: jest.fn(),
  getProfile: jest.fn(),
  login: jest.fn(),
  register: jest.fn(),
}));

describe("AuthProvider", () => {
  const mockedRefreshToken = refreshToken as jest.MockedFunction<typeof refreshToken>;
  const mockedGetProfile = getProfile as jest.MockedFunction<typeof getProfile>;
  const mockedLogin = login as jest.MockedFunction<typeof login>;
  const mockedRegister = register as jest.MockedFunction<typeof register>;

  const createLocalStorageMock = () => {
    let store: Record<string, string> = {};

    return {
      getItem: jest.fn((key: string) => {
        return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null;
      }),
      setItem: jest.fn((key: string, value: string) => {
        store[key] = value;
      }),
      removeItem: jest.fn((key: string) => {
        delete store[key];
      }),
      clear: jest.fn(() => {
        store = {};
      }),
      key: jest.fn((index: number) => Object.keys(store)[index] ?? null),
      get length() {
        return Object.keys(store).length;
      },
    } as unknown as Storage;
  };

  let localStorageMock: ReturnType<typeof createLocalStorageMock>;

  beforeEach(() => {
    jest.clearAllMocks();

    localStorageMock = createLocalStorageMock();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: localStorageMock,
    });

    mockedRefreshToken.mockResolvedValue(MOCK_REFRESH_RESPONSE);
    mockedGetProfile.mockResolvedValue(MOCK_PROFILE);
    mockedLogin.mockResolvedValue(MOCK_AUTH_RESPONSE);
    mockedRegister.mockResolvedValue(MOCK_AUTH_RESPONSE);
  });

  afterEach(() => {
    localStorageMock.clear();
    delete (window as Partial<typeof window>).localStorage;
    jest.restoreAllMocks();
  });

  it("hydrates the session from an existing refresh token", async () => {
    window.localStorage.setItem("refresh_token", "stored-refresh-token");

    const Consumer = () => {
      const { loading, user } = useAuth();

      return (
        <div>
          <span data-testid="loading-state">{loading ? "loading" : "loaded"}</span>
          <span data-testid="user-email">{user?.email ?? "no-user"}</span>
        </div>
      );
    };

    customRender(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    expect(screen.getByTestId("loading-state")).toHaveTextContent("loading");

    await act(async () => {
      await Promise.resolve();
    });

    expect(mockedRefreshToken).toHaveBeenCalledWith("stored-refresh-token");

    expect(await screen.findByTestId("user-email")).toHaveTextContent(MOCK_PROFILE.email);
    expect(screen.getByTestId("loading-state")).toHaveTextContent("loaded");
    expect(localStorageMock.setItem).toHaveBeenCalledWith("refresh_token", MOCK_REFRESH_RESPONSE.refresh_token);
  });

  it("inicia sin usuario cuando no hay sesión previa", async () => {
    const Consumer = () => {
      const { user, token, loading } = useAuth();
      return (
        <div>
          <span data-testid="loading">{loading ? "loading" : "idle"}</span>
          <span data-testid="token">{token ?? "no-token"}</span>
          <span data-testid="user">{user?.email ?? "anon"}</span>
        </div>
      );
    };

    customRender(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("idle");
    });
    expect(screen.getByTestId("token")).toHaveTextContent("no-token");
    expect(screen.getByTestId("user")).toHaveTextContent("anon");
    expect(mockedRefreshToken).not.toHaveBeenCalled();
  });

  it("realiza login exitoso y persiste tokens", async () => {
    const user = userEvent.setup();
    mockedLogin.mockResolvedValueOnce(MOCK_AUTH_RESPONSE);
    mockedGetProfile.mockResolvedValueOnce(MOCK_PROFILE);

    const Consumer = () => {
      const { loginUser, user, token, loading } = useAuth();
      return (
        <div>
          <span data-testid="loading">{loading ? "loading" : "idle"}</span>
          <span data-testid="token">{token ?? "no-token"}</span>
          <span data-testid="user">{user?.email ?? "anon"}</span>
          <button onClick={() => loginUser("user@example.com", "secret")}>Login</button>
        </div>
      );
    };

    customRender(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /login/i }));
    });

    await waitFor(() => {
      expect(screen.getByTestId("user")).toHaveTextContent(MOCK_PROFILE.email);
    });
    expect(screen.getByTestId("token")).toHaveTextContent(MOCK_AUTH_RESPONSE.access_token);
    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      "refresh_token",
      MOCK_AUTH_RESPONSE.refresh_token
    );
    expect(screen.getByTestId("loading")).toHaveTextContent("idle");
  });

  it("propaga el error de login y limpia el estado", async () => {
    const user = userEvent.setup();
    mockedLogin.mockRejectedValueOnce(new Error("Credenciales inválidas"));

    const Consumer = () => {
      const { loginUser, user, token, loading } = useAuth();
      const [error, setError] = React.useState<string | null>(null);

      const handleLogin = async () => {
        try {
          await loginUser("user@example.com", "secret");
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        }
      };

      return (
        <div>
          <span data-testid="loading">{loading ? "loading" : "idle"}</span>
          <span data-testid="token">{token ?? "no-token"}</span>
          <span data-testid="user">{user?.email ?? "anon"}</span>
          <button onClick={handleLogin}>Login fallido</button>
          {error && <span data-testid="error">{error}</span>}
        </div>
      );
    };

    customRender(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /login fallido/i }));
    });

    expect(await screen.findByTestId("error")).toHaveTextContent("Credenciales inválidas");
    expect(screen.getByTestId("token")).toHaveTextContent("no-token");
    expect(screen.getByTestId("user")).toHaveTextContent("anon");
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("refresh_token");
    expect(screen.getByTestId("loading")).toHaveTextContent("idle");
  });

  it("ejecuta logout limpiando tokens y usuario", async () => {
    const user = userEvent.setup();
    mockedLogin.mockResolvedValueOnce(MOCK_AUTH_RESPONSE);
    mockedGetProfile.mockResolvedValueOnce(MOCK_PROFILE);

    const Consumer = () => {
      const { loginUser, logout, user, token } = useAuth();
      return (
        <div>
          <span data-testid="token">{token ?? "no-token"}</span>
          <span data-testid="user">{user?.email ?? "anon"}</span>
          <button onClick={() => loginUser("user@example.com", "secret")}>Login</button>
          <button onClick={() => logout()}>Logout</button>
        </div>
      );
    };

    customRender(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /^login$/i }));
    });

    await waitFor(() => {
      expect(screen.getByTestId("user")).toHaveTextContent(MOCK_PROFILE.email);
    });

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /logout/i }));
    });

    expect(screen.getByTestId("token")).toHaveTextContent("no-token");
    expect(screen.getByTestId("user")).toHaveTextContent("anon");
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("refresh_token");
  });

  it("allows downstream consumers to mock useAuth outside the provider", () => {
    const fixture = {
      user: MOCK_PROFILE,
      token: MOCK_AUTH_RESPONSE.access_token,
      loading: false,
      loginUser: jest.fn(),
      registerUser: jest.fn(),
      logout: jest.fn(),
    } satisfies ReturnType<typeof useAuth>;

    const spy = jest
      .spyOn(AuthProviderModule, "useAuth")
      .mockReturnValue(fixture);

    const Consumer = () => {
      const { user } = AuthProviderModule.useAuth();
      return <span>{user?.email}</span>;
    };

    expect(() => customRender(<Consumer />)).not.toThrow();
    expect(screen.getByText(MOCK_PROFILE.email)).toBeInTheDocument();

    spy.mockRestore();
  });

  it("maneja errores al refrescar una sesión guardada", async () => {
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    window.localStorage.setItem("refresh_token", "stored-refresh");
    mockedRefreshToken.mockRejectedValueOnce(new Error("No se pudo refrescar"));

    const Consumer = () => {
      const { loading, user, token } = useAuth();
      return (
        <div>
          <span data-testid="loading">{loading ? "loading" : "idle"}</span>
          <span data-testid="token">{token ?? "no-token"}</span>
          <span data-testid="user">{user?.email ?? "anon"}</span>
        </div>
      );
    };

    try {
      customRender(
        <AuthProvider>
          <Consumer />
        </AuthProvider>
      );

      expect(screen.getByTestId("loading")).toHaveTextContent("loading");

      await waitFor(() => {
        expect(screen.getByTestId("loading")).toHaveTextContent("idle");
      });

      expect(screen.getByTestId("token")).toHaveTextContent("no-token");
      expect(screen.getByTestId("user")).toHaveTextContent("anon");
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("refresh_token");
    } finally {
      consoleSpy.mockRestore();
    }
  });

  it("permite registrar un usuario y guardar sesión", async () => {
    const user = userEvent.setup();
    mockedRegister.mockResolvedValueOnce(MOCK_AUTH_RESPONSE);
    mockedGetProfile.mockResolvedValueOnce(MOCK_PROFILE);

    const Consumer = () => {
      const { registerUser, user: currentUser, token } = useAuth();
      return (
        <div>
          <span data-testid="token">{token ?? "no-token"}</span>
          <span data-testid="user">{currentUser?.email ?? "anon"}</span>
          <button onClick={() => registerUser("user@example.com", "secret", "User")}>Registrar</button>
        </div>
      );
    };

    customRender(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /registrar/i }));
    });

    await waitFor(() => {
      expect(screen.getByTestId("user")).toHaveTextContent(MOCK_PROFILE.email);
    });
    expect(screen.getByTestId("token")).toHaveTextContent(MOCK_AUTH_RESPONSE.access_token);
    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      "refresh_token",
      MOCK_AUTH_RESPONSE.refresh_token
    );
  });

  it("limpia la sesión cuando el registro falla", async () => {
    const user = userEvent.setup();
    mockedRegister.mockRejectedValueOnce(new Error("Registro inválido"));

    const Consumer = () => {
      const { registerUser, user: currentUser, token } = useAuth();
      const [error, setError] = React.useState<string | null>(null);

      const handleRegister = async () => {
        try {
          await registerUser("user@example.com", "secret", "User");
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        }
      };

      return (
        <div>
          <span data-testid="token">{token ?? "no-token"}</span>
          <span data-testid="user">{currentUser?.email ?? "anon"}</span>
          <button onClick={handleRegister}>Registrar fallido</button>
          {error && <span data-testid="error">{error}</span>}
        </div>
      );
    };

    customRender(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /registrar fallido/i }));
    });

    expect(await screen.findByTestId("error")).toHaveTextContent("Registro inválido");
    expect(screen.getByTestId("token")).toHaveTextContent("no-token");
    expect(screen.getByTestId("user")).toHaveTextContent("anon");
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("refresh_token");
  });

  it("omite hidratar sesión cuando window no está disponible", () => {
    const originalWindowDescriptor = Object.getOwnPropertyDescriptor(
      globalThis,
      "window"
    );

    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: undefined,
    });

    try {
      expect(AuthProviderModule.authProviderTestUtils).toBeDefined();
      expect(() =>
        AuthProviderModule.authProviderTestUtils.persistRefreshToken("token")
      ).not.toThrow();
      expect(localStorageMock.setItem).not.toHaveBeenCalled();
    } finally {
      if (originalWindowDescriptor) {
        Object.defineProperty(globalThis, "window", originalWindowDescriptor);
      } else {
        delete (globalThis as Partial<typeof globalThis>).window;
      }
    }
  });

  it("lanza un error si useAuth se usa fuera del provider", () => {
    const Consumer = () => {
      useAuth();
      return null;
    };

    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    try {
      expect(() => render(<Consumer />)).toThrow(
        "useAuth must be used within AuthProvider"
      );
    } finally {
      consoleSpy.mockRestore();
    }
  });
});
