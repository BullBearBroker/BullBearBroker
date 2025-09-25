"use client";

import Cookies from "js-cookie";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";

import {
  AuthResponse,
  LoginPayload,
  RegisterPayload,
  UserProfile,
  getProfile,
  login as loginRequest,
  refreshToken as refreshTokenRequest,
  register as registerRequest
} from "@/lib/api";

interface AuthContextValue {
  user: UserProfile | null;
  accessToken: string | null;
  refreshToken: string | null;
  loading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
  refreshTokens: () => Promise<void>;
  reloadProfile: (tokenOverride?: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const ACCESS_TOKEN_KEY = "bb_access_token";
const REFRESH_TOKEN_KEY = "bb_refresh_token";

function persistTokens(tokens: Pick<AuthContextValue, "accessToken" | "refreshToken">) {
  if (typeof window === "undefined") {
    return;
  }
  const { accessToken, refreshToken } = tokens;
  if (accessToken) {
    Cookies.set(ACCESS_TOKEN_KEY, accessToken, {
      secure: true,
      sameSite: "strict"
    });
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  } else {
    Cookies.remove(ACCESS_TOKEN_KEY);
    localStorage.removeItem(ACCESS_TOKEN_KEY);
  }

  if (refreshToken) {
    Cookies.set(REFRESH_TOKEN_KEY, refreshToken, {
      secure: true,
      sameSite: "strict"
    });
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  } else {
    Cookies.remove(REFRESH_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
}

function readToken(key: string) {
  if (typeof window === "undefined") return null;
  return Cookies.get(key) || localStorage.getItem(key) || null;
}

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const applyTokens = useCallback((payload: AuthResponse) => {
    setAccessToken(payload.access_token);
    setRefreshToken(payload.refresh_token);
    persistTokens({ accessToken: payload.access_token, refreshToken: payload.refresh_token });
  }, []);

  const clearTokens = useCallback(() => {
    setAccessToken(null);
    setRefreshToken(null);
    persistTokens({ accessToken: null, refreshToken: null });
  }, []);

  const reloadProfile = useCallback(
    async (tokenOverride?: string) => {
      const tokenToUse = tokenOverride ?? accessToken;
      if (!tokenToUse) {
        setUser(null);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const profile = await getProfile(tokenToUse);
        setUser(profile);
      } catch (error) {
        console.error("Unable to load profile", error);
        clearTokens();
        setUser(null);
      } finally {
        setLoading(false);
      }
    },
    [accessToken, clearTokens]
  );

  const login = useCallback(
    async (payload: LoginPayload) => {
      const auth = await loginRequest(payload);
      applyTokens(auth);
      await reloadProfile(auth.access_token);
    },
    [applyTokens, reloadProfile]
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const auth = await registerRequest(payload);
      applyTokens(auth);
      await reloadProfile(auth.access_token);
    },
    [applyTokens, reloadProfile]
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
  }, [clearTokens]);

  const refreshTokens = useCallback(async () => {
    if (!refreshToken) return;
    try {
      const refreshed = await refreshTokenRequest(refreshToken);
      applyTokens(refreshed);
      await reloadProfile(refreshed.access_token);
    } catch (error) {
      console.error("Unable to refresh tokens", error);
      logout();
    }
  }, [applyTokens, logout, refreshToken, reloadProfile]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedAccess = readToken(ACCESS_TOKEN_KEY);
    const storedRefresh = readToken(REFRESH_TOKEN_KEY);
    if (storedAccess) {
      setAccessToken(storedAccess);
    }
    if (storedRefresh) {
      setRefreshToken(storedRefresh);
    }
  }, []);

  useEffect(() => {
    if (!accessToken) {
      setLoading(false);
      setUser(null);
      return;
    }

    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const profile = await getProfile(accessToken);
        if (!cancelled) {
          setUser(profile);
        }
      } catch (error) {
        console.error("Session invalid", error);
        if (!cancelled) {
          clearTokens();
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [accessToken, clearTokens]);

  useEffect(() => {
    if (!refreshToken) return;
    const interval = window.setInterval(() => {
      refreshTokens().catch((error) =>
        console.error("Scheduled refresh failed", error)
      );
    }, 1000 * 60 * 10); // every 10 minutes

    return () => window.clearInterval(interval);
  }, [refreshToken, refreshTokens]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      accessToken,
      refreshToken,
      loading,
      login,
      register,
      logout,
      refreshTokens,
      reloadProfile
    }),
    [
      accessToken,
      refreshToken,
      loading,
      login,
      logout,
      refreshTokens,
      register,
      reloadProfile,
      user
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
