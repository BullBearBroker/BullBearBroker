import "@testing-library/jest-dom";
import "jest-axe/extend-expect";

// Polyfills requeridos por MSW en entorno de pruebas
process.env.NEXT_PUBLIC_API_URL ||= "http://localhost:8000";

if (typeof (global as any).ResizeObserver === "undefined") {
  (global as any).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

try {
  jest.mock("recharts", () => {
    const original = jest.requireActual("recharts");
    const React = jest.requireActual("react");
    const MockResponsiveContainer = ({ width, height, children }: any) =>
      React.createElement(
        "div",
        { style: { width: width || 800, height: height || 400 } },
        children
      );

    return {
      ...original,
      ResponsiveContainer: MockResponsiveContainer,
    };
  });
} catch (error) {
  // Si ya estaba mockeado en otro lugar, omitimos la redefinición
}

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

if (typeof window !== "undefined" && !window.matchMedia) {
  // @ts-expect-error - polyfill para entorno de pruebas
  window.matchMedia = jest.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  }));
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

jest.mock("next-themes", () => {
  const React = require("react");
  return {
    __esModule: true,
    ThemeProvider: ({ children }: any) => React.createElement(React.Fragment, null, children),
    useTheme: () => ({
      theme: "light",
      resolvedTheme: "light",
      setTheme: jest.fn(),
    }),
  };
});
// [Codex] nuevo - Mock de Radix ScrollArea para entorno de pruebas
jest.mock("@radix-ui/react-scroll-area", () => {
  const React = require("react");

  const Root = ({ children, ...props }: any) =>
    React.createElement("div", { ...props }, children);
  Root.displayName = "ScrollAreaRoot";

  const Viewport = ({ children, ...props }: any) =>
    React.createElement("div", { ...props }, children);
  Viewport.displayName = "ScrollAreaViewport";

  const ScrollArea = ({ children, ...props }: any) =>
    React.createElement("div", { ...props }, children);
  ScrollArea.displayName = "ScrollArea";

  const ScrollAreaViewport = Viewport;

  const ScrollAreaScrollbar = ({ children, ...props }: any) =>
    React.createElement("div", { ...props }, children);
  ScrollAreaScrollbar.displayName = "ScrollAreaScrollbar";

  const Scrollbar = ScrollAreaScrollbar;

  const ScrollAreaThumb = (props: any) =>
    React.createElement("div", { ...props });
  ScrollAreaThumb.displayName = "ScrollAreaThumb";

  const Thumb = ScrollAreaThumb;

  const Corner = (props: any) => React.createElement("div", { ...props });
  Corner.displayName = "ScrollAreaCorner";

  const ScrollAreaCorner = Corner;

  return {
    __esModule: true,
    Root,
    Viewport,
    ScrollArea,
    ScrollAreaViewport,
    ScrollAreaScrollbar,
    Scrollbar,
    ScrollAreaThumb,
    Thumb,
    Corner,
    ScrollAreaCorner,
  };
});
