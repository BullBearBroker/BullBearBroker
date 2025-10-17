const baseConfig = require("./jest.config.base.cjs");

/** @type {import('jest').Config} */
module.exports = {
  ...baseConfig,
  collectCoverage: false,
};
