import { server } from "./server"; // ✅ Normalizamos import para mantener consistencia MSW + Prettier

// Configuración global del mock server para Jest
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
