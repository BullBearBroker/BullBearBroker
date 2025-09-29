import "@testing-library/jest-dom";
import "jest-axe/extend-expect";

// Polyfills requeridos por MSW en entorno de pruebas
import { TextDecoder, TextEncoder } from "util";
import { ReadableStream, WritableStream, TransformStream } from "stream/web";

if (!globalThis.TextEncoder) {
  // @ts-ignore - asignación deliberada al objeto global
  globalThis.TextEncoder = TextEncoder;
}

if (!globalThis.TextDecoder) {
  // @ts-ignore - asignación deliberada al objeto global
  globalThis.TextDecoder = TextDecoder;
}

if (!globalThis.TransformStream) {
  // @ts-ignore - asignación deliberada al objeto global
  globalThis.TransformStream = TransformStream;
}

if (!globalThis.ReadableStream) {
  // @ts-ignore - asignación deliberada al objeto global
  globalThis.ReadableStream = ReadableStream;
}

if (!globalThis.WritableStream) {
  // @ts-ignore - asignación deliberada al objeto global
  globalThis.WritableStream = WritableStream;
}

if (!globalThis.BroadcastChannel) {
  class MockBroadcastChannel {
    constructor(_name: string) {}
    close() {}
    postMessage(_value: unknown) {}
    addEventListener() {}
    removeEventListener() {}
    onmessage: ((event: MessageEvent) => void) | null = null;
  }

  // @ts-ignore - asignación deliberada al objeto global
  globalThis.BroadcastChannel = MockBroadcastChannel;
}

if (typeof window !== "undefined" && window.HTMLElement) {
  const descriptor = Object.getOwnPropertyDescriptor(
    window.HTMLElement.prototype,
    "scrollIntoView"
  );

  if (!descriptor || descriptor.value === undefined) {
    Object.defineProperty(window.HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      writable: true,
      value: jest.fn(),
    });
  }
}

// Mock global de next/link para tests
jest.mock("next/link", () => {
  const React = require("react");
  return {
    __esModule: true,
    default: ({ children, href, ...props }: any) =>
      React.createElement(
        "a",
        { href: href ?? props?.href ?? "#", ...props },
        children
      ),
  };
});
