import fs from "node:fs";
import path from "node:path";

const OUTPUT_DIR = path.join(process.cwd(), ".next", "analyze");
let prepared = false;

const ensureOutputDir = () => {
  if (!prepared) {
    fs.rmSync(OUTPUT_DIR, { recursive: true, force: true });
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    prepared = true;
  }
};

const formatSize = (size = 0) => {
  if (!Number.isFinite(size)) return "0 B";
  if (size <= 0) return "0 B";
  const units = ["B", "kB", "MB", "GB"];
  let index = 0;
  let value = size;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index === 0 ? 0 : 2)} ${units[index]}`;
};

const renderAssetsTable = (assets = []) => {
  if (!assets.length) {
    return `<p>No se encontraron assets para este target.</p>`;
  }

  const rows = assets
    .sort((a, b) => (b.size ?? 0) - (a.size ?? 0))
    .map((asset) => {
      const sizeLabel = formatSize(asset.size ?? 0);
      const chunkNames = Array.isArray(asset.chunkNames)
        ? asset.chunkNames.filter(Boolean).join(", ")
        : "";
      return `<tr><td>${asset.name}</td><td>${sizeLabel}</td><td>${chunkNames}</td></tr>`;
    })
    .join("\n");

  return `<table><thead><tr><th>Asset</th><th>Tamaño</th><th>Chunks</th></tr></thead><tbody>${rows}</tbody></table>`;
};

const renderEntrypoints = (entrypoints = {}) => {
  const entries = Object.entries(entrypoints);
  if (!entries.length) return "";
  const rows = entries
    .map(([name, data]) => {
      const assets = Array.isArray(data.assets)
        ? data.assets.map((asset) => asset.name ?? asset).join(", ")
        : "";
      return `<tr><td>${name}</td><td>${assets}</td></tr>`;
    })
    .join("\n");
  return `<section><h2>Entrypoints</h2><table><thead><tr><th>Nombre</th><th>Assets</th></tr></thead><tbody>${rows}</tbody></table></section>`;
};

const renderHtml = (targetLabel, statsJson) => {
  const assets = Array.isArray(statsJson.assets) ? statsJson.assets : [];
  const totalSize = formatSize(
    assets.reduce((total, asset) => total + (asset.size ?? 0), 0)
  );
  const assetsTable = renderAssetsTable(assets);
  const entrypointsSection = renderEntrypoints(statsJson.entrypoints ?? {});

  return `<!DOCTYPE html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <title>Reporte de bundle · ${targetLabel}</title>
    <style>
      :root {
        color-scheme: light dark;
        font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
        background: #0f172a;
        color: #f1f5f9;
      }
      body {
        margin: 2rem;
        background: #0f172a;
        color: #f1f5f9;
      }
      h1 {
        font-size: 1.5rem;
        margin-bottom: 1rem;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 1rem;
      }
      th, td {
        border: 1px solid rgba(148, 163, 184, 0.4);
        padding: 0.5rem 0.75rem;
        text-align: left;
      }
      th {
        background: rgba(30, 41, 59, 0.8);
      }
      tbody tr:nth-child(even) {
        background: rgba(15, 23, 42, 0.6);
      }
      section {
        margin-top: 2rem;
      }
    </style>
  </head>
  <body>
    <h1>Reporte de bundle (${targetLabel})</h1>
    <p><strong>Tamaño total:</strong> ${totalSize}</p>
    ${assetsTable}
    ${entrypointsSection}
  </body>
</html>`;
};

const createAnalyzerPlugin = (targetLabel) => {
  return class SimpleBundleAnalyzerPlugin {
    apply(compiler) {
      compiler.hooks.done.tap("SimpleBundleAnalyzerPlugin", (stats) => {
        ensureOutputDir();
        const statsJson = stats.toJson({
          all: false,
          assets: true,
          entrypoints: true,
          chunks: false,
          modules: false,
          reasons: false,
          source: false,
        });
        const filename = targetLabel === "client" ? "client.html" : "nodejs.html";
        const html = renderHtml(targetLabel, statsJson);
        fs.writeFileSync(path.join(OUTPUT_DIR, filename), html, "utf8");
      });
    }
  };
};

const withAnalyzer = ({ enabled = false } = {}) => {
  return (nextConfig = {}) => {
    if (!enabled) {
      return nextConfig;
    }

    return {
      ...nextConfig,
      webpack(config = {}, options) {
        const plugins = config.plugins ? [...config.plugins] : [];
        const targetLabel = options.isServer ? "nodejs" : "client";
        const AnalyzerPlugin = createAnalyzerPlugin(targetLabel);
        plugins.push(new AnalyzerPlugin());
        const finalConfig = {
          ...config,
          plugins,
        };

        if (typeof nextConfig.webpack === "function") {
          return nextConfig.webpack(finalConfig, options);
        }

        return finalConfig;
      },
    };
  };
};

export default withAnalyzer;
