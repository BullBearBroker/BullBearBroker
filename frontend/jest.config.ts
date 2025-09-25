import type { Config } from "jest";

const config: Config = {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
    "^.+\\.(css|less|scss|sass)$": "identity-obj-proxy"
  },
  transform: {
    "^.+\\.(t|j)sx?$": [
      "ts-jest",
      {
        tsconfig: "<rootDir>/tsconfig.json"
      }
    ]
  },
  testPathIgnorePatterns: ["<rootDir>/.next/", "<rootDir>/node_modules/"]
};

export default config;
