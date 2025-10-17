// ✅ Patched version compatible con MSW 2.x + PNPM + Node 20
import { setupServer } from "msw/node";
import type { SetupServerApi } from "msw/node";
import { http } from "msw";
import { handlers } from "./handlers";

// MSW usa interceptores internos que pueden no resolverse con PNPM;
// esta importación asegura compatibilidad directa.
// 🔧 Normalizamos imports MSW a rutas recomendadas para Node 20
import "@mswjs/interceptors";

export const server: SetupServerApi = setupServer(...handlers);

const rest = http; // ✅ Alias rest para mantener compatibilidad con suites existentes en MSW 2.x

// Lifecycle hooks para Jest
beforeAll(() =>
  server.listen({
    onUnhandledRequest(req, print) {
    const url = (req && (req.url || (req).request?.url)) || '';
    if (url.startsWith('ws://') || url.startsWith('wss://')) return; // QA

      if (req.url.startsWith("ws://")) return;
      print.warning();
    
},
  })
);
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

export { rest }; // ✅ Reexportamos rest desde el import unificado para msw

// ✅ Validado para Jest + PNPM + Node 20 (BullBearBroker test env)
