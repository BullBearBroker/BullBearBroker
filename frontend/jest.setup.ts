// ✅ Polyfill temporal para resolver el error de MSW en Node 20 + PNPM 10 + Jest 29+
// Jest pierde la resolución interna del módulo "@mswjs/interceptors/ClientRequest".
// Este bloque intercepta la carga y fuerza su ruta absoluta real.

import Module from "module";
import path from "path";

const resolveFromHere = Module.createRequire(__filename); // ✅ Node 20 expone createRequire de forma estable, sin fallback CJS

try {
  const {
    fetch: undiciFetch,
    Response: UndiciResponse,
    Request: UndiciRequest,
    Headers: UndiciHeaders,
  } = resolveFromHere("node:undici");

  globalThis.fetch ??= undiciFetch;
  globalThis.Response ??= UndiciResponse;
  globalThis.Request ??= UndiciRequest;
  globalThis.Headers ??= UndiciHeaders;
} catch (_error) {
  // 🔧 Si undici no está disponible, conservamos los globals existentes
}

if (typeof Response === "undefined") {
  try {
    resolveFromHere("whatwg-fetch");
  } catch (_error) {
    // 🔧 Último recurso: definimos un Response vacío para evitar fallos de inicialización
    class MinimalResponse {}
    // @ts-expect-error - asignación deliberada
    globalThis.Response = MinimalResponse;
  }
}

const clientRequestPath = (() => {
  try {
    return resolveFromHere.resolve(
      "@mswjs/interceptors/lib/node/interceptors/ClientRequest/index.js",
    );
  } catch (_error) {
    // ✅ Fixed MSW resolver (Node 20 + PNPM) apuntando a la versión 0.29.0 distribuida por PNPM
    return path.resolve(
      __dirname,
      "..",
      "node_modules/.pnpm/@mswjs+interceptors@0.29.0/node_modules/@mswjs/interceptors/lib/node/interceptors/ClientRequest/index.js",
    );
  }
})();

type ResolveFilenameFn = (
  request: string,
  parent: NodeModule | undefined,
  isMain: boolean,
  options?: Record<string, unknown>,
) => string;

const moduleWithResolve = Module as unknown as { _resolveFilename: ResolveFilenameFn }; // ✅ Tipado explícito para acceder a la API privada de Node
const originalResolveFilename = moduleWithResolve._resolveFilename;
moduleWithResolve._resolveFilename = function (
  request: string,
  parent: NodeModule | undefined,
  isMain: boolean,
  options?: Record<string, unknown>,
) {
  if (request === "@mswjs/interceptors/ClientRequest") {
    return clientRequestPath;
  }
  return originalResolveFilename.call(this, request, parent, isMain, options);
};

// ✅ Mock virtual para exponer el ClientRequest real dentro de Jest (Node 20 + PNPM 10)
jest.mock("@mswjs/interceptors/ClientRequest", () => resolveFromHere(clientRequestPath), {
  virtual: true,
});

// 🔧 Fin del polyfill MSW para Node 20 + PNPM 10 + Jest 29+

import "@testing-library/jest-dom";
import "jest-axe/extend-expect";
jest.mock("next/font/google", () => ({
  Inter: () => ({
    className: "font-inter",
    variable: "--font-inter",
    style: {},
  }),
}));

// Configura una URL de API por defecto para los tests del frontend
process.env.NEXT_PUBLIC_API_URL ??= "http://localhost:8000";

const originalError = console.error;
const originalWarn = console.warn;

const ignoredWarnings = [
  /Warning:.*(linearGradient|stop|defs)/,
  /Push notifications not supported/i,
  /Invalid fallback payload/i,
  /unrecognized in this browser/i,
];

const ignoredErrorMessages = [
  /Mensaje WS no parseable/, // errores controlados por mocks de WS
  /No se pudo construir la URL del WebSocket/,
];

function shouldIgnore(message: unknown) {
  if (typeof message !== "string") {
    return false;
  }
  return ignoredWarnings.some((pattern) => pattern.test(message));
}

function shouldIgnoreError(message: unknown) {
  if (shouldIgnore(message)) {
    return true;
  }
  if (typeof message !== "string") {
    return false;
  }
  return ignoredErrorMessages.some((pattern) => pattern.test(message));
}

beforeAll(() => {
  console.error = (...args: any[]) => {
    const [message] = args;

    if (shouldIgnoreError(message)) {
      return;
    }

    originalError.call(console, ...args);
  };

  console.warn = (...args: any[]) => {
    const [message] = args;

    if (shouldIgnore(message)) {
      return;
    }

    originalWarn.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
  console.warn = originalWarn;
});

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
    const MockResponsiveContainer = ({ width, height, children, ...rest }: any) => {
      const resolvedWidth = typeof width === "number" ? width : 800;
      const resolvedHeight = typeof height === "number" ? height : 400;
      const content =
        typeof children === "function"
          ? children({ width: resolvedWidth, height: resolvedHeight })
          : React.cloneElement(children, { width: resolvedWidth, height: resolvedHeight });

      return React.createElement(
        "div",
        { style: { width: resolvedWidth, height: resolvedHeight }, ...rest },
        React.createElement("svg", { width: resolvedWidth, height: resolvedHeight }, content),
      );
    };

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
  // @ts-expect-error - asignación deliberada al objeto global
  globalThis.TextEncoder = TextEncoder;
}

if (!globalThis.TextDecoder) {
  // @ts-expect-error - asignación deliberada al objeto global
  globalThis.TextDecoder = TextDecoder;
}

if (!globalThis.TransformStream) {
  // @ts-expect-error - asignación deliberada al objeto global
  globalThis.TransformStream = TransformStream;
}

if (!globalThis.ReadableStream) {
  // @ts-expect-error - asignación deliberada al objeto global
  globalThis.ReadableStream = ReadableStream;
}

if (!globalThis.WritableStream) {
  // @ts-expect-error - asignación deliberada al objeto global
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

  // @ts-expect-error - asignación deliberada al objeto global
  globalThis.BroadcastChannel = MockBroadcastChannel;
}

if (typeof window !== "undefined" && window.HTMLElement) {
  const descriptor = Object.getOwnPropertyDescriptor(
    window.HTMLElement.prototype,
    "scrollIntoView",
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
      React.createElement("a", { href: href ?? props?.href ?? "#", ...props }, children),
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

  const Root = ({ children, ...props }: any) => React.createElement("div", { ...props }, children);
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

  const ScrollAreaThumb = (props: any) => React.createElement("div", { ...props });
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

// Mock global para URL APIs usadas en PortfolioPanel
global.URL.createObjectURL = jest.fn(() => "blob:mock-url");
global.URL.revokeObjectURL = jest.fn();
