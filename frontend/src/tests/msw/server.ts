import { setupServer } from "msw/node";

import { handlers } from "./handlers";

export const server = setupServer(...handlers);

// # QA fix: permitir requests no interceptadas durante pruebas
server.listen({ onUnhandledRequest: "warn" });
