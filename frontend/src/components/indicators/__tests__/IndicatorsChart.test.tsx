import { act, render, screen } from "@testing-library/react";
import { IndicatorsChart } from "../IndicatorsChart";

jest.mock("recharts", () => {
  const MockLeaf = ({ "data-testid": dataTestId }: any) => (
    <div data-testid={dataTestId ?? "recharts-node"} />
  );

  return {
    ResponsiveContainer: ({ children }: any) => (
      <div data-testid="responsive-container">{children}</div>
    ),
    LineChart: ({ children }: any) => (
      <div data-testid="line-chart">{children}</div>
    ),
    CartesianGrid: MockLeaf,
    XAxis: MockLeaf,
    YAxis: MockLeaf,
    Tooltip: MockLeaf,
    Legend: MockLeaf,
    Line: MockLeaf,
    ReferenceLine: MockLeaf,
    BarChart: ({ children }: any) => (
      <div data-testid="bar-chart">{children}</div>
    ),
    Bar: MockLeaf,
  };
});

describe("IndicatorsChart", () => {
  it("muestra encabezado, secciones condicionales y textos de insights", async () => {
    const indicators = {
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

    const series = {
      closes: [145.6, 146.2, 147.5],
    };

    const insights = "Tendencia alcista moderada\nVigilar posibles divergencias";

    await act(async () => {
      render(
        <IndicatorsChart
          symbol="AAPL"
          interval="1d"
          indicators={indicators}
          series={series}
          insights={insights}
        />
      );
    });

    expect(
      screen.getByRole("heading", { name: "AAPL · 1D" })
    ).toBeInTheDocument();
    expect(
      screen.getByText("Último cierre: 145.67")
    ).toBeInTheDocument();

    expect(screen.getByText("RSI (Periodo 14)")).toBeInTheDocument();
    expect(screen.getByText("MACD")).toBeInTheDocument();
    expect(screen.getByText("ATR (Periodo 14)")).toBeInTheDocument();
    expect(screen.getByText("Stochastic RSI")).toBeInTheDocument();
    expect(screen.getByText("Ichimoku")).toBeInTheDocument();
    expect(screen.getByText("VWAP")).toBeInTheDocument();

    expect(screen.getByText("🧠 Insights de la IA")).toBeInTheDocument();
    expect(
      screen.getByText("Tendencia alcista moderada")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Vigilar posibles divergencias")
    ).toBeInTheDocument();
  });
});
