import type { Config } from "jest";
import baseConfig from "./jest.config.base";

const config: Config = {
  ...baseConfig,
  collectCoverage: true,
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
