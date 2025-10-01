import { act, customRender, screen, waitFor } from "@/tests/utils/renderWithProviders";
import userEvent from "@testing-library/user-event";
import useSWR from "swr";

import {
  PortfolioPanel
} from "../PortfolioPanel";
import {
  createPortfolioItem,
  deletePortfolioItem,
  listPortfolio,
} from "@/lib/api";

jest.mock("swr", () => {
  const actual = jest.requireActual("swr");
  return {
    __esModule: true,
    ...actual,
    default: jest.fn(),
    SWRConfig: actual.SWRConfig,
  };
});

jest.mock("@/lib/api", () => ({
  createPortfolioItem: jest.fn(),
  deletePortfolioItem: jest.fn(),
  listPortfolio: jest.fn(),
}));

const mockedUseSWR = useSWR as jest.MockedFunction<typeof useSWR>;
const mockedCreatePortfolioItem =
  createPortfolioItem as jest.MockedFunction<typeof createPortfolioItem>;
const mockedDeletePortfolioItem =
  deletePortfolioItem as jest.MockedFunction<typeof deletePortfolioItem>;
const mockedListPortfolio = listPortfolio as jest.MockedFunction<typeof listPortfolio>;

describe("PortfolioPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseSWR.mockReturnValue({
      data: undefined,
      error: undefined,
      mutate: jest.fn().mockResolvedValue(undefined),
      isLoading: false,
    } as any);
  });

  it("no consulta el portafolio cuando falta el token", () => {
    customRender(<PortfolioPanel token={undefined} />);

    expect(mockedUseSWR).toHaveBeenCalledWith(null, expect.any(Function));
    expect(mockedListPortfolio).not.toHaveBeenCalled();
  });

  it("renderiza el total y los activos cuando hay datos", () => {
    mockedUseSWR.mockReturnValue({
      data: {
        total_value: 26800,
        items: [
          { id: "1", symbol: "BTCUSDT", amount: 0.5, price: 50000, value: 25000 },
          { id: "2", symbol: "AAPL", amount: 10, price: 180, value: 1800 },
        ],
      },
      error: undefined,
      mutate: jest.fn(),
      isLoading: false,
    } as any);

    customRender(<PortfolioPanel token="demo" />);

    expect(screen.getByText(/Total:\s+\$26,800\.00/)).toBeInTheDocument();
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText(/Precio:\s+\$50,000\.00/)).toBeInTheDocument();
    expect(screen.getByText("$1,800.00")).toBeInTheDocument();
  });

  it("muestra mensajes de carga y error según corresponda", () => {
    mockedUseSWR
      .mockReturnValueOnce({
        data: undefined,
        error: undefined,
        mutate: jest.fn(),
        isLoading: true,
      } as any)
      .mockReturnValueOnce({
        data: undefined,
        error: new Error("Fallo"),
        mutate: jest.fn(),
        isLoading: false,
      } as any);

    const { rerender } = customRender(<PortfolioPanel token="demo" />);
    expect(screen.getByText(/Cargando portafolio/i)).toBeInTheDocument();

    rerender(<PortfolioPanel token="demo" />);
    expect(screen.getByText(/Error al cargar el portafolio/i)).toBeInTheDocument();
  });

  it("permite agregar un nuevo activo", async () => {
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue({
      data: {
        total_value: 0,
        items: [],
      },
      error: undefined,
      mutate,
      isLoading: false,
    } as any);

    mockedCreatePortfolioItem.mockResolvedValue({
      id: "1",
      symbol: "BTCUSDT",
      amount: 0.5,
    } as any);

    const user = userEvent.setup();
    customRender(<PortfolioPanel token="secure" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL, EURUSD)"),
        " btcusdt "
      );
      await user.type(screen.getByPlaceholderText("Cantidad"), "0.5");
      await user.click(screen.getByRole("button", { name: /agregar activo/i }));
    });

    await waitFor(() => {
      expect(mockedCreatePortfolioItem).toHaveBeenCalledWith("secure", {
        symbol: "BTCUSDT",
        amount: 0.5,
      });
    });

    await waitFor(() => {
      expect(mutate).toHaveBeenCalled();
    });
  });

  it("muestra un mensaje de error cuando crear el activo falla", async () => {
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue({
      data: { total_value: 0, items: [] },
      error: undefined,
      mutate,
      isLoading: false,
    } as any);

    mockedCreatePortfolioItem.mockRejectedValueOnce(new Error("API down"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();

    try {
      customRender(<PortfolioPanel token="secure" />);

      await act(async () => {
        await user.type(
          screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL, EURUSD)"),
          "AAPL"
        );
        await user.type(screen.getByPlaceholderText("Cantidad"), "2");
        await user.click(screen.getByRole("button", { name: /agregar activo/i }));
      });

      expect(await screen.findByText("API down")).toBeInTheDocument();
    } finally {
      consoleSpy.mockRestore();
    }
  });

  it("muestra un error de validación si la cantidad es inválida", async () => {
    const user = userEvent.setup();
    customRender(<PortfolioPanel token="secure" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL, EURUSD)"),
        "AAPL"
      );
      await user.type(screen.getByPlaceholderText("Cantidad"), "0");
      await user.click(screen.getByRole("button", { name: /agregar activo/i }));
    });

    expect(
      screen.getByText("La cantidad debe ser mayor que cero.")
    ).toBeInTheDocument();
    expect(mockedCreatePortfolioItem).not.toHaveBeenCalled();
  });

  it("elimina un activo y actualiza el portafolio", async () => {
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue({
      data: {
        total_value: 1000,
        items: [{ id: "1", symbol: "AAPL", amount: 10, price: 180, value: 1800 }],
      },
      error: undefined,
      mutate,
      isLoading: false,
    } as any);

    mockedDeletePortfolioItem.mockResolvedValue(undefined);

    const user = userEvent.setup();
    customRender(<PortfolioPanel token="secure" />);

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /eliminar aapl/i }));
    });

    await waitFor(() => {
      expect(mockedDeletePortfolioItem).toHaveBeenCalledWith("secure", "1");
    });

    await waitFor(() => {
      expect(mutate).toHaveBeenCalled();
    });
  });

  it("muestra un mensaje cuando faltan precios para un activo", () => {
    mockedUseSWR.mockReturnValue({
      data: {
        total_value: 0,
        items: [{ id: "x", symbol: "EURUSD", amount: 1000, price: null, value: null }],
      },
      error: undefined,
      mutate: jest.fn(),
      isLoading: false,
    } as any);

    customRender(<PortfolioPanel token="demo" />);

    expect(screen.getByText(/EURUSD/)).toBeInTheDocument();
    expect(screen.getByText(/Precio:\s+Sin datos/i)).toBeInTheDocument();
    expect(screen.getByText(/^\s*-\s*$/)).toBeInTheDocument();
  });

  it("informa un error cuando eliminar un activo falla", async () => {
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue({
      data: {
        total_value: 1000,
        items: [{ id: "1", symbol: "AAPL", amount: 10, price: 180, value: 1800 }],
      },
      error: undefined,
      mutate,
      isLoading: false,
    } as any);

    mockedDeletePortfolioItem.mockRejectedValueOnce(new Error("No se pudo"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();

    try {
      customRender(<PortfolioPanel token="secure" />);

      await act(async () => {
        await user.click(screen.getByRole("button", { name: /eliminar aapl/i }));
      });

      expect(await screen.findByText("No se pudo")).toBeInTheDocument();
    } finally {
      consoleSpy.mockRestore();
    }
  });
});
