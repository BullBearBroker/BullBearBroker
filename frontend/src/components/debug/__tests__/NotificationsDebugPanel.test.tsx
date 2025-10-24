import { render, screen } from "@testing-library/react";

import NotificationsDebugPanel from "../NotificationsDebugPanel";

const basePushState = {
  enabled: false,
  error: null as string | null,
  isSupported: true,
  permission: "default" as NotificationPermission,
  loading: false,
  testing: false,
  events: [],
  logs: [] as string[],
  notificationHistory: [],
  lastEvent: null,
  subscription: null,
  subscribe: jest.fn(),
  unsubscribe: jest.fn().mockResolvedValue(true),
  sendTestNotification: jest.fn().mockResolvedValue(undefined),
  requestPermission: jest.fn().mockResolvedValue("granted" as NotificationPermission),
  dismissEvent: jest.fn(),
  clearLogs: jest.fn(),
};

describe("NotificationsDebugPanel", () => {
  const originalEnv = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;

  afterEach(() => {
    process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY = originalEnv;
    jest.clearAllMocks();
  });

  it("deshabilita la suscripción cuando la clave VAPID es placeholder", () => {
    process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY = "BB_placeholder";
    render(<NotificationsDebugPanel pushState={basePushState} token={undefined} />);
    expect(screen.getByRole("button", { name: /^Suscribirse$/ })).toBeDisabled();
  });

  it("mantiene la suscripción habilitada cuando la clave VAPID es válida", () => {
    process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY = "valid_key";
    render(<NotificationsDebugPanel pushState={basePushState} token={undefined} />);
    expect(screen.getByRole("button", { name: /^Suscribirse$/ })).not.toBeDisabled();
  });
});
