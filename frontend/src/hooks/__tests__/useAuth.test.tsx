import { act, renderHook } from "@/tests/utils/renderWithProviders";
import type { PropsWithChildren } from "react";
import { useAuth } from "../useAuth";

// QA: mock provider to validate context transitions without tocar lógica real.
jest.mock("../../components/providers/auth-provider", () => {
  const React = require("react");

  type MockState = { user: any; token: string | null };
  const AuthContext = React.createContext<any>(undefined);

  function MockAuthProvider({ children }: PropsWithChildren) {
    const [state, setState] = React.useState<MockState>({ user: null, token: null });

    const loginUser = React.useCallback(async () => {
      setState({
        user: { id: "user-1", email: "mock@example.com" },
        token: "token-abc",
      });
    }, []);

    const logout = React.useCallback(() => {
      setState({ user: null, token: null });
    }, []);

    const registerUser = React.useCallback(async () => {
      setState({
        user: { id: "user-2", email: "register@example.com" },
        token: "token-reg",
      });
    }, []);

    const value = React.useMemo(
      () => ({
        user: state.user,
        token: state.token,
        loading: false,
        loginUser,
        registerUser,
        logout,
      }),
      [loginUser, logout, registerUser, state.token, state.user]
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
  }

  return {
    __esModule: true,
    AuthProvider: MockAuthProvider,
    useAuth: () => {
      const ctx = React.useContext(AuthContext);
      if (!ctx) {
        throw new Error("useAuth debe ejecutarse dentro del provider");
      }
      return ctx;
    },
  };
});

const { AuthProvider } = jest.requireMock("../../components/providers/auth-provider");

describe("useAuth hook", () => {
  // QA: helper wrapper para reutilizar el provider fingido.
  const wrapper = ({ children }: PropsWithChildren) => (
    <AuthProvider>{children}</AuthProvider>
  );

  it("permite loguear y cerrar sesión actualizando el contexto", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current.user).toBeNull();
    expect(result.current.token).toBeNull();

    await act(async () => {
      await result.current.loginUser("user@example.com", "secret");
    });

    expect(result.current.user).toEqual({ id: "user-1", email: "mock@example.com" });
    expect(result.current.token).toBe("token-abc");

    await act(async () => {
      result.current.logout();
    });

    expect(result.current.user).toBeNull();
    expect(result.current.token).toBeNull();
  });

  it("ofrece un registro ficticio que también hidrata el usuario", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.registerUser("mock@example.com", "secret");
    });

    expect(result.current.user).toEqual({
      id: "user-2",
      email: "register@example.com",
    });
    expect(result.current.token).toBe("token-reg");
  });
});
