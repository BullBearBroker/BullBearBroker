"use client";

import {
  Area,
  AreaChart,
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { HistoricalDataResponse } from "@/lib/api";

interface IndicatorsChartProps {
  symbol: string;
  interval: string;
  indicators: Record<string, any>;
  series?: {
    closes?: number[];
    highs?: number[];
    lows?: number[];
    volumes?: number[];
  };
  history?: HistoricalDataResponse | null;
  historyError?: string | null;
  historyLoading?: boolean;
  insights?: string | null;
  loading?: boolean;
  error?: string | null;
}

interface CandleLike {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

function computeEMA(values: number[], period: number): (number | null)[] {
  const result: (number | null)[] = Array(values.length).fill(null);
  if (values.length < period || period <= 0) {
    return result;
  }
  const smoothing = 2 / (period + 1);
  let sum = 0;
  for (let i = 0; i < period; i += 1) {
    sum += values[i];
  }
  let ema = sum / period;
  result[period - 1] = ema;
  for (let i = period; i < values.length; i += 1) {
    ema = (values[i] - ema) * smoothing + ema;
    result[i] = ema;
  }
  return result;
}

function computeEMAFromNullable(values: (number | null)[], period: number): (number | null)[] {
  const result: (number | null)[] = Array(values.length).fill(null);
  const filtered: number[] = [];
  const indexes: number[] = [];
  for (let i = 0; i < values.length; i += 1) {
    const value = values[i];
    if (value !== null && Number.isFinite(value)) {
      filtered.push(value);
      indexes.push(i);
    }
  }
  if (filtered.length < period || period <= 0) {
    return result;
  }
  const smoothing = 2 / (period + 1);
  let sum = 0;
  for (let i = 0; i < period; i += 1) {
    sum += filtered[i];
  }
  let ema = sum / period;
  result[indexes[period - 1]] = ema;
  for (let i = period; i < filtered.length; i += 1) {
    ema = (filtered[i] - ema) * smoothing + ema;
    result[indexes[i]] = ema;
  }
  return result;
}

function computeBollinger(values: number[], period: number, mult: number) {
  const upper: (number | null)[] = Array(values.length).fill(null);
  const middle: (number | null)[] = Array(values.length).fill(null);
  const lower: (number | null)[] = Array(values.length).fill(null);
  if (values.length < period || period <= 1) {
    return { upper, middle, lower };
  }
  for (let i = period - 1; i < values.length; i += 1) {
    const window = values.slice(i - period + 1, i + 1);
    const mean = window.reduce((acc, val) => acc + val, 0) / period;
    const variance =
      window.reduce((acc, val) => acc + (val - mean) * (val - mean), 0) / period;
    const deviation = Math.sqrt(variance);
    upper[i] = mean + mult * deviation;
    middle[i] = mean;
    lower[i] = mean - mult * deviation;
  }
  return { upper, middle, lower };
}

function computeRSI(values: number[], period: number): (number | null)[] {
  const result: (number | null)[] = Array(values.length).fill(null);
  if (values.length <= period) {
    return result;
  }
  let gains = 0;
  let losses = 0;
  for (let i = 1; i <= period; i += 1) {
    const delta = values[i] - values[i - 1];
    if (delta >= 0) {
      gains += delta;
    } else {
      losses -= delta;
    }
  }
  let averageGain = gains / period;
  let averageLoss = losses / period;
  const firstIndex = period;
  if (averageLoss === 0) {
    result[firstIndex] = 100;
  } else {
    const rs = averageGain / averageLoss;
    result[firstIndex] = 100 - 100 / (1 + rs);
  }
  for (let i = period + 1; i < values.length; i += 1) {
    const delta = values[i] - values[i - 1];
    const gain = delta > 0 ? delta : 0;
    const loss = delta < 0 ? -delta : 0;
    averageGain = (averageGain * (period - 1) + gain) / period;
    averageLoss = (averageLoss * (period - 1) + loss) / period;
    if (averageLoss === 0) {
      result[i] = 100;
    } else {
      const rs = averageGain / averageLoss;
      result[i] = 100 - 100 / (1 + rs);
    }
  }
  return result;
}

function computeATR(
  highs: number[],
  lows: number[],
  closes: number[],
  period: number
): (number | null)[] {
  const len = Math.min(highs.length, lows.length, closes.length);
  const tr: number[] = [];
  for (let i = 0; i < len; i += 1) {
    if (i === 0) {
      tr.push(highs[i] - lows[i]);
    } else {
      const currentHigh = highs[i];
      const currentLow = lows[i];
      const prevClose = closes[i - 1];
      tr.push(
        Math.max(
          currentHigh - currentLow,
          Math.abs(currentHigh - prevClose),
          Math.abs(currentLow - prevClose)
        )
      );
    }
  }
  const result: (number | null)[] = Array(len).fill(null);
  if (tr.length < period || period <= 0) {
    return result;
  }
  let sum = 0;
  for (let i = 0; i < period; i += 1) {
    sum += tr[i];
  }
  let atr = sum / period;
  result[period - 1] = atr;
  for (let i = period; i < tr.length; i += 1) {
    atr = (atr * (period - 1) + tr[i]) / period;
    result[i] = atr;
  }
  return result;
}

function computeMACD(
  values: number[],
  fast: number,
  slow: number,
  signal: number
) {
  const fastEma = computeEMA(values, fast);
  const slowEma = computeEMA(values, slow);
  const macd: (number | null)[] = values.map((_, idx) => {
    const fastValue = fastEma[idx];
    const slowValue = slowEma[idx];
    if (fastValue === null || slowValue === null) {
      return null;
    }
    return fastValue - slowValue;
  });
  const signalSeries = computeEMAFromNullable(macd, signal);
  const histogram: (number | null)[] = macd.map((value, idx) => {
    const signalValue = signalSeries[idx];
    if (value === null || signalValue === null) {
      return null;
    }
    return value - signalValue;
  });
  return { macd, signal: signalSeries, histogram };
}

function computeIchimoku(
  highs: number[],
  lows: number[],
  conversion: number,
  base: number,
  spanB: number
) {
  const len = Math.min(highs.length, lows.length);
  const tenkan: (number | null)[] = Array(len).fill(null);
  const kijun: (number | null)[] = Array(len).fill(null);
  const spanA: (number | null)[] = Array(len).fill(null);
  const spanBSeries: (number | null)[] = Array(len).fill(null);

  const rollingAverage = (start: number, end: number) => {
    const windowHigh = Math.max(...highs.slice(start, end));
    const windowLow = Math.min(...lows.slice(start, end));
    return (windowHigh + windowLow) / 2;
  };

  for (let i = conversion - 1; i < len; i += 1) {
    tenkan[i] = rollingAverage(i - conversion + 1, i + 1);
  }
  for (let i = base - 1; i < len; i += 1) {
    kijun[i] = rollingAverage(i - base + 1, i + 1);
  }
  for (let i = 0; i < len; i += 1) {
    const tenkanValue = tenkan[i];
    const kijunValue = kijun[i];
    if (tenkanValue !== null && kijunValue !== null) {
      spanA[i] = (tenkanValue + kijunValue) / 2;
    }
  }
  for (let i = spanB - 1; i < len; i += 1) {
    spanBSeries[i] = rollingAverage(i - spanB + 1, i + 1);
  }

  return { tenkan, kijun, spanA, spanB: spanBSeries };
}

function computeVWAP(
  highs: number[],
  lows: number[],
  closes: number[],
  volumes: number[]
): (number | null)[] {
  const len = Math.min(highs.length, lows.length, closes.length, volumes.length);
  const result: (number | null)[] = Array(len).fill(null);
  let cumulativeValue = 0;
  let cumulativeVolume = 0;
  for (let i = 0; i < len; i += 1) {
    const typicalPrice = (highs[i] + lows[i] + closes[i]) / 3;
    const volume = volumes[i] ?? 0;
    cumulativeValue += typicalPrice * volume;
    cumulativeVolume += volume;
    if (cumulativeVolume > 0) {
      result[i] = cumulativeValue / cumulativeVolume;
    } else {
      result[i] = null;
    }
  }
  return result;
}

export function IndicatorsChart({
  symbol,
  interval,
  indicators,
  series,
  history,
  historyError,
  historyLoading,
  insights,
  loading,
  error,
}: IndicatorsChartProps) {
  const fallbackCandles: CandleLike[] = (series?.closes ?? []).map((close, idx) => ({
    timestamp: `${idx}`,
    open: series?.closes?.[idx] ?? close,
    high: series?.highs?.[idx] ?? close,
    low: series?.lows?.[idx] ?? close,
    close,
    volume: series?.volumes?.[idx] ?? 0,
  }));

  const candles = history?.values?.length
    ? history.values.map((item) => ({
        timestamp: item.timestamp,
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close,
        volume: item.volume ?? 0,
      }))
    : fallbackCandles;

  const closes = candles.map((item) => item.close);
  const highs = candles.map((item) => item.high ?? item.close);
  const lows = candles.map((item) => item.low ?? item.close);
  const volumes = candles.map((item) => item.volume ?? 0);

  const emaFastPeriod = indicators.ema?.[0]?.period ?? 20;
  const emaSlowPeriod = indicators.ema?.[1]?.period ?? 50;
  const bollingerPeriod = indicators.bollinger?.period ?? 20;
  const bollingerMult = indicators.bollinger?.mult ?? 2;
  const rsiPeriod = indicators.rsi?.period ?? 14;
  const atrPeriod = indicators.atr?.period ?? 14;
  const macdFast = indicators.macd?.fast ?? 12;
  const macdSlow = indicators.macd?.slow ?? 26;
  const macdSignal = indicators.macd?.signal ?? 9;
  const ichimokuSettings = indicators.ichimoku;
  const showIchimoku = Boolean(ichimokuSettings);
  const showATR = Boolean(indicators.atr);
  const showRSI = Boolean(indicators.rsi);
  const showVWAP = Boolean(indicators.vwap) || volumes.some((volume) => volume > 0);

  const emaFast = computeEMA(closes, emaFastPeriod);
  const emaSlow = computeEMA(closes, emaSlowPeriod);
  const bollinger = computeBollinger(closes, bollingerPeriod, bollingerMult);
  const rsiSeries = computeRSI(closes, rsiPeriod);
  const atrSeries = showATR ? computeATR(highs, lows, closes, atrPeriod) : [];
  const macdSeries = computeMACD(closes, macdFast, macdSlow, macdSignal);
  const ichimokuSeries = showIchimoku
    ? computeIchimoku(
        highs,
        lows,
        ichimokuSettings.conversion ?? 9,
        ichimokuSettings.base ?? 26,
        ichimokuSettings.span_b ?? 52
      )
    : null;
  const vwapSeries = showVWAP ? computeVWAP(highs, lows, closes, volumes) : [];

  const labels = candles.map((item, idx) => {
    if (history?.values?.length) {
      try {
        return new Date(item.timestamp).toLocaleString("es-ES", { hour12: false });
      } catch (err) {
        return item.timestamp;
      }
    }
    return `#${idx + 1}`;
  });

  const priceChartData = candles.map((item, idx) => ({
    index: idx,
    label: labels[idx],
    close: item.close,
    emaFast: emaFast[idx],
    emaSlow: emaSlow[idx],
    bollingerUpper: bollinger.upper[idx],
    bollingerLower: bollinger.lower[idx],
    bollingerMiddle: bollinger.middle[idx],
    vwap: vwapSeries[idx] ?? null,
  }));

  const rsiChartData = rsiSeries.map((value, idx) => ({
    index: idx,
    label: labels[idx],
    value,
  }));

  const atrChartData = atrSeries.map((value, idx) => ({
    index: idx,
    label: labels[idx],
    value,
  }));

  const ichimokuChartData = (ichimokuSeries?.tenkan ?? []).map((_, idx) => ({
    index: idx,
    label: labels[idx],
    tenkan: ichimokuSeries?.tenkan[idx] ?? null,
    kijun: ichimokuSeries?.kijun[idx] ?? null,
    spanA: ichimokuSeries?.spanA[idx] ?? null,
    spanB: ichimokuSeries?.spanB[idx] ?? null,
  }));

  const macdChartData = macdSeries.macd.map((value, idx) => ({
    index: idx,
    label: labels[idx],
    macd: value,
    signal: macdSeries.signal[idx],
    histogram: macdSeries.histogram[idx],
  }));

  const insightBlocks =
    insights?.split(/\n+/).filter((line) => line.trim().length > 0) ?? [];

  return (
    <div className="grid gap-6 xl:grid-cols-[2fr_1fr]" data-testid="technical-analysis">
      <div className="space-y-6">
        <header className="space-y-1">
          <h2 className="text-xl font-semibold">
            {symbol} · {interval.toUpperCase()}
          </h2>
          <p className="text-sm text-muted-foreground">
            Último cierre: {indicators.last_close ?? "n/d"}
          </p>
          {history?.source && (
            <p className="text-xs text-muted-foreground">
              Histórico desde: {history.source}
            </p>
          )}
          {historyError && (
            <p className="text-xs text-destructive">{historyError}</p>
          )}
        </header>

        <section className="space-y-4">
          <div className="rounded-lg border bg-card p-4">
            <h3 className="text-sm font-medium">Precio, EMAs y Bandas de Bollinger</h3>
            <div className="mt-3 h-72 w-full">
              {historyLoading && !priceChartData.length ? (
                <p className="text-sm text-muted-foreground">Cargando serie histórica...</p>
              ) : (
                <ResponsiveContainer>
                  <LineChart data={priceChartData} margin={{ left: 12, right: 12, top: 16, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="index" tickFormatter={(value) => priceChartData[value]?.label ?? value} interval="preserveStartEnd" />
                    <YAxis domain={["auto", "auto"]} width={60} />
                    <Tooltip
                      labelFormatter={(value) => priceChartData[value as number]?.label ?? String(value)}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="close" stroke="#0f172a" dot={false} name="Precio" strokeWidth={1.5} />
                    <Line type="monotone" dataKey="emaFast" stroke="#ec4899" dot={false} name={`EMA ${emaFastPeriod}`} strokeWidth={1.2} />
                    <Line type="monotone" dataKey="emaSlow" stroke="#6366f1" dot={false} name={`EMA ${emaSlowPeriod}`} strokeWidth={1.2} />
                    <Line type="monotone" dataKey="bollingerUpper" stroke="#38bdf8" dot={false} name="Bollinger Sup" strokeDasharray="5 5" />
                    <Line type="monotone" dataKey="bollingerLower" stroke="#22c55e" dot={false} name="Bollinger Inf" strokeDasharray="5 5" />
                    <Line type="monotone" dataKey="bollingerMiddle" stroke="#94a3b8" dot={false} name="Bollinger Media" strokeDasharray="3 3" />
                    {showVWAP && (
                      <Line type="monotone" dataKey="vwap" stroke="#f97316" dot={false} name="VWAP" strokeWidth={1.5} />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border bg-card p-4">
              <h3 className="text-sm font-medium">Índice de Fuerza Relativa (RSI)</h3>
              <div className="mt-3 h-56 w-full">
                {showRSI ? (
                  <ResponsiveContainer>
                    <LineChart data={rsiChartData} margin={{ left: 12, right: 12, top: 16, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="index" tickFormatter={(value) => rsiChartData[value]?.label ?? value} interval="preserveStartEnd" />
                      <YAxis domain={[0, 100]} width={50} />
                      <Tooltip labelFormatter={(value) => rsiChartData[value as number]?.label ?? String(value)} />
                      <Legend />
                      <ReferenceLine y={30} stroke="#ef4444" strokeDasharray="4 4" />
                      <ReferenceLine y={70} stroke="#22c55e" strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="value" stroke="#f59e0b" dot={false} name={`RSI ${rsiPeriod}`} strokeWidth={1.5} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-muted-foreground">RSI no disponible.</p>
                )}
              </div>
            </div>

            <div className="rounded-lg border bg-card p-4">
              <h3 className="text-sm font-medium">Average True Range (ATR)</h3>
              <div className="mt-3 h-56 w-full">
                {showATR ? (
                  <ResponsiveContainer>
                    <AreaChart data={atrChartData} margin={{ left: 12, right: 12, top: 16, bottom: 8 }}>
                      <defs>
                        <linearGradient id="atrGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="index" tickFormatter={(value) => atrChartData[value]?.label ?? value} interval="preserveStartEnd" />
                      <YAxis width={60} />
                      <Tooltip labelFormatter={(value) => atrChartData[value as number]?.label ?? String(value)} />
                      <Legend />
                      <Area type="monotone" dataKey="value" stroke="#38bdf8" fillOpacity={1} fill="url(#atrGradient)" name={`ATR ${atrPeriod}`} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-muted-foreground">ATR no disponible.</p>
                )}
              </div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border bg-card p-4">
              <h3 className="text-sm font-medium">Ichimoku</h3>
              <div className="mt-3 h-56 w-full">
                {showIchimoku && ichimokuSeries ? (
                  <ResponsiveContainer>
                    <LineChart data={ichimokuChartData} margin={{ left: 12, right: 12, top: 16, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="index" tickFormatter={(value) => ichimokuChartData[value]?.label ?? value} interval="preserveStartEnd" />
                      <YAxis width={60} />
                      <Tooltip labelFormatter={(value) => ichimokuChartData[value as number]?.label ?? String(value)} />
                      <Legend />
                      <Line type="monotone" dataKey="tenkan" stroke="#f97316" dot={false} name="Tenkan" />
                      <Line type="monotone" dataKey="kijun" stroke="#22d3ee" dot={false} name="Kijun" />
                      <Line type="monotone" dataKey="spanA" stroke="#6366f1" dot={false} name="Span A" strokeDasharray="5 5" />
                      <Line type="monotone" dataKey="spanB" stroke="#10b981" dot={false} name="Span B" strokeDasharray="5 5" />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-muted-foreground">Ichimoku no disponible.</p>
                )}
              </div>
            </div>

            <div className="rounded-lg border bg-card p-4">
              <h3 className="text-sm font-medium">MACD</h3>
              <div className="mt-3 h-56 w-full">
                <ResponsiveContainer>
                  <ComposedChart data={macdChartData} margin={{ left: 12, right: 12, top: 16, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="index" tickFormatter={(value) => macdChartData[value]?.label ?? value} interval="preserveStartEnd" />
                    <YAxis width={60} />
                    <Tooltip labelFormatter={(value) => macdChartData[value as number]?.label ?? String(value)} />
                    <Legend />
                    <Line type="monotone" dataKey="macd" stroke="#0ea5e9" dot={false} name="MACD" />
                    <Line type="monotone" dataKey="signal" stroke="#ef4444" dot={false} name="Signal" />
                    <Bar dataKey="histogram" fill="#22c55e" name="Histograma" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </section>
      </div>

      <aside className="flex flex-col gap-4 rounded-lg border bg-muted/20 p-4" data-testid="analysis-insights">
        <h3 className="text-lg font-semibold">🧠 Insights del asistente</h3>
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
