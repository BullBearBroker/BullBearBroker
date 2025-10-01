const config = {
  presets: [
    [
      "@babel/preset-env",
      { targets: { node: "current" }, modules: "commonjs" },
    ],
    "@babel/preset-typescript",
    "@babel/preset-react",
    "next/babel",
  ],
  ignore: [],
};

export default config;

// Provide CommonJS export for tooling that still uses require().
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
if (typeof module !== "undefined") {
  // eslint-disable-next-line @typescript-eslint/ban-ts-comment
  // @ts-ignore
  module.exports = config;
}
