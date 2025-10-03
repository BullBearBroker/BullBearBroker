import { act, customRender, screen, waitFor, within } from "@/tests/utils/renderWithProviders";
import userEvent from "@testing-library/user-event";
import useSWR from "swr";

import { PortfolioPanel } from "../PortfolioPanel";
import {
  createPortfolioItem,
  deletePortfolioItem,
  exportPortfolioCsv,
  importPortfolioCsv,
  listPortfolio,
} from "@/lib/api";
import { getFeatureFlag } from "@/lib/featureFlags";

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
  exportPortfolioCsv: jest.fn(),
  importPortfolioCsv: jest.fn(),
  listPortfolio: jest.fn(),
}));

jest.mock("@/lib/featureFlags", () => ({
  getFeatureFlag: jest.fn(),
}));

const mockedUseSWR = useSWR as jest.MockedFunction<typeof useSWR>;
const mockedCreatePortfolioItem =
  createPortfolioItem as jest.MockedFunction<typeof createPortfolioItem>;
const mockedDeletePortfolioItem =
  deletePortfolioItem as jest.MockedFunction<typeof deletePortfolioItem>;
const mockedExportPortfolioCsv =
  exportPortfolioCsv as jest.MockedFunction<typeof exportPortfolioCsv>;
const mockedImportPortfolioCsv =
  importPortfolioCsv as jest.MockedFunction<typeof importPortfolioCsv>;
const mockedListPortfolio = listPortfolio as jest.MockedFunction<typeof listPortfolio>;
const mockedGetFeatureFlag = getFeatureFlag as jest.MockedFunction<typeof getFeatureFlag>;

describe("PortfolioPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseSWR.mockReturnValue({
      data: undefined,
      error: undefined,
      mutate: jest.fn().mockResolvedValue(undefined),
      isLoading: false,
    } as any);
    mockedGetFeatureFlag.mockReturnValue(false);
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
    expect(screen.getByTestId("portfolio-loading")).toBeInTheDocument();
    expect(screen.getAllByTestId("skeleton")).toHaveLength(3);

    rerender(<PortfolioPanel token="demo" />);
    expect(screen.getByText(/Error al cargar el portafolio/i)).toBeInTheDocument();
  });

  it("muestra un estado vacío cuando no existen elementos", () => {
    mockedUseSWR.mockReturnValue({
      data: { total_value: 0, items: [] },
      error: undefined,
      mutate: jest.fn(),
      isLoading: false,
    } as any);

    customRender(<PortfolioPanel token="demo" />);

    const emptyState = screen.getByTestId("empty-state");
    expect(within(emptyState).getByText(/tu portafolio está vacío/i)).toBeInTheDocument();
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

  it("muestra acciones de CSV cuando la bandera está activa", () => {
    mockedGetFeatureFlag.mockReturnValue(true);
    mockedUseSWR.mockReturnValue({
      data: { total_value: 0, items: [] },
      error: undefined,
      mutate: jest.fn(),
      isLoading: false,
    } as any);

    customRender(<PortfolioPanel token="secure" />);

    expect(screen.getByRole("button", { name: /exportar csv/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /importar csv/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /plantilla/i })).toBeInTheDocument();
  });

  it("descarga el CSV al exportar", async () => {
    mockedGetFeatureFlag.mockReturnValue(true);
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue({
      data: { total_value: 0, items: [] },
      error: undefined,
      mutate,
      isLoading: false,
    } as any);

    mockedExportPortfolioCsv.mockResolvedValue("symbol,amount\nAAPL,1\n");

    const anchor = document.createElement("a");
    const clickSpy = jest.spyOn(anchor, "click").mockImplementation(() => {});
    const createSpy = jest.spyOn(document, "createElement").mockReturnValue(anchor as any);
    const appendSpy = jest.spyOn(document.body, "appendChild");
    const removeSpy = jest.spyOn(document.body, "removeChild");
    const urlCreateSpy = jest
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:mock-url");
    const urlRevokeSpy = jest.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    const user = userEvent.setup();
    customRender(<PortfolioPanel token="secure" />);

    try {
      await act(async () => {
        await user.click(screen.getByRole("button", { name: /exportar csv/i }));
      });
    } finally {
      createSpy.mockRestore();
      appendSpy.mockRestore();
      removeSpy.mockRestore();
      urlCreateSpy.mockRestore();
      urlRevokeSpy.mockRestore();
      clickSpy.mockRestore();
    }

    expect(mockedExportPortfolioCsv).toHaveBeenCalledWith("secure");
    expect(clickSpy).toHaveBeenCalled();
    expect(appendSpy).toHaveBeenCalled();
    expect(removeSpy).toHaveBeenCalled();
    expect(screen.getByText(/Exportación completada/i)).toBeInTheDocument();
  });

  it("procesa el CSV importado y muestra errores", async () => {
    mockedGetFeatureFlag.mockReturnValue(true);
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue({
      data: { total_value: 0, items: [] },
      error: undefined,
      mutate,
      isLoading: false,
    } as any);

    mockedImportPortfolioCsv.mockResolvedValue({
      created: 1,
      items: [],
      errors: [{ row: 3, message: "La cantidad debe ser numérica" }],
    });

    const user = userEvent.setup();
    const { container } = customRender(<PortfolioPanel token="secure" />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["symbol,amount\nAAPL,1\n"], "portfolio.csv", {
      type: "text/csv",
    });

    await act(async () => {
      await user.upload(input, file);
    });

    await waitFor(() => {
      expect(mockedImportPortfolioCsv).toHaveBeenCalledWith("secure", file);
      expect(mutate).toHaveBeenCalled();
    });

    expect(screen.getByText(/Se importaron 1 activos/)).toBeInTheDocument();
    expect(screen.getByText(/Fila 3: La cantidad debe ser numérica/)).toBeInTheDocument();
  });
});
