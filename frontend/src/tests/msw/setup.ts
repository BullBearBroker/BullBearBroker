import "whatwg-fetch";

import { server } from "./server";

beforeAll(() => {
  // # QA fix: evitar que requests no mockeadas rompan las suites
  server.listen({ onUnhandledRequest: "warn" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});
