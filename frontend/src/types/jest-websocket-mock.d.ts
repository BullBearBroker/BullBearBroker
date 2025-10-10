declare module "jest-websocket-mock" {
  class MockWebSocketServer {
    constructor(url: string, options?: unknown);
    readonly connected: Promise<void>;
    send(data: unknown): void;
    close(): void;
    static clean(): void;
  }

  export { MockWebSocketServer as Server };
  export default MockWebSocketServer;
}
