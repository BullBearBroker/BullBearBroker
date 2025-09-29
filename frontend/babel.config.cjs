module.exports = function (api) {
  const isTest = api.env("test");

  return {
    presets: [
      [
        "next/babel",
        {
          "preset-env": {
            targets: isTest ? { node: "current" } : undefined,
            modules: isTest ? "commonjs" : false,
          },
        },
      ],
      isTest && "@babel/preset-typescript",
    ].filter(Boolean),
  };
};
