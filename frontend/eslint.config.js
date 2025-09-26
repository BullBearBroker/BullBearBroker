// eslint.config.js
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import nextPlugin from "@next/eslint-plugin-next";

export default [
  {
    // ⛔️ Ignorar build outputs y dependencias
    ignores: [
      "node_modules/",
      ".next/",
      "dist/",
      "build/",
      "coverage/",
      "out/",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    plugins: {
      "@next/next": nextPlugin,
    },
    rules: {
      ...nextPlugin.configs["core-web-vitals"].rules,

      // Personalización
      "@next/next/no-html-link-for-pages": "off",

      // TS: reducir ruido
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unsafe-function-type": "off",
      "@typescript-eslint/no-empty-object-type": "off",

      // JS genérico
      "no-undef": "off",
      "no-empty": "warn",
      "no-prototype-builtins": "off",
      "no-useless-escape": "off",
      "no-fallthrough": "off",
      "no-case-declarations": "off",
      "no-control-regex": "off",
      "no-redeclare": "off",
      "no-self-assign": "off",
      "no-cond-assign": "off",
      "@typescript-eslint/no-unused-expressions": "off",
      "@typescript-eslint/no-this-alias": "off",
    },
  },
  {
    files: ["tailwind.config.js", "postcss.config.js"],
    rules: {
      "@typescript-eslint/no-require-imports": "off",
    },
  },
];
