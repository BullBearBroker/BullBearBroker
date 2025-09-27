"use client";

import { useEffect, useState } from "react";
import { getIndicators } from "@/lib/api";
import { IndicatorsChart } from "@/components/indicators/IndicatorsChart";

export default function TestIndicators() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 🔹 Probamos con BTCUSDT a 1h
    getIndicators("crypto", "BTCUSDT", "1h")
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div style={{ padding: "2rem", fontFamily: "Arial" }}>
      <h1>📊 Test API Indicators</h1>
      {loading && <p>Cargando datos...</p>}
      {error && <p style={{ color: "red" }}>Error: {error}</p>}
      {data && (
        <>
          <h2>
            {data.symbol} ({data.interval})
          </h2>

          {/* 🔹 Gráfico con indicadores */}
          <IndicatorsChart
            symbol={data.symbol}
            interval={data.interval}
            indicators={data.indicators}
            series={data.series}
          />

          {/* 🔹 JSON crudo para debug */}
          <pre style={{ marginTop: "2rem" }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </>
      )}
    </div>
  );
}
