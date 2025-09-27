import type { Config } from "jest";

const config: Config = {
  // ✅ Usa ts-jest para compilar TS/TSX en tests
  preset: "ts-jest",

  testEnvironment: "jsdom",

  // Útil para algunas APIs que esperan un origin válido
  testEnvironmentOptions: {
    url: "http://localhost",
  },

  setupFilesAfterEnv: [
    "<rootDir>/jest.setup.ts",
    "<rootDir>/src/tests/msw/setup.ts"
  ],

  moduleNameMapper: {
    "^.+\\.(css|less|scss|sass)$": "identity-obj-proxy",
    "^@/styles/globals\\.css$": "identity-obj-proxy",
    "^@/(.*)$": "<rootDir>/src/$1",
    "^msw/node$": "<rootDir>/node_modules/msw/lib/node/index.js",
    "^@mswjs/interceptors/WebSocket$": "<rootDir>/src/tests/msw/websocket-interceptor.ts",
    "^@mswjs/interceptors/(.*)$": "<rootDir>/node_modules/@mswjs/interceptors/lib/node/interceptors/$1/index.js",
    // Si luego agregas mocks de assets, puedes mapear imágenes/SVG a un mock:
    // "\\.(jpg|jpeg|png|gif|webp|avif|svg)$": "<rootDir>/__mocks__/fileMock.js",
  },

  transform: {
    "^.+\\.(t|j)sx?$": [
      "ts-jest",
      {
        tsconfig: "<rootDir>/tsconfig.jest.json",
      },
    ],
  },

  // ⚠️ Transpila ciertos módulos ESM dentro de node_modules (como recharts y d3-*)
  transformIgnorePatterns: [
    "/node_modules/(?!(recharts|d3-array|d3-scale|d3-time|d3-format|d3-color|delaunator|robust-predicates|internmap|msw|@mswjs|until-async|strict-event-emitter|outvariant|headers-polyfill)/)",
  ],

  // Para que Jest resuelva correctamente extensiones más comunes del proyecto
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json", "node"],

  // Dónde buscar tests (puedes ajustarlo si prefieres __tests__)
  testMatch: [
    "<rootDir>/src/**/*.test.(ts|tsx|js|jsx)",
    "<rootDir>/src/**/__tests__/**/*.(ts|tsx|js|jsx)",
  ],

  testPathIgnorePatterns: ["<rootDir>/.next/", "<rootDir>/node_modules/"],

  // Calidad de vida
  clearMocks: true,
  // verbose: true,
  collectCoverage: true,
  collectCoverageFrom: [
    "<rootDir>/src/**/*.{ts,tsx}",
    "<rootDir>/src/components/forms/**/*.{ts,tsx}",
    "<rootDir>/src/components/sidebar/**/*.{ts,tsx}",
    "<rootDir>/src/components/news/**/*.{ts,tsx}",
    "!<rootDir>/src/**/__tests__/**",
    "!<rootDir>/src/**/stories/**",
    "!<rootDir>/src/app/**",
    "!<rootDir>/src/components/alerts/**",
    "!<rootDir>/src/components/chat/**",
    "!<rootDir>/src/components/dashboard/**",
    "!<rootDir>/src/components/indicators/**",
    "!<rootDir>/src/components/providers/**",
    "!<rootDir>/src/components/ui/**",
    "!<rootDir>/src/context/**",
    "!<rootDir>/src/lib/**"
  ],
  coverageThreshold: {
    global: {
      branches: 85,
      functions: 90,
      lines: 90,
      statements: 90,
    },
  },

};

export default config;
