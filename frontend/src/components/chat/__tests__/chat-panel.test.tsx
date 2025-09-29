import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ChatPanel } from "../chat-panel";
import { sendChatMessage } from "@/lib/api";
import type { ChatResponse, MessagePayload } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  sendChatMessage: jest.fn(),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
}));

jest.mock("@/components/ui/textarea", () => ({
  Textarea: ({ children, ...props }: any) => <textarea {...props}>{children}</textarea>,
}));

jest.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({ children, ...props }: any) => <div {...props}>{children}</div>,
}));

jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children, ...props }: any) => <span {...props}>{children}</span>,
}));

const mockedSendChatMessage = sendChatMessage as jest.MockedFunction<typeof sendChatMessage>;

const ASSISTANT_GREETING =
  "Hola, soy tu asistente financiero BullBear. ¿En qué puedo ayudarte hoy?";

describe("ChatPanel", () => {
  beforeAll(() => {
    window.HTMLElement.prototype.scrollIntoView = jest.fn();
  });

  beforeEach(() => {
    mockedSendChatMessage.mockReset();
  });

  it("renders the initial assistant message and default badge", () => {
    render(<ChatPanel />);

    expect(screen.getByText(ASSISTANT_GREETING)).toBeInTheDocument();
    expect(screen.getByText("IA")).toBeInTheDocument();
  });

  it("sends a message and shows the assistant reply with real data badge", async () => {
    const userMessage: MessagePayload = {
      role: "user",
      content: "¿Cuál es el precio actual de BTC?",
    };

    const assistantReply: MessagePayload = {
      role: "assistant",
      content: "El precio actual de BTC es 50,000 USD.",
    };

    const mockResponse: ChatResponse = {
      messages: [
        { role: "assistant", content: ASSISTANT_GREETING },
        userMessage,
        assistantReply,
      ],
      sources: ["prices"],
      used_data: true,
    };

    mockedSendChatMessage.mockResolvedValueOnce(mockResponse);

    render(<ChatPanel token="secure-token" />);

    const input = screen.getByPlaceholderText(
      "Escribe tu consulta sobre mercados, trading o inversiones..."
    );

    await act(async () => {
      fireEvent.change(input, { target: { value: userMessage.content } });
      fireEvent.click(screen.getByRole("button", { name: /enviar/i }));
    });

    await waitFor(() => {
      expect(mockedSendChatMessage).toHaveBeenCalledWith(
        [
          { role: "assistant", content: ASSISTANT_GREETING },
          userMessage,
        ],
        "secure-token"
      );
    });

    expect(await screen.findByText(assistantReply.content)).toBeInTheDocument();
    expect(
      await screen.findByText("Respuesta con datos reales (Precios)")
    ).toBeInTheDocument();
  });
});
