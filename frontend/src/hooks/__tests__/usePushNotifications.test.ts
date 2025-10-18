import { renderHook, waitFor } from "@/tests/utils/renderWithProviders";
import { flushPromisesAndTimers } from "@/tests/utils/act-helpers";

import { fetchVapidPublicKey, subscribePush } from "@/lib/api";
import { usePushNotifications } from "../usePushNotifications";

// # QA fix: mock seguro para Notification y ServiceWorker (evita redefinir varias veces)
beforeAll(() => {
  if (!global.Notification) {
    Object.defineProperty(global, "Notification", {
      value: { permission: "granted" },
      configurable: true,
      writable: true,
    });
  }

  if (!navigator.serviceWorker) {
    Object.defineProperty(navigator, "serviceWorker", {
      value: {
        register: jest.fn().mockResolvedValue({}),
        ready: Promise.resolve({
          pushManager: {
            subscribe: jest.fn().mockResolvedValue({ endpoint: "mock" }),
          },
        }),
      },
      configurable: true,
      writable: true,
    });
  }
});

jest.mock("@/lib/api", () => ({
  subscribePush: jest.fn().mockResolvedValue({ id: "sub" }),
  testNotificationDispatcher: jest.fn().mockResolvedValue({ status: "ok" }),
  fetchVapidPublicKey: jest.fn().mockResolvedValue("dGVzdA=="), // # QA fix: mockear obtención de clave VAPID
}));

describe("usePushNotifications", () => {
  const originalNotification = window.Notification;
  const originalServiceWorker = navigator.serviceWorker;
  const originalPushManager = (window as any).PushManager;
  const originalAtob = (global as any).atob;
  const mockedSubscribePush = subscribePush as jest.MockedFunction<typeof subscribePush>;
  const mockedFetchVapidPublicKey = fetchVapidPublicKey as jest.MockedFunction<
    typeof fetchVapidPublicKey
  >;

  beforeEach(() => {
    process.env.NEXT_PUBLIC_PUSH_VAPID_PUBLIC_KEY = "dGVzdA==";
    process.env.NEXT_PUBLIC_VAPID_KEY = "dGVzdA==";

    (global as any).atob = (value: string) => Buffer.from(value, "base64").toString("binary");

    const registration = {
      pushManager: {
        getSubscription: jest.fn().mockResolvedValue(null),
        subscribe: jest.fn().mockResolvedValue({
          endpoint: "https://example.com/push",
          toJSON: () => ({ keys: { auth: "auth", p256dh: "p256dh" } }),
        }),
      },
    } as unknown as ServiceWorkerRegistration;

    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: {
        register: jest.fn().mockResolvedValue(registration),
        ready: Promise.resolve(registration), // # QA fix: exponer ready con pushManager mockeado
      },
    });

    Object.defineProperty(window, "PushManager", {
      configurable: true,
      value: function PushManager() {},
    });

    class MockNotification {
      static permission: NotificationPermission = "granted";
      static async requestPermission(): Promise<NotificationPermission> {
        MockNotification.permission = "granted";
        return MockNotification.permission;
      }
    }

    Object.defineProperty(window, "Notification", {
      configurable: true,
      value: MockNotification,
    });
    Object.defineProperty(global, "Notification", {
      configurable: true,
      writable: true,
      value: MockNotification, // # QA fix: reutilizar clase mock para Notification global
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "Notification", {
      configurable: true,
      value: originalNotification,
    });
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: originalServiceWorker,
    });
    if (originalPushManager) {
      Object.defineProperty(window, "PushManager", {
        configurable: true,
        value: originalPushManager,
      });
    } else {
      delete (window as any).PushManager;
    }
    if (originalAtob) {
      (global as any).atob = originalAtob;
    } else {
      delete (global as any).atob;
    }
    mockedSubscribePush.mockClear();
  });

  it("registra la suscripción cuando el navegador soporta push", async () => {
    const { result } = renderHook(() => usePushNotifications("token"));

    await waitFor(() => expect(result.current.enabled).toBe(true));

    expect(mockedSubscribePush).toHaveBeenCalledWith(
      {
        endpoint: "https://example.com/push",
        expirationTime: null,
        keys: { auth: "auth", p256dh: "p256dh" },
      },
      "token",
    );
    expect(result.current.error).toBeNull();
  });

  it("reporta error cuando falta la clave VAPID", async () => {
    process.env.NEXT_PUBLIC_PUSH_VAPID_PUBLIC_KEY = "";
    process.env.NEXT_PUBLIC_VAPID_KEY = "";
    mockedFetchVapidPublicKey.mockResolvedValueOnce(null);

    const { result } = renderHook(() => usePushNotifications("token"));

    await flushPromisesAndTimers();

    expect(result.current.enabled).toBe(false);
    expect(result.current.error).toMatch(/clave pública VAPID/i);
    expect(mockedSubscribePush).not.toHaveBeenCalled();
  });

  // ✅ Codex fix: test para verificar comportamiento habilitado del hook
  test("marca enabled=true cuando Notification.permission='granted' y serviceWorker existe", async () => {
    const { result } = renderHook(() => usePushNotifications("token"));
    await waitFor(() => expect(result.current.enabled).toBe(true));
  });
});
