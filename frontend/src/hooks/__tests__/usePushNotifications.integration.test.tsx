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
import { fetchVapidPublicKey, subscribePush, testNotificationDispatcher } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  fetchVapidPublicKey: jest.fn(),
  subscribePush: jest.fn(),
  testNotificationDispatcher: jest.fn(),
}));

const mockedSubscribePush = subscribePush as jest.MockedFunction<typeof subscribePush>;
const mockedTestNotificationDispatcher = testNotificationDispatcher as jest.MockedFunction<
  typeof testNotificationDispatcher
>;
const mockedFetchVapidPublicKey = fetchVapidPublicKey as jest.MockedFunction<
  typeof fetchVapidPublicKey
>;

describe("usePushNotifications integration", () => {
  const originalNotification = window.Notification;
  const originalServiceWorker = navigator.serviceWorker;
  const originalPushManager = (window as any).PushManager;
  const originalAtob = (global as any).atob;
  let dispatchServiceWorkerMessage: ((data: unknown) => void) | undefined;

  beforeEach(() => {
    process.env.NEXT_PUBLIC_VAPID_KEY = "dGVzdA==";
    mockedSubscribePush.mockResolvedValue({ id: "subscription" });
    mockedTestNotificationDispatcher.mockResolvedValue({ status: "ok", sent: 1 });
    mockedFetchVapidPublicKey.mockResolvedValue(process.env.NEXT_PUBLIC_VAPID_KEY ?? "");
    (global as any).atob = (value: string) => Buffer.from(value, "base64").toString("binary");

    class MockNotification {
      static permission: NotificationPermission = "granted";
      static async requestPermission() {
        return this.permission;
      }
    }

    Object.defineProperty(window, "Notification", {
      configurable: true,
      value: MockNotification,
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
    } as unknown as PushSubscription;

    const registration = {
      pushManager: {
        getSubscription: jest.fn().mockResolvedValue(subscription),
      },
    } as unknown as ServiceWorkerRegistration;

    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: {
        register: jest.fn().mockResolvedValue(registration),
        ready: Promise.resolve(registration),
        getRegistration: jest.fn().mockResolvedValue(registration),
        addEventListener: eventTarget.addEventListener.bind(eventTarget),
        removeEventListener: eventTarget.removeEventListener.bind(eventTarget),
      },
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
    mockedSubscribePush.mockReset();
    mockedTestNotificationDispatcher.mockReset();
    mockedFetchVapidPublicKey.mockReset();
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
    const MockNotification = window.Notification as unknown as {
      permission: NotificationPermission;
      requestPermission: () => Promise<NotificationPermission>;
    };
    MockNotification.permission = "denied";

    customRender(<Harness token="token-denegado" />);

    await waitFor(() => expect(screen.getByTestId("enabled")).toHaveTextContent("false"));
    expect(mockedSubscribePush).not.toHaveBeenCalled();
    expect(mockedTestNotificationDispatcher).not.toHaveBeenCalled();
  });

  // 🧩 Bloque 8A
  test("should fail gracefully if VAPID key mismatches or missing", async () => {
    mockedFetchVapidPublicKey.mockResolvedValueOnce("");

    const { result } = renderHook(() => usePushNotifications("secure-token"));

    await withAct(async () => result.current.requestPermission());
    await flushPromisesAndTimers();

    await waitFor(() => expect(result.current.permission).toBe("unsupported"));

    expect(result.current.permission).toBe("unsupported");
  });
});
