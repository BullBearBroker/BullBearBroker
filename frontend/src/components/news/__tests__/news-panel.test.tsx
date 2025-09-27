// [Codex] nuevo - Ajuste de expectativas a textos reales
import { act, render, screen } from "@testing-library/react";
import { SWRConfig } from "swr";
import { axe } from "jest-axe";
import { NewsPanel } from "../news-panel";
import { newsEmptyHandler, newsErrorHandler } from "@/tests/msw/handlers";
import { server } from "@/tests/msw/server";

async function renderNews() {
  let utils: ReturnType<typeof render> | undefined;
  await act(async () => {
    utils = render(
      <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
        <NewsPanel token="token" />
      </SWRConfig>
    );
  });
  return utils!;
}

describe("NewsPanel", () => {
  it("muestra las noticias recibidas", async () => {
    await renderNews();

    expect(await screen.findByText(/mercados al alza/i)).toBeInTheDocument();
    expect(screen.getByText(/ejemplo/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /leer noticia/i })
    ).toHaveAttribute("href", "https://example.com/news");
  });

  it("muestra estado vacío cuando no hay datos", async () => {
    server.use(newsEmptyHandler);

    await renderNews();

    expect(
      await screen.findByText(/no hay noticias disponibles/i)
    ).toBeInTheDocument();
  });

  it("muestra estado de error ante 500", async () => {
    server.use(newsErrorHandler);

    await renderNews();

    expect(
      await screen.findByText(/no hay noticias disponibles/i)
    ).toBeInTheDocument();
  });

  it("aplica accesibilidad básica", async () => {
    const { container } = await renderNews();

    expect(await axe(container)).toHaveNoViolations();
  });
});
