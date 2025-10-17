import { trackEvent } from "../analytics";

// QA: evitamos ruido en consola y verificamos escenarios seguros de trackEvent.
describe("analytics helpers", () => {
  const originalAnalytics = (window as any).analytics;
  let infoSpy: jest.SpyInstance;
  let errorSpy: jest.SpyInstance;

  beforeEach(() => {
    (window as any).analytics = undefined;
    infoSpy = jest.spyOn(console, "info").mockImplementation(() => {});
    errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    (window as any).analytics = originalAnalytics;
    infoSpy.mockRestore();
    errorSpy.mockRestore();
  });

  it("no lanza errores cuando no hay cliente y registra en consola", () => {
    expect(() => trackEvent("test-event", { foo: "bar" })).not.toThrow();
    expect(infoSpy).toHaveBeenCalledWith("analytics event", "test-event", { foo: "bar" });
  });

  it("utiliza el cliente de analytics cuando está disponible", () => {
    const track = jest.fn();
    (window as any).analytics = { track };

    expect(() => trackEvent("tracked", { value: 1 })).not.toThrow();
    expect(track).toHaveBeenCalledWith("tracked", { value: 1 });
  });

  it("captura excepciones del cliente y avisa sin romper el flujo", () => {
    const error = new Error("fail");
    (window as any).analytics = {
      track: () => {
        throw error;
      },
    };

    expect(() => trackEvent("failing")).not.toThrow();
    expect(errorSpy).toHaveBeenCalledWith("analytics track failed", error);
  });
});
