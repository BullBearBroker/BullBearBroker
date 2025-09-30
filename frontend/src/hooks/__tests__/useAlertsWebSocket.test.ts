import { act, renderHook } from "@testing-library/react";

import { useAlertsWebSocket } from "../useAlertsWebSocket";
import * as api from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url: string;
  onopen: (() => void) | null = null;
  onclose: ((event?: any) => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: ((event?: any) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(): void {
    // noop
  }

  close(): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({});
  }

  triggerOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  triggerMessage(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  triggerError(): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onerror?.(new Event("error"));
  }

  triggerClose(): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({});
  }

  static reset(): void {
    MockWebSocket.instances = [];
  }
}

declare global {
  // eslint-disable-next-line no-var
  var WebSocket: typeof MockWebSocket;
}

describe("useAlertsWebSocket", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000";
    (global as any).WebSocket = MockWebSocket as unknown as typeof WebSocket;
    jest.useFakeTimers();
    MockWebSocket.reset();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    MockWebSocket.reset();
    process.env.NEXT_PUBLIC_API_BASE_URL = API_BASE_URL;
  });

  it("establece la conexión y procesa mensajes de alerta", () => {
    const onAlert = jest.fn();
    const onSystemMessage = jest.fn();

    const { result } = renderHook(() =>
      useAlertsWebSocket({ token: "token-123", onAlert, onSystemMessage })
    );

    expect(MockWebSocket.instances).toHaveLength(1);
    const socket = MockWebSocket.instances[0];
    expect(socket.url).toBe("ws://localhost:8000/ws/alerts?token=token-123");

    act(() => {
      socket.triggerOpen();
    });

    expect(result.current.status).toBe("open");

    act(() => {
      socket.triggerMessage({ type: "alert", message: "BTC cruzó el objetivo" });
      socket.triggerMessage({ type: "system", message: "Bienvenido" });
      // mensaje inválido para cubrir rama de error
      socket.onmessage?.({ data: "not-json" } as any);
    });

    expect(onAlert).toHaveBeenCalledWith(
      expect.objectContaining({ type: "alert", message: "BTC cruzó el objetivo" })
    );
    expect(onSystemMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: "system", message: "Bienvenido" })
    );
    expect(result.current.lastMessage).toMatchObject({ type: "system" });
    expect(result.current.error).toBe("Mensaje de WebSocket no válido");
  });

  it("reintenta la conexión ante un cierre inesperado", () => {
    const { result } = renderHook(() =>
      useAlertsWebSocket({ token: "token-123", enabled: true })
    );

    const socket = MockWebSocket.instances[0];

    act(() => {
      socket.triggerOpen();
    });

    expect(result.current.status).toBe("open");

    act(() => {
      socket.triggerClose();
    });

    expect(result.current.status).toBe("closed");
    expect(MockWebSocket.instances).toHaveLength(1);

    act(() => {
      jest.advanceTimersByTime(1000);
    });

    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it("permite cerrar manualmente la conexión", () => {
    const { result } = renderHook(() =>
      useAlertsWebSocket({ token: "token-123", enabled: true })
    );

    const socket = MockWebSocket.instances[0];

    act(() => {
      socket.triggerOpen();
    });

    act(() => {
      result.current.disconnect();
    });

    expect(result.current.status).toBe("closed");

    act(() => {
      jest.advanceTimersByTime(2000);
    });

    // No se crea un nuevo WebSocket tras desconexión manual
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it("no intenta conectar cuando está deshabilitado", () => {
    const { result, rerender } = renderHook(
      ({ enabled }) => useAlertsWebSocket({ token: "token-123", enabled }),
      { initialProps: { enabled: false } }
    );

    expect(MockWebSocket.instances).toHaveLength(0);
    expect(result.current.status).toBe("closed");

    rerender({ enabled: true });

    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it("puede reconectar manualmente después de un cierre", () => {
    const { result } = renderHook(() =>
      useAlertsWebSocket({ token: "token-123", enabled: true })
    );

    const socket = MockWebSocket.instances[0];

    act(() => {
      socket.triggerOpen();
    });

    act(() => {
      socket.triggerClose();
    });

    act(() => {
      result.current.reconnect();
    });

    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it("no crea conexiones adicionales cuando ya existe una activa", () => {
    const { result } = renderHook(() =>
      useAlertsWebSocket({ token: "token-123", enabled: true })
    );

    expect(MockWebSocket.instances).toHaveLength(1);

    act(() => {
      result.current.reconnect();
    });

    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it("propaga estado de error cuando el socket reporta fallo", () => {
    const { result } = renderHook(() =>
      useAlertsWebSocket({ token: "token-123", enabled: true })
    );

    const socket = MockWebSocket.instances[0];

    act(() => {
      socket.triggerError();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toBe("Ocurrió un error con la conexión en vivo");
  });

  it("maneja fallos al construir la URL del WebSocket", () => {
    const spy = jest
      .spyOn(api, "getAlertsWebSocketUrl")
      .mockImplementation(() => {
        throw new Error("boom");
      });

    const { result } = renderHook(() =>
      useAlertsWebSocket({ token: "token-123", enabled: true })
    );

    expect(MockWebSocket.instances).toHaveLength(0);
    expect(result.current.status).toBe("idle");

    spy.mockRestore();
  });

});
