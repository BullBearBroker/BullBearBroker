const base = require('./jest.config.base.cjs');

/** Merge helper que evita duplicados sencillos */
function uniq(arr) { return Array.from(new Set(arr.filter(Boolean))); }

module.exports = {
  ...base,

  // Entorno del navegador para tests de React
  testEnvironment: 'jsdom',

  // Alias @/ -> <rootDir>/src/
  moduleNameMapper: {
    ...(base.moduleNameMapper || {}),
    '^@/(.*)$': '<rootDir>/src/$1',
    // Mapea estáticos básicos (por si aparecen en tests)
    '\\.(css|less|sass|scss)$': '<rootDir>/__mocks__/styleMock.js',
    '\\.(jpg|jpeg|png|gif|webp|avif|svg)$': '<rootDir>/__mocks__/fileMock.js',
  },

  // Ficheros cargados ANTES que el entorno (variables)
  setupFiles: uniq([
    ...(base.setupFiles || []),
    '<rootDir>/jest.env.setup.ts',
  ]),

  // Ficheros cargados DESPUÉS (polyfills, mocks y custom setup)
  setupFilesAfterEnv: uniq([
    ...(base.setupFilesAfterEnv || []),
    'whatwg-fetch',                        // fetch() en JSDOM
    '@testing-library/jest-dom',           // matchers extra
    '<rootDir>/src/tests/mocks/jest-websocket-mock.ts', // WS mock si existe
    '<rootDir>/jest.setup.ts',             // tu setup principal
  ]),
};
