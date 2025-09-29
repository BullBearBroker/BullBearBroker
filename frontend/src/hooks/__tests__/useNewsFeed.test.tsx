import { act, renderHook, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";

import { useNewsFeed } from "../useNewsFeed";
import { server } from "@/tests/msw/server";
import { newsEmptyHandler, newsErrorHandler, http, HttpResponse } from "@/tests/msw/handlers";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
    {children}
  </SWRConfig>
);

describe("useNewsFeed", () => {
  afterEach(() => {
    server.resetHandlers();
  });

  it("retorna lista de noticias", async () => {
    const { result } = renderHook(() => useNewsFeed(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.data).toBeDefined();
    expect(result.current.data?.[0]?.title).toMatch(/mercados/i);
    expect(result.current.error).toBeUndefined();
  });

  it("retorna arreglo vacío cuando no hay datos", async () => {
    server.use(newsEmptyHandler);

    const { result } = renderHook(() => useNewsFeed({ token: "token" }), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.data).toEqual([]);
    expect(result.current.error).toBeUndefined();
  });

  it("maneja errores del servidor", async () => {
    server.use(newsErrorHandler);

    const { result } = renderHook(() => useNewsFeed(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBeInstanceOf(Error);
  });

  it("permite refrescar la data manualmente", async () => {
    const customHandler = http.get("*/api/news/latest", () =>
      HttpResponse.json({
        articles: [
          {
            id: 1,
            title: "Noticia A",
            url: "https://example.com/a",
            source: "Ejemplo",
          },
        ],
      })
    );
    server.use(customHandler);

    const { result } = renderHook(() => useNewsFeed(), { wrapper });

    await waitFor(() => expect(result.current.data?.[0]?.title).toBe("Noticia A"));

    server.use(
      http.get("*/api/news/latest", () =>
        HttpResponse.json({
          articles: [
            {
              id: 2,
              title: "Noticia B",
              url: "https://example.com/b",
              source: "Ejemplo",
            },
          ],
        })
      )
    );

    await act(async () => {
      await result.current.refresh();
    });

    await waitFor(() => expect(result.current.data?.[0]?.title).toBe("Noticia B"));
  });
});
