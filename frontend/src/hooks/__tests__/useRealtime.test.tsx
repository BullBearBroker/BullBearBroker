import { act, renderHook, waitFor } from "@testing-library/react";
import { Server } from "jest-websocket-mock";

import { useRealtime } from "../useRealtime";

describe("useRealtime", () => {
  let server: InstanceType<typeof Server>;

  beforeEach(() => {
    server = new Server("ws://localhost:8000/api/realtime/ws");
  });

  afterEach(() => {
    if (server) {
      act(() => {
        server.close();
      });
    }
    Server.clean();
  });

  it("establece connected=true cuando la conexión abre", async () => {
    const { result } = renderHook(() => useRealtime());

    await act(async () => {
      await server.connected;
    });

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });
  });

  it("actualiza el estado data con los mensajes recibidos", async () => {
    const { result } = renderHook(() => useRealtime());

    await act(async () => {
      await server.connected;
    });

    act(() => {
      server.send({ type: "price", symbol: "BTCUSDT", price: 12345.67 });
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(
        expect.objectContaining({ type: "price", symbol: "BTCUSDT" }),
      );
    });
  });

  it("marca connected=false cuando el servidor cierra", async () => {
    const { result } = renderHook(() => useRealtime());

    await act(async () => {
      await server.connected;
    });

    act(() => {
      server.close();
    });

    await waitFor(() => {
      expect(result.current.connected).toBe(false);
    });
  });

  it("maneja mensajes corruptos sin lanzar errores", async () => {
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    const { result } = renderHook(() => useRealtime());

    await act(async () => {
      await server.connected;
    });

    act(() => {
      server.send("not-json");
    });

    expect(result.current.data).toBeNull();
    expect(consoleSpy).toHaveBeenCalled();

    consoleSpy.mockRestore();
  });
});
