import React from "react";
import { act, render, screen } from "@testing-library/react";

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
});
