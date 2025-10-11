import { server } from './server';

// Configuración global del mock server para Jest
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
