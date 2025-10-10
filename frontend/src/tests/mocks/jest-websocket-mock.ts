// ✅ Codex fix: mock simplificado de jest-websocket-mock para entorno de pruebas

type WebSocketEventHandler<T> = ((event: T) => void) | null;

class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  static __isMock = true;

  url: string;
  readyState = MockWebSocket.CONNECTING;
  onopen: WebSocketEventHandler<Event> = null;
  onclose: WebSocketEventHandler<CloseEvent> = null;
  onmessage: WebSocketEventHandler<MessageEvent<string>> = null;
  onerror: WebSocketEventHandler<Event> = null;

  private server: Server | null = null;

  constructor(url: string) {
    this.url = url;
    const found = Server.lookup(url);
    if (!found) {
      throw new Error(`No mock server listening on ${url}`);
    }
    this.server = found;
    found.attach(this);
  }

  send(data: string) {
    this.server?.receive(this, data);
  }

  close() {
    if (this.readyState === MockWebSocket.CLOSED) {
      return;
    }
    this.readyState = MockWebSocket.CLOSING;
    this.server?.detach(this);
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(
      new CloseEvent("close", {
        wasClean: true,
        code: 1000,
        reason: "client_close",
      }),
    );
  }

  _open() {
    if (this.readyState === MockWebSocket.OPEN) return;
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  _emitMessage(payload: string) {
    if (this.readyState !== MockWebSocket.OPEN) return;
    this.onmessage?.(
      new MessageEvent("message", {
        data: payload,
      }),
    );
  }

  _emitError() {
    this.readyState = MockWebSocket.CLOSED;
    this.onerror?.(new Event("error"));
  }

  _emitClose(reason = "server_close") {
    if (this.readyState === MockWebSocket.CLOSED) return;
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(
      new CloseEvent("close", {
        wasClean: true,
        code: 1000,
        reason,
      }),
    );
  }
}

class Server {
  private static registry = new Map<string, Server>();

  readonly url: string;
  private clients = new Set<MockWebSocket>();
  private resolveConnected?: () => void;
  readonly connected: Promise<void>;

  constructor(url: string) {
    this.url = url;
    Server.registry.set(url, this);
    this.connected = new Promise((resolve) => {
      this.resolveConnected = resolve;
    });
    const scope = typeof window !== "undefined" ? window : globalThis;
    // @ts-expect-error asignación deliberada para test
    scope.WebSocket = MockWebSocket;
  }

  static lookup(url: string) {
    return Server.registry.get(url) ?? null;
  }

  static clean() {
    for (const server of Server.registry.values()) {
      server.close();
    }
    Server.registry.clear();
  }

  attach(client: MockWebSocket) {
    this.clients.add(client);
    queueMicrotask(() => {
      client._open();
      this.resolveConnected?.();
      this.resolveConnected = undefined;
    });
  }

  detach(client: MockWebSocket) {
    this.clients.delete(client);
  }

  receive(_client: MockWebSocket, _data: string) {
    // Intencionalmente vacío: los tests pueden inspeccionar si fuese necesario
  }

  send(data: string | Record<string, unknown>) {
    const payload = typeof data === "string" ? data : JSON.stringify(data);
    for (const client of this.clients) {
      client._emitMessage(payload);
    }
  }

  error() {
    for (const client of this.clients) {
      client._emitError();
    }
    this.clients.clear();
    Server.registry.delete(this.url);
  }

  close() {
    for (const client of this.clients) {
      client._emitClose();
    }
    this.clients.clear();
    Server.registry.delete(this.url);
  }
}

export { Server };
export default Server;
