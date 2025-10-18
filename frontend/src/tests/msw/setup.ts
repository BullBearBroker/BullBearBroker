import { server } from "./server";

beforeAll(() =>
  server.listen({
    onUnhandledRequest(req, print) {
      try {
        const url = new URL(req.url);
        if (url.pathname === "/api/realtime/ws" || url.pathname === "/ws/notifications") {
          return;
        }
      } catch {
        // noop
      }
      print.warning();
    },
  })
);
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
