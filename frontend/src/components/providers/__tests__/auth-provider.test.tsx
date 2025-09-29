import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";

import { AuthProvider, useAuth } from "../auth-provider";
import { getProfile, refreshToken } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  login: jest.fn(),
  register: jest.fn(),
  refreshToken: jest.fn(),
  getProfile: jest.fn(),
}));

describe("AuthProvider", () => {
  const createLocalStorageMock = () => {
    let store: Record<string, string> = {};

    return {
      getItem: jest.fn((key: string) => {
        return Object.prototype.hasOwnProperty.call(store, key)
          ? store[key]
          : null;
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
    };
  };

  let localStorageMock: ReturnType<typeof createLocalStorageMock>;

  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock = createLocalStorageMock();

    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: localStorageMock,
    });
  });

  it("provides the auth context to children", async () => {
    const profile = { id: "user-1", email: "user@example.com" };
    const refreshResponse = {
      access_token: "access-token",
      refresh_token: "refresh-token-2",
    };

    const mockedRefreshToken = refreshToken as jest.MockedFunction<
      typeof refreshToken
    >;
    const mockedGetProfile = getProfile as jest.MockedFunction<typeof getProfile>;

    mockedRefreshToken.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(() => resolve(refreshResponse), 10)
        )
    );
    mockedGetProfile.mockResolvedValue(profile);

    window.localStorage.setItem("refresh_token", "refresh-token-1");

    const ChildComponent = () => {
      const { loading, user } = useAuth();

      return (
        <div>
          <span>{loading ? "loading" : "loaded"}</span>
          <span>{user?.email ?? "no-user"}</span>
        </div>
      );
    };

    await act(async () => {
      render(
        <AuthProvider>
          <ChildComponent />
        </AuthProvider>
      );
    });

    expect(screen.getByText("loading")).toBeInTheDocument();

    await waitFor(() => {
      expect(mockedRefreshToken).toHaveBeenCalledWith("refresh-token-1");
    });

    expect(await screen.findByText(profile.email)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("loaded")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        "refresh_token",
        refreshResponse.refresh_token
      );
    });
  });
});
