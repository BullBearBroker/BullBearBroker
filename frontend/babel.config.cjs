// babel.config.cjs o .babelrc.js (igual contenido en los dos)
module.exports = {
  presets: [
    "next/babel",          // ✅ Preset oficial de Next.js (JSX + TS integrado)
    ["@babel/preset-env", { targets: { node: "current" } }], // ✅ Compatibilidad Node
    "@babel/preset-react", // ✅ JSX explícito (aunque next/babel ya lo incluye, no estorba)
    "@babel/preset-typescript" // ✅ TS/TSX
  ],
};
