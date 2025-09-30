import type { ReactNode } from "react";

import { customRender, screen } from "@/tests/utils/renderWithProviders";

import { IndicatorsChart } from "../IndicatorsChart";

type MockProps = { children?: ReactNode; [key: string]: any };

jest.mock("recharts", () => {
  const Container = ({ children, "data-testid": testId }: MockProps) => (
    <div data-testid={testId}>{children}</div>
  );

  const Element = ({ "data-testid": testId, dataKey, name, children }: MockProps) => (
    <div data-testid={testId ?? dataKey ?? name}>{children}</div>
  );

  return {
    ResponsiveContainer: Container,
    LineChart: Container,
    AreaChart: Container,
    ComposedChart: Container,
    CartesianGrid: Element,
    XAxis: Element,
    YAxis: Element,
    Tooltip: Element,
    Legend: Container,
    ReferenceLine: Element,
    Line: ({ dataKey, name }: MockProps) => (
      <div data-testid={`line-${dataKey}`}>{name}</div>
    ),
    Area: ({ dataKey, name }: MockProps) => (
      <div data-testid={`area-${dataKey}`}>{name}</div>
    ),
    Bar: ({ dataKey, name }: MockProps) => (
      <div data-testid={`bar-${dataKey}`}>{name}</div>
    ),
  };
});

describe("IndicatorsChart", () => {
  const baseIndicators = {
    last_close: 145.67,
    ema: [
      { period: 20, value: 144.32 },
      { period: 50, value: 140.11 },
    ],
    bollinger: {
      upper: 150.2,
      lower: 140.4,
      middle: 145.3,
    },
    rsi: {
      period: 14,
      value: 55.6,
    },
    macd: {
      fast: 12,
      slow: 26,
      signal: 9,
      macd: 1.2,
      hist: 0.3,
    },
    atr: {
      period: 14,
      value: 2.5,
    },
    stochastic_rsi: {
      "%K": 65,
      "%D": 60,
    },
    ichimoku: {
      conversion: 9,
      base: 26,
      span_b: 52,
      tenkan_sen: 150.1,
      kijun_sen: 148.4,
      senkou_span_a: 149.2,
      senkou_span_b: 151.6,
    },
    vwap: {
      value: 147.8,
    },
  };

  it("renderiza el análisis técnico completo cuando hay datos", () => {
    const insights = [
      "Tendencia alcista moderada",
      "Vigilar posibles divergencias",
      "Considerar stop-loss ajustado",
    ].join("\n");

    customRender(
      <IndicatorsChart
        symbol="AAPL"
        interval="4h"
        indicators={baseIndicators}
        series={{
          closes: [145.6, 146.2, 147.5, 148.1, 146.8],
          highs: [146, 147, 148, 149, 147],
          lows: [145, 145.5, 146.2, 147, 146],
          volumes: [1200, 1300, 1250, 1400, 1500],
        }}
        insights={insights}
        history={{
          source: "Binance",
          values: [
            {
              timestamp: "2024-01-01T10:00:00Z",
              open: 145.2,
              high: 146.4,
              low: 144.8,
              close: 145.9,
              volume: 1200,
            },
          ],
        }}
      />
    );

    expect(screen.getByRole("heading", { name: "AAPL · 4H" })).toBeInTheDocument();
    expect(screen.getByText("Último cierre: 145.67")).toBeInTheDocument();
    expect(screen.getByText("Histórico desde: Binance")).toBeInTheDocument();

    expect(screen.getByText("Precio, EMAs y Bandas de Bollinger")).toBeInTheDocument();
    expect(screen.getByTestId("line-close")).toHaveTextContent("Precio");
    expect(screen.getByTestId("line-emaFast")).toHaveTextContent("EMA 20");
    expect(screen.getByTestId("line-emaSlow")).toHaveTextContent("EMA 50");
    expect(screen.getByTestId("line-bollingerUpper")).toHaveTextContent("Bollinger Sup");
    expect(screen.getByTestId("line-bollingerLower")).toHaveTextContent("Bollinger Inf");

    expect(screen.getByText("Índice de Fuerza Relativa (RSI)")).toBeInTheDocument();
    expect(screen.getByTestId("line-value")).toHaveTextContent("RSI 14");

    expect(screen.getByText("Average True Range (ATR)")).toBeInTheDocument();
    expect(screen.getByTestId("area-value")).toHaveTextContent("ATR 14");

    expect(screen.getByText("Ichimoku")).toBeInTheDocument();
    expect(screen.getByTestId("line-tenkan")).toHaveTextContent("Tenkan");
    expect(screen.getByTestId("line-kijun")).toHaveTextContent("Kijun");

    expect(screen.getByRole("heading", { name: "MACD" })).toBeInTheDocument();
    expect(screen.getByTestId("line-macd")).toHaveTextContent("MACD");
    expect(screen.getByTestId("bar-histogram")).toHaveTextContent("Histograma");

    expect(screen.getByText("🧠 Insights del asistente")).toBeInTheDocument();
    expect(screen.getByText("Tendencia alcista moderada")).toBeInTheDocument();
    expect(screen.getByText("Vigilar posibles divergencias")).toBeInTheDocument();
    expect(screen.getByText("Considerar stop-loss ajustado")).toBeInTheDocument();
  });

  it("maneja datos incompletos mostrando valores por defecto", () => {
    customRender(
      <IndicatorsChart
        symbol="ETH"
        interval="1d"
        indicators={{ last_close: 2000 }}
        insights={null}
      />
    );

    expect(screen.getByRole("heading", { name: "ETH · 1D" })).toBeInTheDocument();
    expect(screen.getByText("Último cierre: 2000")).toBeInTheDocument();
    expect(screen.getByText("Aún no hay comentarios generados.")).toBeInTheDocument();
  });

  it("muestra mensajes de carga y error en el panel de insights", () => {
    const { rerender } = customRender(
      <IndicatorsChart
        symbol="AAPL"
        interval="1d"
        indicators={baseIndicators}
        loading
      />
    );

    expect(screen.getByText("Analizando indicadores...")).toBeInTheDocument();

    rerender(
      <IndicatorsChart
        symbol="AAPL"
        interval="1d"
        indicators={baseIndicators}
        error="No se pudo obtener datos"
      />
    );

    expect(screen.getByText("No se pudo obtener datos")).toBeInTheDocument();
  });
});
