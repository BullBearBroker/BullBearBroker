import { server } from "./server";

afterEach(() => server.resetHandlers());
afterAll(() => server.close());
