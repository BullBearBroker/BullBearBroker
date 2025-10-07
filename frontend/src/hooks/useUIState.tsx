"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";
import { useTheme } from "next-themes";

interface UIStateContextValue {
  sidebarOpen: boolean;
  setSidebarOpen: Dispatch<SetStateAction<boolean>>;
  openSidebar: () => void;
  closeSidebar: () => void;
  toggleSidebar: () => void;
  toastVisible: boolean;
  setToastVisible: Dispatch<SetStateAction<boolean>>;
  theme: string | undefined;
  setTheme: (theme: string) => void;
}

export const UIStateContext = createContext<UIStateContextValue | undefined>(undefined);

export function UIStateProvider({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toastVisible, setToastVisible] = useState(false);
  const { theme, resolvedTheme, setTheme } = useTheme();

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    const { body } = document;
    if (!body) {
      return;
    }

    if (sidebarOpen) {
      body.classList.add("overflow-hidden", "md:overflow-auto");
    } else {
      body.classList.remove("overflow-hidden", "md:overflow-auto");
    }
  }, [sidebarOpen]);

  const openSidebar = useCallback(() => setSidebarOpen(true), []);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);
  const toggleSidebar = useCallback(
    () => setSidebarOpen((previous) => !previous),
    [],
  );

  const contextValue = useMemo<UIStateContextValue>(() => {
    const currentTheme = theme === "system" ? resolvedTheme ?? theme : theme;

    return {
      sidebarOpen,
      setSidebarOpen,
      openSidebar,
      closeSidebar,
      toggleSidebar,
      toastVisible,
      setToastVisible,
      theme: currentTheme,
      setTheme,
    };
  }, [
    closeSidebar,
    openSidebar,
    resolvedTheme,
    setTheme,
    sidebarOpen,
    theme,
    toastVisible,
    toggleSidebar,
  ]);

  return <UIStateContext.Provider value={contextValue}>{children}</UIStateContext.Provider>;
}

export function useOptionalUIState() {
  return useContext(UIStateContext);
}

export function useUIState() {
  const context = useOptionalUIState();

  if (!context) {
    throw new Error("useUIState debe usarse dentro de un UIStateProvider");
  }

  return context;
}
