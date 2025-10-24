import { renderHook, waitFor } from "@/tests/utils/renderWithProviders";
import { flushPromisesAndTimers } from "@/tests/utils/act-helpers";

import { fetchVapidPublicKey, subscribePush, unsubscribePush } from "@/lib/api";
import { usePushNotifications } from "../usePushNotifications";

jest.mock("@/lib/api", () => ({
  subscribePush: jest.fn().mockResolvedValue({ id: "sub" }),
  unsubscribePush: jest.fn().mockResolvedValue({ removed: true }),
  testNotificationDispatcher: jest.fn().mockResolvedValue({ status: "ok" }),
  fetchVapidPublicKey: jest.fn().mockResolvedValue("dGVzdA=="), // # QA fix: mockear obtención de clave VAPID
}));

describe("usePushNotifications", () => {
  const originalNotification = window.Notification;
  const originalGlobalNotification = global.Notification;
  const originalNavigator = global.navigator;
  const originalServiceWorker = navigator.serviceWorker;
  const originalPushManager = (window as any).PushManager;
  const originalAtob = (global as any).atob;
  const mockedSubscribePush = subscribePush as jest.MockedFunction<typeof subscribePush>;
  const mockedUnsubscribePush = unsubscribePush as jest.MockedFunction<typeof unsubscribePush>;
  const mockedFetchVapidPublicKey = fetchVapidPublicKey as jest.MockedFunction<
    typeof fetchVapidPublicKey
  >;
  let requestPermissionMock!: jest.Mock<Promise<NotificationPermission>, []>;
  let NotificationMock!: {
    permission: NotificationPermission;
    requestPermission: jest.Mock<Promise<NotificationPermission>, []>;
    new (title: string, options?: NotificationOptions): Notification;
  };

  beforeEach(() => {
    requestPermissionMock = jest
      .fn<Promise<NotificationPermission>, []>()
      .mockResolvedValue("default");

    class LocalNotificationMock {
      static permission: NotificationPermission = "default";
      static requestPermission: jest.Mock<Promise<NotificationPermission>, []> = requestPermissionMock;
      constructor(public _title: string, public _options?: NotificationOptions) {}
    }

    Object.defineProperty(global, "Notification", {
      configurable: true,
      value: LocalNotificationMock,
    });
    Object.defineProperty(window, "Notification", {
      configurable: true,
      value: LocalNotificationMock,
    });

    NotificationMock = window.Notification as unknown as {
      permission: NotificationPermission;
      requestPermission: jest.Mock<Promise<NotificationPermission>, []>;
      new (title: string, options?: NotificationOptions): Notification;
    };

    (global as any).navigator = { serviceWorker: {} } as any;
    (global as any).window = Object.assign(global.window || {}, {
      PushManager: function PushManager() {},
    });

    process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY = "dGVzdA==";
    process.env.NEXT_PUBLIC_VAPID_KEY = "dGVzdA==";
    mockedFetchVapidPublicKey.mockResolvedValue("dGVzdA==");
    mockedSubscribePush.mockResolvedValue({ id: "sub" });

    (global as any).atob = (value: string) => Buffer.from(value, "base64").toString("binary");

    const subscription = {
      endpoint: "https://example.com/push",
      expirationTime: null,
      toJSON: () => ({ keys: { auth: "auth", p256dh: "p256dh" } }),
      unsubscribe: jest.fn().mockResolvedValue(true),
    } as unknown as PushSubscription;

    const registration = {
      pushManager: {
        getSubscription: jest.fn().mockResolvedValue(null),
        subscribe: jest.fn().mockResolvedValue(subscription),
      },
    } as unknown as ServiceWorkerRegistration;

    (global as any).navigator.serviceWorker = {
      register: jest.fn().mockResolvedValue(registration),
      ready: Promise.resolve(registration),
    };

    const typedNotification = window.Notification as unknown as {
      permission: NotificationPermission;
      requestPermission: jest.Mock<Promise<NotificationPermission>, []>;
    };
    typedNotification.permission = "granted";
    typedNotification.requestPermission.mockResolvedValue("granted");
  });

  afterEach(() => {
    if (originalGlobalNotification) {
      Object.defineProperty(global, "Notification", {
        configurable: true,
        value: originalGlobalNotification,
      });
    } else {
      delete (global as any).Notification;
    }
    Object.defineProperty(window, "Notification", {
      configurable: true,
      value: originalNotification,
    });
    if (originalNavigator) {
      (global as any).navigator = originalNavigator;
    } else {
      delete (global as any).navigator;
    }
    if (originalNavigator && originalServiceWorker) {
      Object.defineProperty(originalNavigator, "serviceWorker", {
        configurable: true,
        value: originalServiceWorker,
      });
    }
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
    requestPermissionMock.mockReset();
    mockedSubscribePush.mockClear();
    mockedUnsubscribePush.mockClear();
    mockedFetchVapidPublicKey.mockClear();
    delete process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
    delete process.env.NEXT_PUBLIC_VAPID_KEY;
  });

  it("registra la suscripción cuando el navegador soporta push", async () => {
    NotificationMock.permission = "granted";
    requestPermissionMock.mockResolvedValue("granted");
    const { result } = renderHook(() => usePushNotifications("token"));

    await waitFor(() => expect(result.current.enabled).toBe(true));
    expect(result.current.subscription).not.toBeNull();

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
    NotificationMock.permission = "default";
    requestPermissionMock.mockResolvedValue("default");
    process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY = "";
    process.env.NEXT_PUBLIC_VAPID_KEY = "";
    mockedFetchVapidPublicKey.mockResolvedValueOnce(null);
    mockedFetchVapidPublicKey.mockResolvedValueOnce(null);

    const { result } = renderHook(() => usePushNotifications("token"));

    await flushPromisesAndTimers();

    expect(result.current.enabled).toBe(false);
    expect(result.current.isSupported).toBe(false);
    expect(result.current.error).toMatch(/clave pública VAPID/i);
    expect(mockedSubscribePush).not.toHaveBeenCalled();
  });

  it("evita suscripción cuando la clave VAPID es placeholder", async () => {
    NotificationMock.permission = "default";
    requestPermissionMock.mockResolvedValue("default");
    process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY = "BB_placeholder";
    mockedFetchVapidPublicKey.mockResolvedValue("BB_placeholder");

    const { result } = renderHook(() => usePushNotifications("token"));

    await flushPromisesAndTimers();

    expect(result.current.enabled).toBe(false);
    expect(result.current.isSupported).toBe(false);
    expect(result.current.error).toMatch(/clave pública VAPID/i);
    expect(mockedSubscribePush).not.toHaveBeenCalled();
  });

  // ✅ Codex fix: test para verificar comportamiento habilitado del hook
  test("marca enabled=true cuando Notification.permission='granted' y serviceWorker existe", async () => {
    NotificationMock.permission = "granted";
    requestPermissionMock.mockResolvedValue("granted");
    const { result } = renderHook(() => usePushNotifications("token"));
    await waitFor(() => expect(result.current.enabled).toBe(true));
  });

  it("permite desuscribirse y sincroniza el backend", async () => {
    NotificationMock.permission = "granted";
    requestPermissionMock.mockResolvedValue("granted");
    const { result } = renderHook(() => usePushNotifications("token"));

    await waitFor(() => expect(result.current.subscription).not.toBeNull());

    const registration = await navigator.serviceWorker.ready;
    const activeSubscription = result.current.subscription!;

    (registration.pushManager.getSubscription as jest.Mock).mockResolvedValue(activeSubscription);

    await result.current.unsubscribe();

    const unsubscribeMock = activeSubscription.unsubscribe as unknown as jest.Mock;
    expect(unsubscribeMock).toHaveBeenCalled();
    expect(mockedUnsubscribePush).toHaveBeenCalledWith(activeSubscription.endpoint, "token");
  });
});
