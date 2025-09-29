import { act, render, screen, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "../auth-context";
import type { AuthResponse, UserProfile } from "@/lib/api";
import { refreshToken, getProfile } from "@/lib/api";

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return {
    ...actual,
    refreshToken: jest.fn(),
    getProfile: jest.fn(),
  };
});

describe("AuthProvider", () => {
  let storageData: Record<string, string>;

  beforeEach(() => {
    storageData = {};
    const localStorageMock = {
      getItem: jest.fn((key: string) => storageData[key] ?? null),
      setItem: jest.fn((key: string, value: string) => {
        storageData[key] = value;
      }),
      removeItem: jest.fn((key: string) => {
        delete storageData[key];
      }),
      clear: jest.fn(() => {
        storageData = {};
      }),
    };

    Object.defineProperty(window, "localStorage", {
      value: localStorageMock,
      configurable: true,
      writable: true,
    });

    jest.clearAllMocks();
  });

  const TestConsumer = () => {
    const { user, accessToken, refreshToken: rToken, loading } = useAuth();

    return (
      <div>
        <span data-testid="user-email">{user?.email ?? "no-user"}</span>
        <span data-testid="access-token">{accessToken ?? "no-access"}</span>
        <span data-testid="refresh-token">{rToken ?? "no-refresh"}</span>
        <span data-testid="loading">{loading ? "loading" : "ready"}</span>
      </div>
    );
  };

  it("restores the session from localStorage and exposes the auth state", async () => {
    const mockTokens: AuthResponse = {
      access_token: "new-access-token",
      refresh_token: "new-refresh-token",
    };
    const mockUser: UserProfile = {
      id: "user-1",
      email: "user@example.com",
      name: "Test User",
    };

    storageData["access_token"] = "stored-access";
    storageData["refresh_token"] = "stored-refresh";

    const mockedRefreshToken = refreshToken as jest.MockedFunction<typeof refreshToken>;
    const mockedGetProfile = getProfile as jest.MockedFunction<typeof getProfile>;

    mockedRefreshToken.mockResolvedValue(mockTokens);
    mockedGetProfile.mockResolvedValue(mockUser);

    await act(async () => {
      render(
        <AuthProvider>
          <TestConsumer />
        </AuthProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("ready");
    });

    await waitFor(() => {
      expect(screen.getByTestId("user-email")).toHaveTextContent(mockUser.email);
      expect(screen.getByTestId("access-token")).toHaveTextContent(mockTokens.access_token);
      expect(screen.getByTestId("refresh-token")).toHaveTextContent(mockTokens.refresh_token);
    });

    expect(mockedRefreshToken).toHaveBeenCalledWith("stored-refresh");
    expect(mockedGetProfile).toHaveBeenCalledWith(mockTokens.access_token);
    expect(storageData).toEqual({
      access_token: mockTokens.access_token,
      refresh_token: mockTokens.refresh_token,
    });
  });

  it("throws when useAuth is used without provider", () => {
    const WithoutProvider = () => {
      useAuth();
      return null;
    };

    expect(() => render(<WithoutProvider />)).toThrow("useAuth debe usarse dentro de AuthProvider");
  });
});
