import React from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChatPanel } from "../chat-panel";
import { sendChatMessage } from "@/lib/api";

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
}));

describe("ChatPanel", () => {
  let scrollSpy: jest.SpyInstance;
  const mockedSendChatMessage =
    sendChatMessage as jest.MockedFunction<typeof sendChatMessage>;

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
    scrollSpy.mockClear();
  });

  it("renderiza el saludo inicial del asistente y la insignia IA", () => {
    act(() => {
      render(<ChatPanel token={undefined} />);
    });

    expect(
      screen.getByText(
        "Hola, soy tu asistente financiero BullBear. ¿En qué puedo ayudarte hoy?"
      )
    ).toBeInTheDocument();
    expect(screen.getByText("IA")).toBeInTheDocument();
    expect(mockedSendChatMessage).not.toHaveBeenCalled();
  });

  it("muestra el mensaje de usuario cuando hay una conversación con un mensaje", () => {
    const userMessage = {
      role: "user" as const,
      content: "Mensaje inicial del usuario",
    };

    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy.mockImplementationOnce(<S>(initialState: S | (() => S)) => {
      void initialState;
      const state = ([userMessage] as unknown) as S;
      const setState = (() => {}) as React.Dispatch<React.SetStateAction<S>>;
      return [state, setState];
    });

    try {
      act(() => {
        render(<ChatPanel token={undefined} />);
      });

      expect(screen.getByText(userMessage.content)).toBeInTheDocument();
    } finally {
      useStateSpy.mockRestore();
    }
  });

  it("gestiona una conversación con múltiples mensajes", async () => {
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
    });

    render(<ChatPanel token="demo" />);

    await act(async () => {
      await user.type(
        screen.getByPlaceholderText(
          "Escribe tu consulta sobre mercados, trading o inversiones..."
        ),
        "Hola"
      );
      await user.click(screen.getByRole("button", { name: /enviar/i }));
    });

    await waitFor(() => {
      expect(screen.getByText("Respuesta 1")).toBeInTheDocument();
      expect(screen.getByText("Respuesta 2")).toBeInTheDocument();
    });

    expect(screen.getByText(/Respuesta con datos reales/i)).toBeInTheDocument();
  });

  it("muestra un mensaje de error cuando el envío falla", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockRejectedValueOnce(new Error("Error de red"));

    render(<ChatPanel token="demo" />);

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

    render(<ChatPanel token="demo" />);

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
});
