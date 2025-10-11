import path from "path";

type InterceptorModule = Record<string, unknown>;

const candidates = [
  path.resolve(
    __dirname,
    "../../../..",
    "node_modules",
    "@mswjs",
    "interceptors",
    "lib",
    "node",
    "interceptors",
  ),
  path.resolve(
    __dirname,
    "../../../../../",
    "node_modules",
    ".pnpm",
    "node_modules",
    "@mswjs",
    "interceptors",
    "lib",
    "node",
    "interceptors",
  ),
];

export function loadInterceptor(target: string): InterceptorModule {
  for (const basePath of candidates) {
    try {

      return require(path.join(basePath, target, "index.js")) as InterceptorModule;
    } catch (error) {
      // Continue searching in other candidates
    }
  }

  throw new Error(`No se pudo resolver el interceptor ${target}`);
}
