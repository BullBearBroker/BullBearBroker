import type { Config } from "jest";
import path from "path";

const config: Config = {
  rootDir: path.resolve(__dirname),

  testEnvironment: "jsdom",
  testEnvironmentOptions: {
    url: "http://localhost",
  },

  setupFilesAfterEnv: [
    "<rootDir>/jest.setup.ts",
    "<rootDir>/src/tests/msw/setup.ts",
  ],

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

  // ✅ Forzar a Jest a usar Babel en tests y TS/JSX
  transform: {
    "^.+\\.(js|jsx|ts|tsx)$": [
      "babel-jest",
      {

        presets: [
          "next/babel",
          "@babel/preset-env",
          "@babel/preset-react",
          "@babel/preset-typescript",
        ],

      },
    ],
  },

  transformIgnorePatterns: [
    "/node_modules/(?!(recharts|d3-|msw|@mswjs|until-async|strict-event-emitter|outvariant|headers-polyfill)/)",
  ],

  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json", "node"],

  testMatch: [
    "<rootDir>/src/**/*.test.(ts|tsx|js|jsx)",
    "<rootDir>/src/**/__tests__/**/*.(ts|tsx|js|jsx)",
  ],
  testPathIgnorePatterns: ["<rootDir>/.next/", "<rootDir>/node_modules/"],

  clearMocks: true,

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
