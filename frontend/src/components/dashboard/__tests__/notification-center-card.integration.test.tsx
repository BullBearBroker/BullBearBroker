// 🧩 Bloque 8B
import { render, screen, fireEvent } from "@testing-library/react";

// 🧩 Bloque 9B
jest.mock("@/components/providers/auth-provider", () => ({
  useAuth: jest.fn(() => ({ token: null })),
}));
// 🧩 Bloque 9B
const { useAuth: mockUseAuth } = jest.requireMock("@/components/providers/auth-provider") as {
  useAuth: jest.Mock;
};
// 🧩 Bloque 9B
jest.mock("@/hooks/useLiveNotifications", () => ({
  useLiveNotifications: jest.fn(() => ({ events: [], status: "fallback" })),
}));
// 🧩 Bloque 9B
const { useLiveNotifications: mockUseLiveNotifications } = jest.requireMock(
  "@/hooks/useLiveNotifications",
) as {
  useLiveNotifications: jest.Mock;
};
// QA: mock push notifications hook para controlar UI sin requerir Service Worker real
jest.mock("@/hooks/usePushNotifications", () => ({
  usePushNotifications: jest.fn(() => ({
    enabled: false,
    error: null,
    isSupported: true,
    permission: "granted" as NotificationPermission,
    loading: false,
    testing: false,
    events: [],
    logs: [],
    notificationHistory: [],
    lastEvent: null,
    subscription: null,
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
    sendTestNotification: jest.fn(),
    requestPermission: jest.fn().mockResolvedValue("granted"),
    dismissEvent: jest.fn(),
    clearLogs: jest.fn(),
  })),
}));
const { usePushNotifications: mockUsePushNotifications } = jest.requireMock(
  "@/hooks/usePushNotifications",
) as {
  usePushNotifications: jest.Mock;
};

import NotificationCenterCard from "../notification-center-card";

describe("NotificationCenterCard", () => {
  const originalNotification = window.Notification;
  let currentPushState: ReturnType<typeof mockUsePushNotifications>;

  beforeEach(() => {
    localStorage.clear();
    mockUseAuth.mockReturnValue({ token: null });
    mockUseLiveNotifications.mockReturnValue({ events: [], status: "fallback" });
    process.env.NEXT_PUBLIC_FEATURE_NOTIFICATIONS_DEBUG = "false";
    currentPushState = {
      enabled: false,
      error: null,
      isSupported: true,
      permission: "granted" as NotificationPermission,
      loading: false,
      testing: false,
      events: [],
      logs: [],
      notificationHistory: [],
      lastEvent: null,
      subscription: null,
      subscribe: jest.fn(),
      unsubscribe: jest.fn(),
      sendTestNotification: jest.fn(),
      requestPermission: jest.fn().mockResolvedValue("granted"),
      dismissEvent: jest.fn(),
      clearLogs: jest.fn(),
    };
    mockUsePushNotifications.mockReturnValue(currentPushState);
    class MockNotification {
      static permission: NotificationPermission = "granted";
      static async requestPermission() {
        return this.permission;
      }
    }
    // @ts-expect-error - mock constructor
    window.Notification = MockNotification;
  });

  afterEach(() => {
    window.Notification = originalNotification;
    delete process.env.NEXT_PUBLIC_FEATURE_NOTIFICATIONS_DEBUG;
  });

  it("renders and handles push actions", async () => {
    render(<NotificationCenterCard />);

    expect(screen.getByText("Notificaciones en vivo")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Enviar prueba/i }));
    expect(currentPushState.sendTestNotification).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /Limpiar/i }));
    expect(currentPushState.clearLogs).toHaveBeenCalled();
  });

  // 🧩 Bloque 9B
  it("shows live connection state indicator", () => {
    render(<NotificationCenterCard />);
    expect(screen.getByText(/Canal en modo seguro/i)).toBeInTheDocument();
  });

  it("no renderiza el panel de debug cuando el flag está deshabilitado", () => {
    process.env.NEXT_PUBLIC_FEATURE_NOTIFICATIONS_DEBUG = "false";
    render(<NotificationCenterCard />);
    expect(screen.queryByText(/Debug Web Push/)).not.toBeInTheDocument();
  });

  it("muestra el panel de debug cuando la flag está activa", () => {
    process.env.NEXT_PUBLIC_FEATURE_NOTIFICATIONS_DEBUG = "true";
    render(<NotificationCenterCard />);
    expect(screen.getByText(/Debug Web Push/)).toBeInTheDocument();
  });
});
