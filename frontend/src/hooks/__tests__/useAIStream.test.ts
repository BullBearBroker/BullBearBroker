import { act, renderHook } from "@/tests/utils/renderWithProviders";

import { useAIStream, type UseAIStreamOptions } from "../useAIStream";

// QA: EventSource simulado para controlar flujos sin red real.
class EventSourceMock {
  static instances: EventSourceMock[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;
  url: string;
  closed = false;

  constructor(url: string) {
    this.url = url;
    EventSourceMock.instances.push(this);
  }

  close() {
    this.closed = true;
  }
}

describe("useAIStream", () => {
  const originalEventSource = window.EventSource;
  let consoleDebugSpy: jest.SpyInstance;

  beforeEach(() => {
    EventSourceMock.instances = [];
    (window as any).EventSource = EventSourceMock as unknown as typeof EventSource;
    consoleDebugSpy = jest.spyOn(console, "debug").mockImplementation(() => {});
  });

  afterEach(() => {
    window.EventSource = originalEventSource as typeof EventSource;
    consoleDebugSpy.mockRestore();
  });

  it("abre el stream cuando está habilitado y parsea mensajes JSON", async () => {
    const { result } = renderHook(() => useAIStream({ enabled: true, token: "abc" }));

    expect(EventSourceMock.instances).toHaveLength(1);
    expect(EventSourceMock.instances[0].url).toContain("token=abc");

    await act(async () => {
      EventSourceMock.instances[0].onopen?.();
    });

    expect(result.current.connected).toBe(true);

    await act(async () => {
      EventSourceMock.instances[0].onmessage?.({
        data: JSON.stringify({ message: "hola" }),
      } as MessageEvent<string>);
    });

    expect(result.current.insights).toHaveLength(1);
    expect(result.current.insights[0]).toMatchObject({ message: "hola", source: "stream" });
  });

  it("propaga insights manuales y del canal realtime", async () => {
    const { result, rerender } = renderHook<
      ReturnType<typeof useAIStream>,
      UseAIStreamOptions | undefined
    >((props) => useAIStream(props), {
      initialProps: { enabled: true },
    });

    await act(async () => {
      result.current.addInsight("manual insight", { timestamp: "2024-01-01T00:00:00Z" });
    });

    expect(result.current.insights).toHaveLength(1);
    expect(result.current.insights[0]).toMatchObject({ source: "manual" });

    rerender({
      enabled: true,
      realtimePayload: {
        type: "insight",
        content: "desde realtime",
        timestamp: "2024-01-02T00:00:00Z",
      },
    });

    expect(result.current.insights).toHaveLength(2);
    expect(result.current.insights[1]).toMatchObject({
      source: "realtime",
      message: "desde realtime",
    });
    expect(consoleDebugSpy).toHaveBeenCalledWith("AI Insight recibido:", "desde realtime");
  });

  it("cierra el stream y limpia estado cuando se deshabilita", async () => {
    const { rerender } = renderHook(
      (props: Parameters<typeof useAIStream>[0]) => useAIStream(props),
      { initialProps: { enabled: true } },
    );

    expect(EventSourceMock.instances).toHaveLength(1);

    rerender({ enabled: false });

    expect(EventSourceMock.instances[0].closed).toBe(true);
  });
});
