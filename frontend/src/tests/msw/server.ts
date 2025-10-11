// ✅ Patched version compatible with MSW 2.x + PNPM + Node 20
import { setupServer } from 'msw/node';
import { SetupServerApi } from 'msw';
import { handlers } from './handlers';

// MSW usa interceptores internos que pueden no resolverse con PNPM;
// esta importación asegura compatibilidad directa.
import '@mswjs/interceptors';

export const server: SetupServerApi = setupServer(...handlers);

// Lifecycle hooks para Jest
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

export { rest } from 'msw';

// ✅ Validado para Jest + PNPM + Node 20 (BullBearBroker test env)
