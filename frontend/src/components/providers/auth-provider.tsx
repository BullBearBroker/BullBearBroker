"use client";

import {
  AuthResponse,
  UserProfile,
  getProfile,
  login,
  register,
  refreshToken
} from "@/lib/api";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";

interface AuthContextProps {
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
  loginUser: (
    email: string,
    password: string,
    options?: { signal?: AbortSignal }
  ) => Promise<void>;
  registerUser: (
    email: string,
    password: string,
    name?: string,
    riskProfile?: "conservador" | "moderado" | "agresivo"
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextProps | undefined>(undefined);

function persistRefreshToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem("refresh_token", token);
  } else {
    localStorage.removeItem("refresh_token");
  }
}

async function fetchProfile(accessToken: string) {
  return getProfile(accessToken);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const savedRefresh = localStorage.getItem("refresh_token");
    if (!savedRefresh) {
      setLoading(false);
      return;
    }

    let active = true;

    const hydrateSession = async () => {
      try {
        const refreshed = await refreshToken(savedRefresh);
        if (!active) return;
        setToken(refreshed.access_token);
        persistRefreshToken(refreshed.refresh_token);
        const profile = await fetchProfile(refreshed.access_token);
        if (!active) return;
        setUser(profile);
      } catch (error) {
        if (!active) return;
        console.error("No se pudo refrescar la sesión", error);
        persistRefreshToken(null);
        setToken(null);
        setUser(null);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    hydrateSession();

    return () => {
      active = false;
    };
  }, []);

  const persistSession = useCallback((response: AuthResponse) => {
    setToken(response.access_token);
    persistRefreshToken(response.refresh_token);
  }, []);

  const loginUser = useCallback(
    async (email: string, password: string, options?: { signal?: AbortSignal }) => {
      setLoading(true);
      try {
        const auth = await login({ email, password }, { signal: options?.signal });
        persistSession(auth);
        const profile = await fetchProfile(auth.access_token);
        setUser(profile);
      } catch (error) {
        persistRefreshToken(null);
        setToken(null);
        setUser(null);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [persistSession]
  );

  const registerUser = useCallback(
    async (
      email: string,
      password: string,
      name?: string,
      riskProfile?: "conservador" | "moderado" | "agresivo"
    ) => {
      setLoading(true);
      try {
        const auth = await register({ email, password, name, risk_profile: riskProfile });
        persistSession(auth);
        const profile = await fetchProfile(auth.access_token);
        setUser(profile);
      } catch (error) {
        persistRefreshToken(null);
        setToken(null);
        setUser(null);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [persistSession]
  );

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    persistRefreshToken(null);
  }, []);

  const value = useMemo(
    () => ({ user, token, loading, loginUser, registerUser, logout }),
    [loading, loginUser, logout, registerUser, token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export const authProviderTestUtils = {
  persistRefreshToken,
};
