import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import useSWR from "swr";

import { createAlert, updateAlert } from "@/lib/api";
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

// ✅ sin sintaxis TS, para que Jest no falle
const mockedUseSWR = useSWR;
const mockedCreateAlert = createAlert;
const mockedUpdateAlert = updateAlert;

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
      await user.type(
        screen.getByPlaceholderText("Valor (ej. 30)"),
        "50000"
      );
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
      await user.type(
        screen.getByPlaceholderText("Valor (ej. 30)"),
        "3000"
      );
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
    render(<AlertsPanel token="demo-token" />);

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
});
