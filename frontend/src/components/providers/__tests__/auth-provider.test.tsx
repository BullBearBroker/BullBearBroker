import React from "react";
import { act, render, screen } from "@testing-library/react";

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

    render(
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

    expect(() => render(<Consumer />)).not.toThrow();
    expect(screen.getByText(MOCK_PROFILE.email)).toBeInTheDocument();

    spy.mockRestore();
  });
});
