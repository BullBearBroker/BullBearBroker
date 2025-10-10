import { act, renderHook } from "@/tests/utils/renderWithProviders";

import { useLiveNotifications } from "../useLiveNotifications";

// QA: mock de SWR para inyectar datos controlados en los efectos.
const useSWRMock = jest.fn((key?: string | null, _fetcher?: unknown, _config?: unknown) => ({
  data: key ? currentFallbackData : undefined,
}));

jest.mock("swr", () => ({
  __esModule: true,
  default: (...args: unknown[]) => useSWRMock(...(args as [string | null, unknown, unknown])),
}));

let currentFallbackData: unknown;

class WebSocketMock {
  static instances: WebSocketMock[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;
  url: string;

  constructor(url: string) {
    this.url = url;
    WebSocketMock.instances.push(this);
  }

  close() {
    this.closed = true;
  }
}

describe("useLiveNotifications", () => {
  const originalWebSocket = window.WebSocket;
  let consoleErrorSpy: jest.SpyInstance;

  beforeEach(() => {
    currentFallbackData = undefined;
    useSWRMock.mockClear();
    (window as any).WebSocket = WebSocketMock as unknown as typeof WebSocket;
    consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    window.WebSocket = originalWebSocket as typeof WebSocket;
    consoleErrorSpy.mockRestore();
    WebSocketMock.instances = [];
  });

  it("hidrata eventos desde el fallback cuando no hay token", async () => {
    currentFallbackData = [
      { id: "1", title: "Hola", body: "test", timestamp: "2024-01-01T00:00:00Z" },
    ];

    const { result } = renderHook(() => useLiveNotifications(null));

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.status).toBe("fallback");
    expect(result.current.events).toHaveLength(1);
    expect(useSWRMock).toHaveBeenCalledWith("/api/notifications/logs", expect.any(Function), {
      refreshInterval: 5000,
    });
  });

  it("se conecta vía WebSocket y agrega mensajes entrantes", async () => {
    currentFallbackData = undefined;

    const { result } = renderHook(() => useLiveNotifications("token"));

    expect(WebSocketMock.instances).toHaveLength(1);
    expect(WebSocketMock.instances[0].url).toContain("token=token");

    await act(async () => {
      WebSocketMock.instances[0].onopen?.();
    });

    expect(result.current.status).toBe("connected");

    await act(async () => {
      WebSocketMock.instances[0].onmessage?.({
        data: JSON.stringify({ id: "2", title: "Live", body: "data", timestamp: Date.now() }),
      } as MessageEvent<string>);
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]).toMatchObject({ title: "Live" });
  });

  it("cambia a fallback ante errores e ignora mensajes inválidos", async () => {
    currentFallbackData = { logs: [] };

    const { result } = renderHook(() => useLiveNotifications("token"));

    await act(async () => {
      WebSocketMock.instances[0].onmessage?.({ data: "no-json" } as MessageEvent<string>);
    });

    expect(consoleErrorSpy).toHaveBeenCalledWith("Invalid WS message:", expect.any(SyntaxError));

    await act(async () => {
      WebSocketMock.instances[0].onerror?.();
    });

    expect(result.current.status).toBe("fallback");

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.events).toEqual([]);
  });
});
