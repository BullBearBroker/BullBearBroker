import { customRender, screen } from "@/tests/utils/renderWithProviders";

import { IndicatorsChart } from "../IndicatorsChart";

jest.mock("recharts", () => {
  const Container = ({ children, "data-testid": testId }: any) => (
    <div data-testid={testId}>{children}</div>
  );

  const Line = ({ dataKey, name }: any) => (
    <div data-testid={`line-${dataKey}`}>{name}</div>
  );

  const Legend = ({ children }: any) => (
    <div data-testid="legend">{children}</div>
  );

  const ReferenceLine = ({ y }: any) => <div data-testid={`reference-${y}`} />;

  const Bar = ({ dataKey, name }: any) => (
    <div data-testid={`bar-${dataKey}`}>{name}</div>
  );

  return {
    ResponsiveContainer: Container,
    LineChart: Container,
    Line,
    XAxis: Container,
    YAxis: Container,
    Tooltip: Container,
    Legend,
    CartesianGrid: Container,
    ReferenceLine,
    BarChart: Container,
    Bar,
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

  it("renderiza el gráfico con variaciones de timeframe y leyendas", () => {
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
        series={{ closes: [145.6, 146.2, 147.5] }}
        insights={insights}
      />
    );

    expect(
      screen.getByRole("heading", { name: "AAPL · 4H" })
    ).toBeInTheDocument();
    expect(screen.getByText("Último cierre: 145.67")).toBeInTheDocument();

    expect(screen.getByTestId("line-close")).toHaveTextContent("Precio");
    expect(screen.getByTestId("line-ema20")).toHaveTextContent("EMA 20");
    expect(screen.getByTestId("line-ema50")).toHaveTextContent("EMA 50");
    expect(screen.getByTestId("line-upper")).toHaveTextContent("BB Upper");
    expect(screen.getAllByTestId("legend").length).toBeGreaterThan(0);

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
    expect(
      screen.getByText("Aún no hay comentarios generados.")
    ).toBeInTheDocument();
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
