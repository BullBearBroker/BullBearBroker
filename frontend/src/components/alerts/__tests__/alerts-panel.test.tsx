import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import useSWR from "swr";

import {
  createAlert,
  updateAlert,
  sendAlertNotification,
  suggestAlertCondition,
} from "@/lib/api";
import { AlertsPanel } from "../alerts-panel";

jest.mock("swr", () => ({
  __esModule: true,
  default: jest.fn(),
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
const mockedSendAlertNotification =
  sendAlertNotification as jest.MockedFunction<typeof sendAlertNotification>;
const mockedSuggestAlertCondition =
  suggestAlertCondition as jest.MockedFunction<typeof suggestAlertCondition>;

describe("AlertsPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseSWR.mockReturnValue({
      data: [],
      error: undefined,
      mutate: jest.fn().mockResolvedValue(undefined),
      isLoading: false,
    });
  });

  it("creates an alert with the expected payload", async () => {
    const user = userEvent.setup();
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue({
      data: [],
      error: undefined,
      mutate,
      isLoading: false,
    });

    mockedCreateAlert.mockResolvedValue({
      id: "1",
      title: "Comprar BTC",
      asset: "BTCUSDT",
      condition: "Precio cruza los 50k",
      value: 50000,
      active: true,
    });

    render(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Título de la alerta"),
        "  Comprar BTC "
      );
      await user.type(
        screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL)"),
        "btcusdt"
      );
      await user.type(
        screen.getByPlaceholderText("Condición (ej. BTC > 50,000 USD)"),
        "Precio cruza los 50k"
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
        })
      );
    });

    expect(mutate).toHaveBeenCalled();
  });

  it("shows a validation error when title is missing", async () => {
    const user = userEvent.setup();
    render(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL)"),
        "ETHUSDT"
      );
      await user.type(
        screen.getByPlaceholderText("Condición (ej. BTC > 50,000 USD)"),
        "ETH supera los 3000"
      );
      await user.type(screen.getByPlaceholderText("Valor (ej. 30)"), "3000");
      await user.click(screen.getByRole("button", { name: /crear alerta/i }));
    });

    expect(
      await screen.findByText("Debes asignar un título a la alerta.")
    ).toBeInTheDocument();
    expect(mockedCreateAlert).not.toHaveBeenCalled();
  });

  it("toggles an alert to inactive", async () => {
    const user = userEvent.setup();
    const mutate = jest.fn().mockResolvedValue(undefined);
    mockedUseSWR.mockReturnValue({
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
      error: undefined,
      mutate,
      isLoading: false,
    });

    mockedUpdateAlert.mockResolvedValue({
      id: "alert-1",
      title: "Cruz dorada",
      asset: "BTCUSDT",
      condition: "Cruce EMA 50/200",
      value: 50000,
      active: false,
    });

    render(<AlertsPanel token="secure-token" />);

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
    render(<AlertsPanel token="demo-token" />);

    const textarea = screen.getByPlaceholderText(
      /condición/i
    ) as HTMLTextAreaElement;
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
    render(<AlertsPanel token="demo-token" />);

    const textarea = screen.getByPlaceholderText(
      /condición/i
    ) as HTMLTextAreaElement;
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
    mockedUseSWR.mockReturnValue({
      data: undefined,
      error: undefined,
      mutate: jest.fn().mockResolvedValue(undefined),
      isLoading: true,
    });

    render(<AlertsPanel token="token" />);

    expect(screen.getByText("Cargando alertas...")).toBeInTheDocument();
  });

  it("muestra un mensaje de error cuando la carga falla", () => {
    mockedUseSWR.mockReturnValue({
      data: undefined,
      error: new Error("Fallo en SWR"),
      mutate: jest.fn().mockResolvedValue(undefined),
      isLoading: false,
    });

    render(<AlertsPanel token="token" />);

    expect(screen.getByText(/fallo en swr/i)).toBeInTheDocument();
  });

  it("indica cuando no hay alertas disponibles", () => {
    mockedUseSWR.mockReturnValue({
      data: [],
      error: undefined,
      mutate: jest.fn().mockResolvedValue(undefined),
      isLoading: false,
    });

    render(<AlertsPanel token="token" />);

    expect(
      screen.getByText("Aún no tienes alertas. Crea una para recibir notificaciones.")
    ).toBeInTheDocument();
  });

  it("renderiza la lista con múltiples alertas", () => {
    mockedUseSWR.mockReturnValue({
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
      error: undefined,
      mutate: jest.fn().mockResolvedValue(undefined),
      isLoading: false,
    });

    render(<AlertsPanel token="token" />);

    expect(screen.getByText("Alerta 1")).toBeInTheDocument();
    expect(screen.getByText("Alerta 2")).toBeInTheDocument();
    expect(screen.getAllByText("Activa")).toHaveLength(1);
    expect(screen.getAllByText("Pausada")).toHaveLength(1);
  });

  it("obtiene una sugerencia de condición y muestra la nota", async () => {
    mockedSuggestAlertCondition.mockResolvedValue({
      suggestion: "BTC > 45000",
      notes: "Basado en indicadores",
    });
    const user = userEvent.setup();

    render(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Activo (ej. BTCUSDT, AAPL)"),
        "btc"
      );
      await user.click(screen.getByRole("button", { name: /sugerir alerta/i }));
    });

    expect(mockedSuggestAlertCondition).toHaveBeenCalledWith(
      "secure-token",
      expect.objectContaining({ asset: "btc", interval: "1h" })
    );
    expect(screen.getByPlaceholderText(/condición/i)).toHaveValue("BTC > 45000");
    expect(screen.getByText("Basado en indicadores")).toBeInTheDocument();
  });

  it("muestra un error si se solicita sugerencia sin activo", async () => {
    const user = userEvent.setup();
    render(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /sugerir alerta/i }));
    });

    expect(
      screen.getByText("Completa el campo de activo antes de pedir sugerencias.")
    ).toBeInTheDocument();
    expect(mockedSuggestAlertCondition).not.toHaveBeenCalled();
  });

  it("envía una notificación manual y muestra el resumen", async () => {
    mockedSendAlertNotification.mockResolvedValue({
      telegram: { status: "sent", target: "123" },
      discord: { status: "queued", target: "999" },
    });
    const user = userEvent.setup();

    render(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Mensaje para Telegram/Discord"),
        "Comprar BTC"
      );
      await user.type(
        screen.getByPlaceholderText("Chat ID de Telegram (opcional)"),
        "123"
      );
      await user.type(
        screen.getByPlaceholderText("Canal de Discord (opcional)"),
        "999"
      );
      await user.click(screen.getByRole("button", { name: /enviar notificación/i }));
    });

    await waitFor(() => {
      expect(mockedSendAlertNotification).toHaveBeenCalledWith(
        "secure-token",
        expect.objectContaining({ message: "Comprar BTC" })
      );
      expect(
        screen.getByText(/Notificación enviada \(telegram: sent \| discord: queued\)/i)
      ).toBeInTheDocument();
    });
  });

  it("muestra un error de validación al intentar enviar una notificación vacía", async () => {
    const user = userEvent.setup();
    render(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /enviar notificación/i }));
    });

    expect(
      screen.getByText("Escribe un mensaje para enviar la alerta.")
    ).toBeInTheDocument();
    expect(mockedSendAlertNotification).not.toHaveBeenCalled();
  });

  it("gestiona un error del API al enviar la notificación", async () => {
    mockedSendAlertNotification.mockRejectedValue(new Error("Servicio caído"));
    const user = userEvent.setup();

    render(<AlertsPanel token="secure-token" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText("Mensaje para Telegram/Discord"),
        "Probar"
      );
      await user.click(screen.getByRole("button", { name: /enviar notificación/i }));
    });

    await waitFor(() => {
      expect(screen.getByText("Servicio caído")).toBeInTheDocument();
    });
  });
});
