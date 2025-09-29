import React from "react";
import { render, screen } from "@testing-library/react";

type AuthModule = typeof import("../auth-context");
type AuthContextType = ReturnType<AuthModule["useAuth"]>;

let AuthProvider: AuthModule["AuthProvider"];
let useAuth: AuthModule["useAuth"];
let AuthContext: React.Context<AuthContextType | undefined>;

describe("auth context", () => {
  beforeAll(async () => {
    const authModule = await import("../auth-context");
    AuthProvider = authModule.AuthProvider;
    useAuth = authModule.useAuth;
    AuthContext = (authModule as any).AuthContext as React.Context<AuthContextType | undefined>;
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
      </AuthContext.Provider>
    );

    expect(screen.getByTestId("user-name")).toHaveTextContent("Test User");
    expect(mockValue.login).not.toHaveBeenCalled();
    expect(mockValue.logout).not.toHaveBeenCalled();
  });

  it("throws an error when useAuth is called without a provider", () => {
    const WithoutProvider = () => {
      useAuth();
      return null;
    };

    expect(() => render(<WithoutProvider />)).toThrow(
      "useAuth debe usarse dentro de AuthProvider"
    );
  });
});
