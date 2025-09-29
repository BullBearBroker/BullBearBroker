import { render, screen } from "@testing-library/react";

import { IndicatorsChart } from "../IndicatorsChart";

jest.mock("recharts", () => {
  const Passthrough = ({ children }: any) => <div>{children}</div>;

  return {
    ResponsiveContainer: Passthrough,
    LineChart: Passthrough,
    Line: Passthrough,
    XAxis: Passthrough,
    YAxis: Passthrough,
    Tooltip: Passthrough,
    Legend: Passthrough,
    CartesianGrid: Passthrough,
    ReferenceLine: Passthrough,
    BarChart: Passthrough,
    Bar: Passthrough,
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
      macd: 1.2,
      signal: 0.9,
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
      tenkan_sen: 150.1,
      kijun_sen: 148.4,
      senkou_span_a: 149.2,
      senkou_span_b: 151.6,
    },
    vwap: {
      value: 147.8,
    },
  };

  it("renders the header, indicator summaries, and insight list", () => {
    const insights = [
      "Tendencia alcista moderada",
      "Vigilar posibles divergencias",
      "Considerar stop-loss ajustado",
    ].join("\n");

    render(
      <IndicatorsChart
        symbol="AAPL"
        interval="1d"
        indicators={baseIndicators}
        series={{ closes: [145.6, 146.2, 147.5] }}
        insights={insights}
      />
    );

    expect(
      screen.getByRole("heading", { name: "AAPL · 1D" })
    ).toBeInTheDocument();
    expect(screen.getByText("Último cierre: 145.67")).toBeInTheDocument();

    expect(screen.getByText("ATR (Periodo 14)")).toBeInTheDocument();
    expect(screen.getByText("2.5")).toBeInTheDocument();
    expect(screen.getByText("Stochastic RSI")).toBeInTheDocument();
    expect(screen.getByText("%K 65 · %D 60")).toBeInTheDocument();

    expect(screen.getByText("🧠 Insights de la IA")).toBeInTheDocument();
    expect(
      screen.getByText("Tendencia alcista moderada")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Vigilar posibles divergencias")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Considerar stop-loss ajustado")
    ).toBeInTheDocument();
  });

  it("shows fallback messages when loading or error states are provided", () => {
    const { rerender } = render(
      <IndicatorsChart
        symbol="AAPL"
        interval="1d"
        indicators={baseIndicators}
        loading
      />
    );

    expect(
      screen.getByText("Analizando indicadores...")
    ).toBeInTheDocument();

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
