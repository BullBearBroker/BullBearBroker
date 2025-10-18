/* Extiende config base y añade entorno jsdom + setups locales */
let base = {};
try {
  base = require('./jest.config.base.cjs');
} catch {}

module.exports = {
  ...base,
  testEnvironment: 'jsdom',
  moduleNameMapper: {
    ...(base.moduleNameMapper || {}),
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@/styles/globals\\.css$': '<rootDir>/__mocks__/styleMock.js',
    '\\.(css|less|sass|scss)$': '<rootDir>/__mocks__/styleMock.js',
    '\\.(png|jpg|jpeg|gif|svg)$': '<rootDir>/__mocks__/fileMock.js',
  },
  setupFiles: [
    '<rootDir>/jest.env.setup.ts',
    'whatwg-fetch',
    ...(base.setupFiles || []),
  ],
  setupFilesAfterEnv: [
    '<rootDir>/jest.setup.ts',
    '@testing-library/jest-dom',
    ...(base.setupFilesAfterEnv || []),
  ],
};
