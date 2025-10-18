import { setupServer } from "msw/node";
import { handlers } from "./handlers";
import { wsHandlers } from "./handlers.ws";

export const server = setupServer(...handlers, ...wsHandlers);

server.listen({
  onUnhandledRequest(req, print) {
    try {
      const url = new URL(req.url);
      if (url.protocol.startsWith("ws")) {
        return;
      }
    } catch {
      // If the URL cannot be parsed, fall back to the default warning
    }
    print.warning();
  },
});

process.once("beforeExit", () => {
  server.close();
});
