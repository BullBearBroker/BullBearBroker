import next from "eslint-config-next";

export default [
  ...next(),
  {
    rules: {
      "@next/next/no-html-link-for-pages": "off"
    }
  }
];
