import userEvent from "@testing-library/user-event";

import {
  customRender,
  renderHook,
  screen,
  waitFor,
  within,
} from "@/tests/utils/renderWithProviders";
import { withAct, flushPromisesAndTimers } from "@/tests/utils/act-helpers";

import { usePushNotifications } from "../usePushNotifications";
import {
  fetchVapidPublicKey,
  subscribePush,
  testNotificationDispatcher,
  unsubscribePush,
} from "@/lib/api";

jest.mock("@/lib/api", () => ({
  fetchVapidPublicKey: jest.fn(),
  subscribePush: jest.fn(),
  unsubscribePush: jest.fn(),
  testNotificationDispatcher: jest.fn(),
}));

const mockedSubscribePush = subscribePush as jest.MockedFunction<typeof subscribePush>;
const mockedTestNotificationDispatcher = testNotificationDispatcher as jest.MockedFunction<
  typeof testNotificationDispatcher
>;
const mockedFetchVapidPublicKey = fetchVapidPublicKey as jest.MockedFunction<
  typeof fetchVapidPublicKey
>;
const mockedUnsubscribePush = unsubscribePush as jest.MockedFunction<typeof unsubscribePush>;

describe("usePushNotifications integration", () => {
  const originalNotification = window.Notification;
  const originalGlobalNotification = global.Notification;
  const originalNavigator = global.navigator;
  const originalServiceWorker = navigator.serviceWorker;
  const originalPushManager = (window as any).PushManager;
  const originalAtob = (global as any).atob;
  let dispatchServiceWorkerMessage: ((data: unknown) => void) | undefined;
  let notificationRequestPermissionMock: jest.Mock<Promise<NotificationPermission>, []>;

  beforeEach(() => {
    process.env.NEXT_PUBLIC_VAPID_KEY = "dGVzdA==";
    process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY = "dGVzdA==";
    mockedSubscribePush.mockResolvedValue({ id: "subscription" });
    mockedTestNotificationDispatcher.mockResolvedValue({ status: "ok", sent: 1 });
    mockedFetchVapidPublicKey.mockResolvedValue(process.env.NEXT_PUBLIC_VAPID_KEY ?? "");
    (global as any).atob = (value: string) => Buffer.from(value, "base64").toString("binary");

    notificationRequestPermissionMock = jest
      .fn<Promise<NotificationPermission>, []>()
      .mockResolvedValue("default");

    class MockNotification {
      static permission: NotificationPermission = "default";
      static requestPermission: jest.Mock<Promise<NotificationPermission>, []> =
        notificationRequestPermissionMock;
      constructor(public _title: string, public _options?: NotificationOptions) {}
    }

    Object.defineProperty(global, "Notification", {
      configurable: true,
      value: MockNotification,
    });

    Object.defineProperty(window, "Notification", {
      configurable: true,
      value: MockNotification,
    });

    (global as any).navigator = { serviceWorker: {} } as any;
    (global as any).window = Object.assign(global.window || {}, {
      PushManager: function PushManager() {},
    });

    Object.defineProperty(window, "PushManager", {
      configurable: true,
      value: function PushManager() {},
    });

    const eventTarget = new EventTarget();
    dispatchServiceWorkerMessage = (data: unknown) => {
      const message = new MessageEvent("message", { data });
      eventTarget.dispatchEvent(message);
    };

    const subscription = {
      endpoint: "https://example.com/push",
      expirationTime: null,
      toJSON: () => ({ keys: { auth: "auth", p256dh: "p256dh" } }),
      unsubscribe: jest.fn().mockResolvedValue(true),
    } as unknown as PushSubscription;

    const registration = {
      pushManager: {
        getSubscription: jest.fn().mockResolvedValue(subscription),
      },
    } as unknown as ServiceWorkerRegistration;

    (global as any).navigator.serviceWorker = {
      register: jest.fn().mockResolvedValue(registration),
      ready: Promise.resolve(registration),
      getRegistration: jest.fn().mockResolvedValue(registration),
      addEventListener: eventTarget.addEventListener.bind(eventTarget),
      removeEventListener: eventTarget.removeEventListener.bind(eventTarget),
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
    mockedSubscribePush.mockClear();
    mockedUnsubscribePush.mockClear();
    mockedTestNotificationDispatcher.mockClear();
    mockedFetchVapidPublicKey.mockClear();
    notificationRequestPermissionMock?.mockReset();
    delete process.env.NEXT_PUBLIC_VAPID_KEY;
    delete process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
  });

  const Harness = ({ token = "secure-token" }: { token?: string }) => {
    const { events, logs, sendTestNotification, testing, enabled } = usePushNotifications(token);

    return (
      <div>
        <button
          data-testid="send-test"
          disabled={testing}
          onClick={() => void sendTestNotification()}
        >
          enviar
        </button>
        <output data-testid="enabled">{String(enabled)}</output>
        <ul data-testid="events">
          {events.map((event) => (
            <li key={event.id}>{event.title}</li>
          ))}
        </ul>
        <ul data-testid="logs">
          {logs.map((log, index) => (
            <li key={`${log}-${index}`}>{log}</li>
          ))}
        </ul>
      </div>
    );
  };

  it("recibe eventos del dispatcher y registra logs", async () => {
    customRender(<Harness />);

    await waitFor(() => expect(mockedSubscribePush).toHaveBeenCalled());
    if (dispatchServiceWorkerMessage) {
      await withAct(async () => {
        dispatchServiceWorkerMessage?.({
          type: "notification:dispatcher",
          title: "BullBearBroker Test",
          body: "Mensaje de prueba",
          payload: { origin: "jest" },
          receivedAt: "2023-01-01T00:00:00.000Z",
        });
      });
      await flushPromisesAndTimers();
    }
    await waitFor(() =>
      expect(
        within(screen.getByTestId("events")).getByText("BullBearBroker Test"),
      ).toBeInTheDocument(),
    );

    const logsList = within(screen.getByTestId("logs"));
    expect(
      logsList
        .getAllByRole("listitem")
        .some((item) => item.textContent?.includes("Evento recibido")),
    ).toBe(true);

    const trigger = screen.getByTestId("send-test");
    await withAct(async () => {
      await userEvent.click(trigger);
    });
    await flushPromisesAndTimers();
    expect(mockedTestNotificationDispatcher).toHaveBeenCalledWith("secure-token");
    expect(
      logsList
        .getAllByRole("listitem")
        .some((item) => item.textContent?.includes("Push recibido correctamente")),
    ).toBe(true);
  });

  it("maneja permisos denegados sin lanzar errores", async () => {
    notificationRequestPermissionMock.mockResolvedValue("denied");
    const MockNotification = window.Notification as unknown as {
      permission: NotificationPermission;
      requestPermission: jest.Mock<Promise<NotificationPermission>, []>;
    };
    MockNotification.permission = "denied";
    MockNotification.requestPermission.mockResolvedValue("denied");

    customRender(<Harness token="token-denegado" />);

    await waitFor(() => expect(screen.getByTestId("enabled")).toHaveTextContent("false"));
    expect(mockedSubscribePush).not.toHaveBeenCalled();
    expect(mockedTestNotificationDispatcher).not.toHaveBeenCalled();
  });

  // 🧩 Bloque 8A
  test("should fail gracefully if VAPID key is missing or placeholder", async () => {
    notificationRequestPermissionMock.mockResolvedValue("default");
    const notification = window.Notification as unknown as {
      permission: NotificationPermission;
      requestPermission: jest.Mock<Promise<NotificationPermission>, []>;
    };
    notification.permission = "default";
    process.env.NEXT_PUBLIC_VAPID_KEY = "";
    process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY = "";
    mockedFetchVapidPublicKey.mockResolvedValue("");

    const { result } = renderHook(() => usePushNotifications("secure-token"));

    await flushPromisesAndTimers();

    expect(result.current.isSupported).toBe(false);
    expect(result.current.enabled).toBe(false);
    expect(result.current.permission).toBe("unsupported");
    expect(result.current.error).toMatch(/clave pública VAPID/i);
    expect(mockedSubscribePush).not.toHaveBeenCalled();
  });
});
