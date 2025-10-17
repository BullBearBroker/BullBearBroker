// 🧩 Codex fix
import { render, screen, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import NotificationCenterCard from "../notification-center-card";
import { useLiveNotifications, type NotificationEvent } from "@/hooks/useLiveNotifications";
import * as pushHook from "@/hooks/usePushNotifications";
import { createMockNotificationEvent } from "@/tests/mocks/notifications";

jest.mock("@/hooks/useLiveNotifications", () => ({
  __esModule: true,
  useLiveNotifications: jest.fn(),
}));

jest.mock("@/components/providers/auth-provider", () => ({
  useAuth: () => ({
    user: { email: "tester@example.com" },
    token: "mock-token",
    loading: false,
    loginUser: jest.fn(),
    registerUser: jest.fn(),
    logout: jest.fn(),
  }),
}));
const mockedUseLiveNotifications = useLiveNotifications as jest.MockedFunction<
  typeof useLiveNotifications
>;

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

describe("🔔 NotificationCenterCard (WebSocket integration)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(pushHook, "usePushNotifications").mockReturnValue({
      enabled: true,
      error: null,
      permission: "granted",
      loading: false,
      testing: false,
      events: [],
      logs: [],
      notificationHistory: [],
      lastEvent: null,
      sendTestNotification: jest.fn().mockResolvedValue(undefined),
      requestPermission: jest.fn().mockResolvedValue("granted"),
      dismissEvent: jest.fn(),
      clearLogs: jest.fn(),
    });
  });

  it("muestra un toast al recibir un evento WS simulado", async () => {
    mockedUseLiveNotifications.mockReturnValue({
      events: [
        createMockNotificationEvent({
          id: "test-ws-001",
          title: "🚀 Notificación de prueba",
          body: "Emitida en test simulado",
          type: "test",
        }) as NotificationEvent,
      ],
      status: "connected",
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <NotificationCenterCard />
      </SWRConfig>,
    );

    await waitFor(() => {
      expect(screen.getByText("🚀 Notificación de prueba")).toBeInTheDocument();
    });

    expect(screen.getByText(/Emitida en test simulado/)).toBeInTheDocument();
  });
});
