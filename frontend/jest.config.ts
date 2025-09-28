import type { Config } from "jest";

const config: Config = {
  // ✅ Simula entorno navegador
  testEnvironment: "jsdom",

  testEnvironmentOptions: {
    url: "http://localhost",
  },

  // ✅ Archivos que se cargan antes de cada test
  setupFilesAfterEnv: [
    "<rootDir>/jest.setup.ts",
    "<rootDir>/src/tests/msw/setup.ts",
  ],

  // ✅ Mapear imports no soportados
  moduleNameMapper: {
    "^.+\\.(css|less|scss|sass)$": "identity-obj-proxy",
    "^@/styles/globals\\.css$": "identity-obj-proxy",
    "^@/(.*)$": "<rootDir>/src/$1",
    "^msw/node$": "<rootDir>/node_modules/msw/lib/node/index.js",
    "^@mswjs/interceptors/WebSocket$":
      "<rootDir>/src/tests/msw/websocket-interceptor.ts",
    "^@mswjs/interceptors/(.*)$":
      "<rootDir>/node_modules/@mswjs/interceptors/lib/node/interceptors/$1/index.js",
  },

  // ✅ Transforma TS/JS con Babel (usando tu babel.config.js en ESM)
  transform: {
    "^.+\\.(t|j)sx?$": [
      "babel-jest",
      {
        configFile: "<rootDir>/babel.config.cjs",
      },
    ],
  },

  // ⚠️ Incluye librerías ESM que Jest no procesa por defecto
  transformIgnorePatterns: [
    "/node_modules/(?!(recharts|d3-|msw|@mswjs|until-async|strict-event-emitter|outvariant|headers-polyfill)/)",
  ],

  // ✅ Extensiones soportadas
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json", "node"],

  // ✅ Localización de tests
  testMatch: [
    "<rootDir>/src/**/*.test.(ts|tsx|js|jsx)",
    "<rootDir>/src/**/__tests__/**/*.(ts|tsx|js|jsx)",
  ],

  testPathIgnorePatterns: ["<rootDir>/.next/", "<rootDir>/node_modules/"],

  clearMocks: true,

  // ✅ Cobertura
  collectCoverage: true,
  collectCoverageFrom: [
    "<rootDir>/src/**/*.{ts,tsx}",
    "<rootDir>/src/components/forms/**/*.{ts,tsx}",
    "<rootDir>/src/components/sidebar/**/*.{ts,tsx}",
    "<rootDir>/src/components/news/**/*.{ts,tsx}",
    "!<rootDir>/src/**/__tests__/**",
    "!<rootDir>/src/**/stories/**",
    "!<rootDir>/src/app/**",
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
