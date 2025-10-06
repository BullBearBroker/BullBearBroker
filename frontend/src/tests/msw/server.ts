import { setupServer } from "msw/node";

import { handlers } from "./handlers";

// # QA fix: permitir requests no interceptadas sin abortar tests
export const server = setupServer(...handlers);

server.listen({
  onUnhandledRequest: "warn", // evita errores en pruebas no mockeadas
});
