"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { login as apiLogin, refreshToken, getProfile, AuthResponse, UserProfile } from "@/lib/api";

export interface AuthContextType {
  user: UserProfile | null;
  accessToken: string | null;
  refreshToken: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshTokenValue, setRefreshTokenValue] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Cargar tokens desde localStorage al iniciar
  useEffect(() => {
    const storedAccess = localStorage.getItem("access_token");
    const storedRefresh = localStorage.getItem("refresh_token");
    if (storedAccess && storedRefresh) {
      setAccessToken(storedAccess);
      setRefreshTokenValue(storedRefresh);
      refreshSession(storedRefresh);
    } else {
      setLoading(false);
    }
  }, []);

  async function refreshSession(rToken: string) {
    try {
      const data = await refreshToken(rToken);
      setAccessToken(data.access_token);
      setRefreshTokenValue(data.refresh_token);
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      const profile = await getProfile(data.access_token);
      setUser(profile);
    } catch (err) {
      console.error("No se pudo refrescar sesión:", err);
      logout();
    } finally {
      setLoading(false);
    }
  }

  async function login(email: string, password: string) {
    setLoading(true);
    try {
      const data: AuthResponse = await apiLogin({ email, password });
      setAccessToken(data.access_token);
      setRefreshTokenValue(data.refresh_token);
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      const profile = await getProfile(data.access_token);
      setUser(profile);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    setUser(null);
    setAccessToken(null);
    setRefreshTokenValue(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  return (
    <AuthContext.Provider
      value={{ user, accessToken, refreshToken: refreshTokenValue, login, logout, loading }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
