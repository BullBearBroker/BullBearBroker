"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  BarChart,
  Bar,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";

interface IndicatorsChartProps {
  symbol: string;
  interval: string;
  indicators: Record<string, any>;
  series?: {
    closes?: number[];
    highs?: number[];
    lows?: number[];
  };
  insights?: string | null;
  loading?: boolean;
  error?: string | null;
}

export function IndicatorsChart({
  symbol,
  interval,
  indicators,
  series,
  insights,
  loading,
  error,
}: IndicatorsChartProps) {
  const closes = series?.closes && series.closes.length > 0
    ? series.closes
    : [indicators.last_close ?? 0];

  const emaList: { period: number; value: number }[] = indicators.ema ?? [];
  const bollinger = indicators.bollinger ?? null;
  const rsiDataFull = indicators.rsi ?? null;
  const macdDataFull = indicators.macd ?? null;
  const atrData = indicators.atr ?? null; // [Codex] nuevo
  const stochData = indicators.stochastic_rsi ?? null; // [Codex] nuevo
  const ichimokuData = indicators.ichimoku ?? null; // [Codex] nuevo
  const vwapData = indicators.vwap ?? null; // [Codex] nuevo

  const ema20 = emaList.find((item) => item.period === 20)?.value ?? null;
  const ema50 = emaList.find((item) => item.period === 50)?.value ?? null;

  const chartData = closes.map((close, idx) => ({
    index: idx,
    close,
    ema20,
    ema50,
    upper: bollinger?.upper ?? null,
    lower: bollinger?.lower ?? null,
    middle: bollinger?.middle ?? null,
  }));

  const rsiData = rsiDataFull
    ? [{ index: 0, value: rsiDataFull.value }]
    : [];
  const macdChartData = macdDataFull
    ? [
        {
          index: 0,
          macd: macdDataFull.macd,
          signal: macdDataFull.signal,
          hist: macdDataFull.hist,
        },
      ]
    : [];

  const insightBlocks = insights?.split(/\n+/).filter((line) => line.trim().length > 0) ?? []; // [Codex] nuevo

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      <div className="space-y-6">
        <header className="flex flex-col gap-1">
          <h2 className="text-xl font-semibold">{symbol} · {interval.toUpperCase()}</h2>
          <p className="text-sm text-muted-foreground">
            Último cierre: {indicators.last_close ?? "n/d"}
          </p>
        </header>

        <div className="space-y-8">
          <div style={{ width: "100%", height: 320 }}>
            <ResponsiveContainer>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="index" hide />
                <YAxis domain={["auto", "auto"]} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="close" stroke="#000000" dot={false} name="Precio" />
                <Line type="monotone" dataKey="ema20" stroke="#FF5733" dot={false} name="EMA 20" />
                <Line type="monotone" dataKey="ema50" stroke="#3366FF" dot={false} name="EMA 50" />
                <Line type="monotone" dataKey="upper" stroke="#8884d8" dot={false} name="BB Upper" />
                <Line type="monotone" dataKey="lower" stroke="#82ca9d" dot={false} name="BB Lower" />
                <Line type="monotone" dataKey="middle" stroke="#aaaaaa" dot={false} name="BB Middle" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {rsiDataFull && (
            <div style={{ width: "100%", height: 200 }}>
              <h3 className="mb-2 text-sm font-medium">RSI (Periodo {rsiDataFull.period})</h3>
              <ResponsiveContainer>
                <LineChart data={rsiData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="index" hide />
                  <YAxis domain={[0, 100]} />
                  <ReferenceLine y={30} stroke="red" strokeDasharray="3 3" />
                  <ReferenceLine y={70} stroke="green" strokeDasharray="3 3" />
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="#FFAA00" dot name="RSI" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {macdDataFull && (
            <div style={{ width: "100%", height: 240 }}>
              <h3 className="mb-2 text-sm font-medium">MACD</h3>
              <ResponsiveContainer>
                <LineChart data={macdChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="index" hide />
                  <YAxis domain={["auto", "auto"]} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="macd" stroke="#0088FE" name="MACD" />
                  <Line type="monotone" dataKey="signal" stroke="#FF0000" name="Signal" />
                  <BarChart data={macdChartData}>
                    <Bar dataKey="hist" fill="#82ca9d" name="Histograma" />
                  </BarChart>
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <section className="grid gap-4 md:grid-cols-2">
            {atrData && (
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">ATR (Periodo {atrData.period})</p>
                <p className="text-lg font-semibold">{atrData.value}</p>
              </div>
            )}
            {stochData && (
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Stochastic RSI</p>
                <p className="text-lg font-semibold">%K {stochData["%K"]} · %D {stochData["%D"]}</p>
              </div>
            )}
            {ichimokuData && (
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Ichimoku</p>
                <p className="text-sm">Tenkan: {ichimokuData.tenkan_sen}</p>
                <p className="text-sm">Kijun: {ichimokuData.kijun_sen}</p>
                <p className="text-sm">Span A/B: {ichimokuData.senkou_span_a} / {ichimokuData.senkou_span_b}</p>
              </div>
            )}
            {vwapData && (
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">VWAP</p>
                <p className="text-lg font-semibold">{vwapData.value}</p>
              </div>
            )}
          </section>
        </div>
      </div>

      {/* [Codex] nuevo - resumen con insights generados por IA */}
      <aside className="flex flex-col gap-4 rounded-lg border bg-muted/20 p-4">
        <h3 className="text-lg font-semibold">🧠 Insights de la IA</h3>
        {loading && <p className="text-sm text-muted-foreground">Analizando indicadores...</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && insightBlocks.length === 0 && (
          <p className="text-sm text-muted-foreground">Aún no hay comentarios generados.</p>
        )}
        <ul className="space-y-2 text-sm">
          {insightBlocks.map((line, idx) => (
            <li key={idx} className="rounded-md bg-background p-2 shadow-sm">
              {line}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
