const path = require("path");

/** @type {import('jest').Config} */
const baseConfig = {
  preset: "ts-jest/presets/js-with-ts",
  rootDir: path.resolve(__dirname),
  testEnvironment: "jsdom",
  testEnvironmentOptions: {
    url: "http://localhost",
  },
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts", "<rootDir>/src/tests/msw/setup.ts"],
  moduleNameMapper: {
    // # QA fix: corregir regex y rutas raíz de los alias "@/..."
    "^@/components/(.*)$": "<rootDir>/src/components/$1",
    "^@/hooks/(.*)$": "<rootDir>/src/hooks/$1",
    "^@/lib/(.*)$": "<rootDir>/src/lib/$1",
    "^@/utils/(.*)$": "<rootDir>/src/utils/$1", // ✅ Alias añadido para resolver "@/utils/fonts" en Jest
    "^@/context/(.*)$": "<rootDir>/src/context/$1",
    "^@/tests/(.*)$": "<rootDir>/src/tests/$1",
    "^recharts$": "<rootDir>/__mocks__/recharts.tsx",
    "^msw/node$": "<rootDir>/node_modules/msw/lib/node/index.js",
    "^jest-websocket-mock$": "<rootDir>/src/tests/mocks/jest-websocket-mock.ts", // ✅ Codex fix: mock consistente para WebSocket
    "^@/styles/globals\.css$": "identity-obj-proxy",
    "\.(css|less|scss|sass)$": "identity-obj-proxy",
  },
  transform: {
    "^.+\\.(ts|tsx)$": [
      "ts-jest",
      {
        tsconfig: path.resolve(__dirname, "tsconfig.jest.json"),
        diagnostics: false,
      },
    ],
    "^.+\\.(js|jsx)$": [
      "babel-jest",
      { configFile: path.resolve(__dirname, "babel.config.js"), babelrc: false },
    ],
  },
  transformIgnorePatterns: [
    "/node_modules/(?!(\\.pnpm/[^/]+/node_modules/)?(recharts|d3-|msw|@mswjs|until-async|strict-event-emitter|outvariant|headers-polyfill)/)",
    "node_modules/(?!(\\.pnpm/[^/]+/node_modules/)?(recharts|d3-|msw|@mswjs|until-async|strict-event-emitter|outvariant|headers-polyfill|nanoid|uuid|other-esm-lib)/)",
  ],
  coveragePathIgnorePatterns: [
    "<rootDir>/src/tests/", // ✅ Ignoramos infraestructura de pruebas para el cálculo de cobertura global
    "<rootDir>/src/types/", // ✅ Tipos estáticos quedan fuera del objetivo de cobertura
  ],
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json", "node"],
  testMatch: [
    "<rootDir>/app/**/*.test.(ts|tsx|js|jsx)",
    "<rootDir>/app/**/__tests__/**/*.(ts|tsx|js|jsx)",
    "<rootDir>/src/**/*.test.(ts|tsx|js|jsx)",
    "<rootDir>/src/**/__tests__/**/*.(ts|tsx|js|jsx)",
  ],
  testPathIgnorePatterns: ["<rootDir>/.next/", "<rootDir>/node_modules/"],
  clearMocks: true,
  collectCoverage: false,
  collectCoverageFrom: [
    "<rootDir>/src/**/*.{ts,tsx}", // ✅ Limitamos coverage al código compartido (excluimos páginas manuales de app/)
    "<rootDir>/src/components/forms/**/*.{ts,tsx}",
    "<rootDir>/src/components/sidebar/**/*.{ts,tsx}",
    "<rootDir>/src/components/news/**/*.{ts,tsx}",
    "!<rootDir>/src/tests/**/*", // ✅ Excluimos utilidades de pruebas (MSW, mocks) del cómputo de cobertura
    "!<rootDir>/src/types/**/*", // ✅ Tipos .d.ts no ejecutables fuera del scope de coverage
    "!<rootDir>/app/**/__tests__/**",
    "!<rootDir>/src/**/__tests__/**",
    "!<rootDir>/src/**/stories/**",
  ],
};

module.exports = baseConfig;
