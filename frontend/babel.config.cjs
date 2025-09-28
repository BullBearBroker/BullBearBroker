// frontend/babel.config.cjs
module.exports = {
  presets: [
    "next/babel",          // Preset oficial de Next.js
    "@babel/preset-env",   // Transforma ESNext a Node compatible
    "@babel/preset-react", // Soporte JSX
    "@babel/preset-typescript", // Soporte TS/TSX
  ],
};
