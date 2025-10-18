import { setupServer } from "msw/node";
import { handlers, httpHandlers } from "./handlers";
import { wsHandlers } from "./handlers.ws";

const restHandlers =
  handlers === httpHandlers ? httpHandlers : [...handlers, ...httpHandlers];

export const server = setupServer(...restHandlers, ...(wsHandlers as any[]));
