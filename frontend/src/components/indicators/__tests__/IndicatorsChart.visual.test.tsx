import { act, customRender, screen } from "@/tests/utils/renderWithProviders";

import { IndicatorsChart } from "../IndicatorsChart";

// QA: establecemos mocks mínimos de navegador para que Recharts renderice gradientes.
class ResizeObserverMock {
  callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  observe() {
    this.callback([{ contentRect: { width: 420, height: 300 } } as ResizeObserverEntry], this as any);
  }

  unobserve() {}

  disconnect() {}
}

describe("IndicatorsChart visual", () => {
  let originalResizeObserver: typeof ResizeObserver | undefined;
  let originalLinearGradient: typeof window.SVGLinearGradientElement | undefined;
  let originalStopElement: typeof window.SVGStopElement | undefined;
  let resizeInstance: ResizeObserverMock | undefined;

  beforeEach(() => {
    originalResizeObserver = window.ResizeObserver;
    originalLinearGradient = window.SVGLinearGradientElement;
    originalStopElement = window.SVGStopElement;

    (window as any).SVGLinearGradientElement = function SVGLinearGradientElement() {} as any;
    (window as any).SVGStopElement = function SVGStopElement() {} as any;

    window.ResizeObserver = class extends ResizeObserverMock {
      constructor(callback: ResizeObserverCallback) {
        super(callback);
        resizeInstance = this;
      }
    } as typeof ResizeObserver;
  });

  afterEach(() => {
    window.ResizeObserver = originalResizeObserver as typeof ResizeObserver;
    (window as any).SVGLinearGradientElement = originalLinearGradient;
    (window as any).SVGStopElement = originalStopElement;
    resizeInstance = undefined;
  });

  it("dibuja el gradiente del ATR y reacciona a cambios de tamaño y props", async () => {
    const baseProps = {
      symbol: "AAPL",
      interval: "1h",
      indicators: {
        last_close: 150,
        atr: { period: 14, value: 1.5 },
        ema: [
          { period: 12, value: 151 },
          { period: 26, value: 149 },
        ],
        bollinger: { period: 20, mult: 2 },
        rsi: { period: 14, value: 55 },
        macd: { fast: 12, slow: 26, signal: 9 },
      },
      series: {
        closes: [150, 151, 149, 152],
        highs: [151, 152, 150, 153],
        lows: [149, 148, 147, 151],
        volumes: [120, 132, 140, 150],
      },
    };

    const { container, rerender } = customRender(
      <div style={{ width: 480, height: 320 }}>
        <IndicatorsChart {...baseProps} />
      </div>
    );

    await act(async () => {
      resizeInstance?.observe();
    });

    expect(container.querySelector("linearGradient#atrGradient")).not.toBeNull();

    rerender(
      <div style={{ width: 360, height: 240 }}>
        <IndicatorsChart
          {...baseProps}
          interval="4h"
          indicators={{
            ...baseProps.indicators,
            atr: { period: 10, value: 1.2 },
          }}
        />
      </div>
    );

    await act(async () => {
      resizeInstance?.callback(
        [{ contentRect: { width: 360, height: 240 } } as ResizeObserverEntry],
        resizeInstance as unknown as ResizeObserver
      );
    });

    expect(screen.getByRole("heading", { name: "AAPL · 4H" })).toBeInTheDocument();
    expect(container.querySelector("linearGradient#atrGradient")).not.toBeNull();
  });
});
