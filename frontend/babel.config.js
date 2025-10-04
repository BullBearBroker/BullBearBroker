const config = {
  presets: [
    "next/babel",
    [
      "@babel/preset-env",
      // Keep modules disabled so that Babel preserves native ESM output for Next.js tooling.
      { targets: { node: "current" }, modules: false },
    ],
    [
      "@babel/preset-react",
      // Ensure the automatic JSX runtime so that React imports remain implicit across the app.
      { runtime: "automatic" },
    ],
    "@babel/preset-typescript",
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
