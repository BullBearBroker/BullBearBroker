import React from "react";
import { act, customRender, screen, waitFor } from "@/tests/utils/renderWithProviders";
import userEvent from "@testing-library/user-event";

import { ChatPanel } from "../chat-panel";
import { sendChatMessage, getChatHistory } from "@/lib/api";

// Mock de Radix ScrollArea porque JSDOM no implementa addEventListener como espera la lib
jest.mock("@radix-ui/react-scroll-area", () => {
  const React = require("react");

  const Root = ({ children, ...props }: any) =>
    React.createElement("div", props, children);
  Root.displayName = "ScrollAreaRoot";

  const Viewport = ({ children, ...props }: any) =>
    React.createElement("div", props, children);
  Viewport.displayName = "ScrollAreaViewport";

  const Scrollbar = ({ children, ...props }: any) =>
    React.createElement("div", props, children);
  Scrollbar.displayName = "ScrollAreaScrollbar";

  const ScrollAreaScrollbar = Scrollbar;

  const Thumb = (props: any) => React.createElement("div", props);
  Thumb.displayName = "ScrollAreaThumb";

  const ScrollAreaThumb = Thumb;

  const Corner = (props: any) => React.createElement("div", props);
  Corner.displayName = "ScrollAreaCorner";

  const ScrollAreaCorner = Corner;

  return {
    __esModule: true,
    Root,
    Viewport,
    Scrollbar,
    ScrollAreaScrollbar,
    Thumb,
    ScrollAreaThumb,
    Corner,
    ScrollAreaCorner,
  };
});

jest.mock("@/lib/api", () => ({
  sendChatMessage: jest.fn().mockResolvedValue({
    messages: [],
    sources: [],
    used_data: false,
  }),
  getChatHistory: jest.fn().mockResolvedValue({
    session_id: "",
    created_at: new Date().toISOString(),
    messages: [],
  }),
}));

describe("ChatPanel", () => {
  let scrollSpy: jest.SpyInstance;
  const mockedSendChatMessage =
    sendChatMessage as jest.MockedFunction<typeof sendChatMessage>;
  const mockedGetChatHistory =
    getChatHistory as jest.MockedFunction<typeof getChatHistory>;

  beforeAll(() => {
    if (!window.HTMLElement.prototype.scrollIntoView) {
      Object.defineProperty(window.HTMLElement.prototype, "scrollIntoView", {
        value: jest.fn(),
        configurable: true,
      });
    }
    scrollSpy = jest
      .spyOn(window.HTMLElement.prototype, "scrollIntoView")
      .mockImplementation(() => {});
  });

  afterAll(() => {
    scrollSpy.mockRestore();
  });

  beforeEach(() => {
    mockedSendChatMessage.mockClear();
    mockedGetChatHistory.mockClear();
    window.localStorage.clear();
    scrollSpy.mockClear();
  });

  it("renderiza el saludo inicial del asistente y la insignia IA", () => {
    act(() => {
      customRender(<ChatPanel token={undefined} />);
    });

    expect(
      screen.getByText(
        "Hola, soy tu asistente financiero BullBear. ¿En qué puedo ayudarte hoy?"
      )
    ).toBeInTheDocument();
    expect(screen.getByText("IA")).toBeInTheDocument();
    expect(mockedSendChatMessage).not.toHaveBeenCalled();
    expect(mockedGetChatHistory).not.toHaveBeenCalled();
  });

  it("gestiona una conversación con múltiples mensajes y persiste la sesión", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockResolvedValueOnce({
      messages: [
        { role: "assistant", content: "Saludo inicial" },
        { role: "user", content: "Hola" },
        { role: "assistant", content: "Respuesta 1" },
        { role: "assistant", content: "Respuesta 2" },
      ],
      sources: ["news"],
      used_data: true,
      sessionId: "session-123",
    });
    mockedGetChatHistory.mockResolvedValueOnce({
      session_id: "session-123",
      created_at: new Date().toISOString(),
      messages: [
        { id: "a", role: "assistant", content: "Saludo inicial", created_at: new Date().toISOString() },
        { id: "b", role: "user", content: "Hola", created_at: new Date().toISOString() },
        { id: "c", role: "assistant", content: "Respuesta 1", created_at: new Date().toISOString() },
        { id: "d", role: "assistant", content: "Respuesta 2", created_at: new Date().toISOString() },
      ],
    } as any);

    customRender(<ChatPanel token="demo" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText(
          "Escribe tu consulta sobre mercados, trading o inversiones..."
        ),
        "Hola"
      );
      await user.click(screen.getByRole("button", { name: /enviar/i }));
    });

    await waitFor(() => expect(mockedGetChatHistory).toHaveBeenCalled());

    expect(screen.getByText("Respuesta 1")).toBeInTheDocument();
    expect(screen.getByText("Respuesta 2")).toBeInTheDocument();

    expect(screen.getByText(/Respuesta con datos reales/i)).toBeInTheDocument();
    expect(window.localStorage.getItem("chat_session_id")).toBe("session-123");
  });

  it("ignora envíos vacíos sin llamar a la API", async () => {
    const user = userEvent.setup();

    customRender(<ChatPanel token="demo" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText(
          "Escribe tu consulta sobre mercados, trading o inversiones..."
        ),
        "   "
      );
      await user.click(screen.getByRole("button", { name: /enviar/i }));
    });

    expect(mockedSendChatMessage).not.toHaveBeenCalled();
  });

  it("muestra un mensaje de error cuando el envío falla", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockRejectedValueOnce(new Error("Error de red"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    try {
      customRender(<ChatPanel token="demo" />);

      await act(async () => {
        await user.type(
          screen.getByPlaceholderText(
            "Escribe tu consulta sobre mercados, trading o inversiones..."
          ),
          "Probemos"
        );
        await user.click(screen.getByRole("button", { name: /enviar/i }));
      });

      await waitFor(() => {
        expect(screen.getByText("Error de red")).toBeInTheDocument();
      });

      expect(screen.getByText("IA")).toBeInTheDocument();
    } finally {
      consoleSpy.mockRestore();
    }
  });

  it("recupera el historial cuando existe una sesión guardada", async () => {
    window.localStorage.setItem("chat_session_id", "existing-session");
    mockedGetChatHistory.mockResolvedValueOnce({
      session_id: "existing-session",
      created_at: new Date().toISOString(),
      messages: [
        { id: "1", role: "assistant", content: "Historial previo", created_at: new Date().toISOString() },
      ],
    } as any);

    await act(async () => {
      customRender(<ChatPanel token="demo" />);
    });

    await waitFor(() => {
      expect(mockedGetChatHistory).toHaveBeenCalledWith("existing-session", "demo");
    });

    expect(screen.getByText("Historial previo")).toBeInTheDocument();
  });

  it("desplaza la vista al último mensaje tras enviar", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockResolvedValueOnce({
      messages: [
        { role: "assistant", content: "Hola" },
        { role: "user", content: "Consulta" },
        { role: "assistant", content: "Respuesta final" },
      ],
      sources: [],
      used_data: false,
    });

    customRender(<ChatPanel token="demo" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText(
          "Escribe tu consulta sobre mercados, trading o inversiones..."
        ),
        "Consulta"
      );
      await user.click(screen.getByRole("button", { name: /enviar/i }));
    });

    await waitFor(() => {
      expect(screen.getByText("Respuesta final")).toBeInTheDocument();
    });

    expect(scrollSpy).toHaveBeenCalled();
  });

  it("mantiene la conversación cuando la respuesta llega vacía", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockResolvedValueOnce({
      messages: [],
      sources: [],
      used_data: false,
    });

    customRender(<ChatPanel token="demo" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText(
          "Escribe tu consulta sobre mercados, trading o inversiones..."
        ),
        "Consulta sin respuesta"
      );
      await user.click(screen.getByRole("button", { name: /enviar/i }));
    });

    await waitFor(() => {
      expect(mockedSendChatMessage).toHaveBeenCalled();
    });

    expect(
      screen.getByText("Consulta sin respuesta", { selector: "div" })
    ).toBeInTheDocument();
    expect(screen.getByText("IA")).toBeInTheDocument();
  });

  it("muestra insignia de datos reales cuando la respuesta usa datos sin fuentes", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockResolvedValueOnce({
      messages: [
        { role: "assistant", content: "Hola" },
        { role: "user", content: "Consulta" },
        { role: "assistant", content: "Respuesta final" },
      ],
      sources: [],
      used_data: true,
    });

    customRender(<ChatPanel token="demo" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText(
          "Escribe tu consulta sobre mercados, trading o inversiones..."
        ),
        "Consulta"
      );
      await user.click(screen.getByRole("button", { name: /enviar/i }));
    });

    await waitFor(() => {
      expect(screen.getByText("Datos reales")).toBeInTheDocument();
    });
  });
});
