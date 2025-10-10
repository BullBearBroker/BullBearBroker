import { act, customRender, screen, waitFor } from "@/tests/utils/renderWithProviders";
import userEvent from "@testing-library/user-event";
import useSWR, { type SWRResponse } from "swr";

import {
  createAlert,
  updateAlert,
  sendAlertNotification,
  suggestAlertCondition,
  deleteAlert,
  listAlerts,
} from "@/lib/api";
import { AlertsPanel } from "../alerts-panel";
import { useAlertsWebSocket } from "@/hooks/useAlertsWebSocket";

const mockedUseAlertsWebSocket = useAlertsWebSocket as jest.MockedFunction<
  typeof useAlertsWebSocket
>;

jest.mock("swr", () => {
  const actual = jest.requireActual("swr");
  return {
    __esModule: true,
    ...actual,
    default: jest.fn(),
    SWRConfig: actual.SWRConfig,
  };
});

jest.mock("@/hooks/useAlertsWebSocket", () => ({
  __esModule: true,
  useAlertsWebSocket: jest.fn(() => ({
    status: "closed",
    lastMessage: null,
    error: null,
    reconnect: jest.fn(),
    disconnect: jest.fn(),
  })),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  createAlert: jest.fn(),
  updateAlert: jest.fn(),
  deleteAlert: jest.fn(),
  listAlerts: jest.fn(),
  sendAlertNotification: jest.fn(),
  suggestAlertCondition: jest.fn(),
}));

// ✅ Mockeos con tipado para evitar errores en TS
const mockedUseSWR = useSWR as jest.MockedFunction<typeof useSWR>;
const mockedCreateAlert = createAlert as jest.MockedFunction<typeof createAlert>;
const mockedUpdateAlert = updateAlert as jest.MockedFunction<typeof updateAlert>;
const mockedSendAlertNotification = sendAlertNotification as jest.MockedFunction<
  typeof sendAlertNotification
>;
const mockedSuggestAlertCondition = suggestAlertCondition as jest.MockedFunction<
  typeof suggestAlertCondition
>;
const mockedDeleteAlert = deleteAlert as jest.MockedFunction<typeof deleteAlert>;
const mockedListAlerts = listAlerts as jest.MockedFunction<typeof listAlerts>;

const createSWRMock = (overrides: Partial<SWRResponse<unknown>> = {}): SWRResponse<unknown> =>
  ({
    data: undefined,
    error: undefined,
    mutate: jest.fn().mockResolvedValue(undefined),
    isLoading: false,
    isValidating: false,
    ...overrides,
  }) as SWRResponse<unknown>; // CODEx: helper para incluir campos obligatorios de SWR

describe("AlertsPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseAlertsWebSocket.mockImplementation(() => ({
      status: "closed",
      lastMessage: null,
      error: null,
      reconnect: jest.fn(),
      disconnect: jest.fn(),
    }));
    mockedUseSWR.mockReturnValue(createSWRMock({ data: [] }));
  });

  afterEach(() => {
    mockedUseAlertsWebSocket.mockReset();
  });

  it("no consulta alertas cuando falta el token", () => {
    customRender(<AlertsPanel token={undefined} />);

    expect(mockedUseSWR).toHaveBeenCalledWith(null, expect.any(Function));
    expect(mockedListAlerts).not.toHaveBeenCalled();
  });

  it("creates an alert with the expected payload", async () => {
    const user = userEvent.setup();
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue(createSWRMock({ data: [], mutate }));

    mockedCreateAlert.mockResolvedValue({
      id: "1",
      title: "Comprar BTC",
      asset: "BTCUSDT",
      condition: "Precio cruza los 50k",
      value: 50000,
      active: true,
    });

    customRender(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(screen.getByPlaceholderText("Título de la alerta"), "  Comprar BTC ");
      await user.type(screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL)"), "btcusdt");
      await user.type(
        screen.getByPlaceholderText("Condición (ej. BTC > 50,000 USD)"),
        "Precio cruza los 50k",
      );
      await user.type(screen.getByPlaceholderText("Valor (ej. 30)"), "50000");
    });

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /crear alerta/i }));
    });

    await waitFor(() => {
      expect(mockedCreateAlert).toHaveBeenCalledWith(
        "secure-token",
        expect.objectContaining({
          title: "Comprar BTC",
          asset: "BTCUSDT",
          condition: "Precio cruza los 50k",
          value: 50000,
          active: true,
        }),
      );
    });

    expect(mutate).toHaveBeenCalled();
  });

  it("shows a validation error when title is missing", async () => {
    const user = userEvent.setup();
    customRender(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL)"), "ETHUSDT");
      await user.type(
        screen.getByPlaceholderText("Condición (ej. BTC > 50,000 USD)"),
        "ETH supera los 3000",
      );
      await user.type(screen.getByPlaceholderText("Valor (ej. 30)"), "3000");
      await user.click(screen.getByRole("button", { name: /crear alerta/i }));
    });

    expect(await screen.findByText("Debes asignar un título a la alerta.")).toBeInTheDocument();
    expect(mockedCreateAlert).not.toHaveBeenCalled();
  });

  it("toggles an alert to inactive", async () => {
    const user = userEvent.setup();
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue(
      createSWRMock({
        data: [
          {
            id: "alert-1",
            title: "Cruz dorada",
            asset: "BTCUSDT",
            condition: "Cruce EMA 50/200",
            value: 50000,
            active: true,
          },
        ],
        mutate,
      }),
    );

    mockedUpdateAlert.mockResolvedValue({
      id: "alert-1",
      title: "Cruz dorada",
      asset: "BTCUSDT",
      condition: "Cruce EMA 50/200",
      value: 50000,
      active: false,
    });

    customRender(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /pausar/i }));
    });

    await waitFor(() => {
      expect(mockedUpdateAlert).toHaveBeenCalledWith("secure-token", "alert-1", {
        active: false,
      });
    });

    expect(mutate).toHaveBeenCalled();
  });

  it("prefills a quick condition only when the textarea is empty", async () => {
    const user = userEvent.setup();
    customRender(<AlertsPanel token="demo-token" />);

    const textarea = screen.getByPlaceholderText(/condición/i) as HTMLTextAreaElement;
    const helperButton = screen.getByRole("button", { name: /menor que/i });

    expect(textarea).toHaveValue("");
    expect(helperButton).toBeEnabled();

    await act(async () => {
      await user.click(helperButton);
    });

    expect(textarea).toHaveValue("<");
    expect(helperButton).toBeDisabled();
  });

  it("keeps custom expressions in the textarea as the source of truth", async () => {
    const user = userEvent.setup();
    customRender(<AlertsPanel token="demo-token" />);

    const textarea = screen.getByPlaceholderText(/condición/i) as HTMLTextAreaElement;
    const helperButton = screen.getByRole("button", { name: /menor que/i });

    await act(async () => {
      await user.type(textarea, "Precio cruza 30k");
    });

    expect(textarea).toHaveValue("Precio cruza 30k");
    expect(helperButton).toBeDisabled();

    await act(async () => {
      await user.click(helperButton);
    });

    expect(textarea).toHaveValue("Precio cruza 30k");

    await act(async () => {
      await user.clear(textarea);
    });

    expect(textarea).toHaveValue("");
    expect(helperButton).toBeEnabled();

    await act(async () => {
      await user.click(helperButton);
    });

    expect(textarea).toHaveValue("<");
  });

  it("muestra el estado de carga cuando SWR está cargando", () => {
    mockedUseSWR.mockReturnValue(createSWRMock({ isLoading: true }));

    customRender(<AlertsPanel token="token" />);

    expect(screen.getByText("Cargando alertas...")).toBeInTheDocument();
  });

  it("muestra un mensaje de error cuando la carga falla", () => {
    mockedUseSWR.mockReturnValue(
      createSWRMock({
        error: new Error("Fallo en SWR"),
      }),
    );

    customRender(<AlertsPanel token="token" />);

    expect(screen.getByText(/fallo en swr/i)).toBeInTheDocument();
  });

  it("indica cuando no hay alertas disponibles", () => {
    mockedUseSWR.mockReturnValue(createSWRMock({ data: [] }));

    customRender(<AlertsPanel token="token" />);

    expect(
      screen.getByText("Aún no tienes alertas. Crea una para recibir notificaciones."),
    ).toBeInTheDocument();
  });

  it("renderiza la lista con múltiples alertas", () => {
    mockedUseSWR.mockReturnValue(
      createSWRMock({
        data: [
          {
            id: "a-1",
            title: "Alerta 1",
            asset: "BTCUSDT",
            condition: "Precio > 50k",
            value: 50000,
            active: true,
          },
          {
            id: "a-2",
            title: "Alerta 2",
            asset: "ETHUSDT",
            condition: "Precio < 2k",
            value: 2000,
            active: false,
          },
        ],
      }),
    );

    customRender(<AlertsPanel token="token" />);

    expect(screen.getByText("Alerta 1")).toBeInTheDocument();
    expect(screen.getByText("Alerta 2")).toBeInTheDocument();
    expect(screen.getAllByText("Activa")).toHaveLength(1);
    expect(screen.getAllByText("Pausada")).toHaveLength(1);
  });

  it("elimina una alerta y refresca la lista", async () => {
    const user = userEvent.setup();
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue(
      createSWRMock({
        data: [
          {
            id: "alert-1",
            title: "Alerta 1",
            asset: "BTCUSDT",
            condition: "Precio > 50k",
            value: 50000,
            active: true,
          },
        ],
        mutate,
      }),
    );
    mockedDeleteAlert.mockResolvedValueOnce(undefined as never);

    customRender(<AlertsPanel token="token" />);

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /eliminar alerta/i }));
    });

    await waitFor(() => {
      expect(mockedDeleteAlert).toHaveBeenCalledWith("token", "alert-1");
    });

    expect(mutate).toHaveBeenCalled();
  });

  it("obtiene una sugerencia de condición y muestra la nota", async () => {
    mockedSuggestAlertCondition.mockResolvedValue({
      suggestion: "BTC > 45000",
      notes: "Basado en indicadores",
    });
    const user = userEvent.setup();

    customRender(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL)"), "btc");
      await user.click(screen.getByRole("button", { name: /sugerir alerta/i }));
    });

    expect(mockedSuggestAlertCondition).toHaveBeenCalledWith(
      "secure-token",
      expect.objectContaining({ asset: "btc", interval: "1h" }),
    );
    expect(screen.getByPlaceholderText(/condición/i)).toHaveValue("BTC > 45000");
    expect(screen.getByText("Basado en indicadores")).toBeInTheDocument();
  });

  it("muestra el estado y mensaje del websocket cuando no hay alertas", () => {
    mockedUseAlertsWebSocket.mockImplementation(() => ({
      status: "open",
      lastMessage: null,
      error: null,
      reconnect: jest.fn(),
      disconnect: jest.fn(),
    }));

    customRender(<AlertsPanel token="token" />);

    expect(screen.getByText("Conectado")).toBeInTheDocument();
    expect(screen.getByText("Aún no hay alertas en vivo.")).toBeInTheDocument();
  });

  it("muestra mensajes del sistema y errores del websocket", () => {
    let capturedCallbacks: Parameters<typeof mockedUseAlertsWebSocket>[0] | undefined;
    mockedUseAlertsWebSocket.mockImplementation((options) => {
      capturedCallbacks = options;
      return {
        status: "error",
        lastMessage: null,
        error: "Canal inestable",
        reconnect: jest.fn(),
        disconnect: jest.fn(),
      };
    });

    customRender(<AlertsPanel token="token" />);

    act(() => {
      capturedCallbacks?.onSystemMessage?.({
        type: "system",
        message: "Reconectando",
      });
    });

    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.getByText("Reconectando")).toBeInTheDocument();
    expect(screen.getByText("Canal inestable")).toBeInTheDocument();
  });

  it("renderiza alertas en vivo recibidas por websocket", () => {
    const fakeNow = 1700000000000;
    const dateSpy = jest.spyOn(Date, "now").mockReturnValue(fakeNow);
    let capturedCallbacks: Parameters<typeof mockedUseAlertsWebSocket>[0] | undefined;
    mockedUseAlertsWebSocket.mockImplementation((options) => {
      capturedCallbacks = options;
      return {
        status: "open",
        lastMessage: null,
        error: null,
        reconnect: jest.fn(),
        disconnect: jest.fn(),
      };
    });

    try {
      customRender(<AlertsPanel token="token" />);

      act(() => {
        capturedCallbacks?.onAlert?.({
          type: "alert",
          message: "Precio objetivo alcanzado",
          symbol: "ETHUSDT",
          price: "2345.5",
          target: 2500,
        });
      });

      expect(screen.getByText(/ETHUSDT · Precio objetivo alcanzado/)).toBeInTheDocument();
      expect(screen.getByText(/Precio 2345.50 · Objetivo 2500.00/)).toBeInTheDocument();
    } finally {
      dateSpy.mockRestore();
    }
  });

  it("usa valores por defecto cuando el evento carece de información", () => {
    let capturedCallbacks: Parameters<typeof mockedUseAlertsWebSocket>[0] | undefined;
    mockedUseAlertsWebSocket.mockImplementation((options) => {
      capturedCallbacks = options;
      return {
        status: "open",
        lastMessage: null,
        error: null,
        reconnect: jest.fn(),
        disconnect: jest.fn(),
      };
    });

    customRender(<AlertsPanel token="token" />);

    act(() => {
      capturedCallbacks?.onAlert?.({
        type: "alert",
        message: 123,
        price: null,
        target: undefined,
      } as any);
    });

    expect(screen.getByText(/Alerta · Se recibió una alerta en vivo/)).toBeInTheDocument();
  });

  it("muestra un error si se solicita sugerencia sin activo", async () => {
    const user = userEvent.setup();
    customRender(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /sugerir alerta/i }));
    });

    expect(
      screen.getByText("Completa el campo de activo antes de pedir sugerencias."),
    ).toBeInTheDocument();
    expect(mockedSuggestAlertCondition).not.toHaveBeenCalled();
  });

  it("envía una notificación manual y muestra el resumen", async () => {
    mockedSendAlertNotification.mockResolvedValue({
      telegram: { status: "sent", target: "123" },
      discord: { status: "queued", target: "999" },
    });
    const user = userEvent.setup();

    customRender(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(screen.getByPlaceholderText("Mensaje para Telegram/Discord"), "Comprar BTC");
      await user.type(screen.getByPlaceholderText("Chat ID de Telegram (opcional)"), "123");
      await user.type(screen.getByPlaceholderText("Canal de Discord (opcional)"), "999");
      await user.click(screen.getByRole("button", { name: /enviar notificación/i }));
    });

    await waitFor(() => {
      expect(mockedSendAlertNotification).toHaveBeenCalledWith(
        "secure-token",
        expect.objectContaining({ message: "Comprar BTC" }),
      );
      expect(
        screen.getByText(/Notificación enviada \(telegram: sent \| discord: queued\)/i),
      ).toBeInTheDocument();
    });
  });

  it("mapea estados visuales para conexiones no abiertas", () => {
    mockedUseAlertsWebSocket.mockImplementation(() => ({
      status: "connecting",
      lastMessage: null,
      error: null,
      reconnect: jest.fn(),
      disconnect: jest.fn(),
    }));

    customRender(<AlertsPanel token="token" />);

    expect(screen.getByText("Conectando...")).toBeInTheDocument();
    expect(screen.getByText("Conectando al canal en vivo...")).toBeInTheDocument();
  });

  it("muestra el estado inactivo cuando el websocket no ha iniciado", () => {
    mockedUseAlertsWebSocket.mockImplementation(() => ({
      status: "idle",
      lastMessage: null,
      error: null,
      reconnect: jest.fn(),
      disconnect: jest.fn(),
    }));

    customRender(<AlertsPanel token="token" />);

    const statusChip = screen.getByText("Inactivo");
    expect(statusChip).toBeInTheDocument();
    expect(statusChip).toHaveClass("text-muted-foreground");
  });

  it("muestra un error de validación al intentar enviar una notificación vacía", async () => {
    const user = userEvent.setup();
    customRender(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /enviar notificación/i }));
    });

    expect(screen.getByText("Escribe un mensaje para enviar la alerta.")).toBeInTheDocument();
    expect(mockedSendAlertNotification).not.toHaveBeenCalled();
  });

  it("gestiona un error del API al enviar la notificación", async () => {
    mockedSendAlertNotification.mockRejectedValue(new Error("Servicio caído"));
    const user = userEvent.setup();
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    try {
      customRender(<AlertsPanel token="secure-token" />);

      await act(async () => {
        await user.type(screen.getByPlaceholderText("Mensaje para Telegram/Discord"), "Probar");
        await user.click(screen.getByRole("button", { name: /enviar notificación/i }));
      });

      await waitFor(() => {
        expect(screen.getByText("Servicio caído")).toBeInTheDocument();
      });
    } finally {
      consoleSpy.mockRestore();
    }
  });

  it("requiere condición para crear la alerta", async () => {
    const user = userEvent.setup();
    customRender(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(screen.getByPlaceholderText("Título de la alerta"), "Alerta sin condición");
      await user.type(screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL)"), "btc");
      await user.type(screen.getByPlaceholderText("Valor (ej. 30)"), "30000");
      await user.click(screen.getByRole("button", { name: /crear alerta/i }));
    });

    expect(screen.getByText("Debes especificar una condición para la alerta.")).toBeInTheDocument();
    expect(mockedCreateAlert).not.toHaveBeenCalled();
  });

  it("requiere valor numérico para crear la alerta", async () => {
    const user = userEvent.setup();
    customRender(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(screen.getByPlaceholderText("Título de la alerta"), "Alerta");
      await user.type(screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL)"), "eth");
      await user.type(
        screen.getByPlaceholderText("Condición (ej. BTC > 50,000 USD)"),
        "ETH supera los 3k",
      );
      await user.click(screen.getByRole("button", { name: /crear alerta/i }));
    });

    expect(screen.getByText("Debes indicar un valor numérico para la alerta.")).toBeInTheDocument();
    expect(mockedCreateAlert).not.toHaveBeenCalled();
  });

  it("valida que exista activo antes de crear la alerta", async () => {
    const user = userEvent.setup();
    customRender(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(screen.getByPlaceholderText("Título de la alerta"), "Alerta");
      await user.type(screen.getByPlaceholderText("Condición (ej. BTC > 50,000 USD)"), "BTC");
      await user.type(screen.getByPlaceholderText("Valor (ej. 30)"), "1");
      await user.click(screen.getByRole("button", { name: /crear alerta/i }));
    });

    expect(screen.getByText("Debes indicar el activo para la alerta.")).toBeInTheDocument();
    expect(mockedCreateAlert).not.toHaveBeenCalled();
  });

  it("muestra un mensaje cuando el backend falla al crear", async () => {
    const user = userEvent.setup();
    mockedCreateAlert.mockRejectedValueOnce(new Error("Backend caído"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    try {
      customRender(<AlertsPanel token="secure-token" />);

      await act(async () => {
        await user.type(screen.getByPlaceholderText("Título de la alerta"), "Alerta");
        await user.type(screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL)"), "btc");
        await user.type(
          screen.getByPlaceholderText("Condición (ej. BTC > 50,000 USD)"),
          "BTC > 50k",
        );
        await user.type(screen.getByPlaceholderText("Valor (ej. 30)"), "50000");
        await user.click(screen.getByRole("button", { name: /crear alerta/i }));
      });

      await waitFor(() => {
        expect(screen.getByText("Backend caído")).toBeInTheDocument();
      });
    } finally {
      consoleSpy.mockRestore();
    }
  });

  it("muestra un error si la API falla al actualizar", async () => {
    const user = userEvent.setup();
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue(
      createSWRMock({
        data: [
          {
            id: "alert-1",
            title: "Alerta",
            asset: "BTCUSDT",
            condition: "Precio > 50k",
            value: 50000,
            active: true,
          },
        ],
        mutate,
      }),
    );
    mockedUpdateAlert.mockRejectedValueOnce(new Error("No se pudo pausar"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    try {
      customRender(<AlertsPanel token="secure-token" />);

      await act(async () => {
        await user.click(screen.getByRole("button", { name: /pausar/i }));
      });

      await waitFor(() => {
        expect(screen.getByText("No se pudo pausar")).toBeInTheDocument();
      });
    } finally {
      consoleSpy.mockRestore();
    }
  });

  it("muestra un error si la API falla al eliminar", async () => {
    const user = userEvent.setup();
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue(
      createSWRMock({
        data: [
          {
            id: "alert-1",
            title: "Alerta",
            asset: "BTCUSDT",
            condition: "Precio > 50k",
            value: 50000,
            active: true,
          },
        ],
        mutate,
      }),
    );
    mockedDeleteAlert.mockRejectedValueOnce(new Error("No se pudo eliminar"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    try {
      customRender(<AlertsPanel token="secure-token" />);

      await act(async () => {
        await user.click(screen.getByRole("button", { name: /eliminar alerta/i }));
      });

      await waitFor(() => {
        expect(screen.getByText("No se pudo eliminar")).toBeInTheDocument();
      });
    } finally {
      consoleSpy.mockRestore();
    }
  });

  it("muestra el error de sugerencia cuando la IA falla", async () => {
    const user = userEvent.setup();
    mockedSuggestAlertCondition.mockRejectedValueOnce(new Error("IA caída"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    try {
      customRender(<AlertsPanel token="secure-token" />);

      await act(async () => {
        await user.type(screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL)"), "btc");
        await user.click(screen.getByRole("button", { name: /sugerir alerta/i }));
      });

      await waitFor(() => {
        expect(screen.getByText("IA caída")).toBeInTheDocument();
      });
    } finally {
      consoleSpy.mockRestore();
    }
  });
});
