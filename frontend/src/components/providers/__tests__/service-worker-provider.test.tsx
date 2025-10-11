import { render, waitFor } from "@testing-library/react";
import React from "react";
import { ServiceWorkerProvider } from "../service-worker-provider";

describe("ServiceWorkerProvider", () => {
  const originalServiceWorker = navigator.serviceWorker;
  const originalConsoleError = console.error;

  beforeEach(() => {
    jest.resetAllMocks();

    const serviceWorkerMock = {
      register: jest.fn(),
      getRegistration: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      controller: {},
      ready: Promise.resolve(),
    };

    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: serviceWorkerMock,
    });

    console.error = jest.fn();
  });

  afterEach(() => {
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: originalServiceWorker,
    });
    console.error = originalConsoleError;
  });

  it("registra el service worker cuando no existe uno previo", async () => {
    const registrationMock = { waiting: { postMessage: jest.fn() } };
    const serviceWorker = navigator.serviceWorker as unknown as {
      register: jest.Mock;
      getRegistration: jest.Mock;
    };

    serviceWorker.getRegistration.mockResolvedValue(undefined);
    serviceWorker.register.mockResolvedValue(registrationMock);

    render(<ServiceWorkerProvider />);

    await waitFor(() => {
      expect(serviceWorker.getRegistration).toHaveBeenCalledWith("/sw.js");
      expect(serviceWorker.register).toHaveBeenCalledWith("/sw.js");
    });

    await waitFor(() => {
      expect(registrationMock.waiting?.postMessage).toHaveBeenCalledWith({ type: "SKIP_WAITING" });
    });
  });

  it("maneja errores al registrar el service worker sin romper el render", async () => {
    const serviceWorker = navigator.serviceWorker as unknown as {
      register: jest.Mock;
      getRegistration: jest.Mock;
    };

    serviceWorker.getRegistration.mockResolvedValue(undefined);
    serviceWorker.register.mockRejectedValue(new Error("fail"));

    render(<ServiceWorkerProvider />);

    await waitFor(() => {
      expect(serviceWorker.register).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(console.error).toHaveBeenCalledWith(
        "Service worker registration failed",
        expect.any(Error),
      );
    });
  });

  it("escucha cambios del controlador y relanza el registro", async () => {
    const serviceWorker = navigator.serviceWorker as unknown as {
      register: jest.Mock;
      getRegistration: jest.Mock;
      addEventListener: jest.Mock;
      removeEventListener: jest.Mock;
    };

    serviceWorker.getRegistration.mockResolvedValue(undefined);
    serviceWorker.register.mockResolvedValue({});

    render(<ServiceWorkerProvider />);

    await waitFor(() => {
      expect(serviceWorker.register).toHaveBeenCalledTimes(1);
    });

    const controllerChangeHandler = serviceWorker.addEventListener.mock.calls.find(
      ([eventName]) => eventName === "controllerchange",
    )?.[1] as (() => void) | undefined;

    expect(serviceWorker.addEventListener).toHaveBeenCalledWith(
      "controllerchange",
      expect.any(Function),
    );
    expect(controllerChangeHandler).toBeInstanceOf(Function);

    controllerChangeHandler?.();

    await waitFor(() => {
      expect(serviceWorker.register).toHaveBeenCalledTimes(2);
    });

    expect(serviceWorker.removeEventListener).not.toHaveBeenCalled();
  });
});
