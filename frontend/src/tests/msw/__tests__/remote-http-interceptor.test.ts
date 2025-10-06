// QA: validamos el proxy que reexporta el interceptor remoto para sumar cobertura.
jest.mock("../interceptors/resolve", () => ({
  loadInterceptor: jest.fn(() => ({ intercept: jest.fn() })),
}));

const { loadInterceptor } = require("../interceptors/resolve");

describe("RemoteHttpInterceptor module", () => {
  it("carga el interceptor remoto por defecto", () => {
    const module = require("../interceptors/RemoteHttpInterceptor");

    expect(loadInterceptor).toHaveBeenCalledWith("RemoteHttpInterceptor");
    expect(module.default).toEqual({ intercept: expect.any(Function) });
  });
});
