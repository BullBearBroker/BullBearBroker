import { render, screen } from "@testing-library/react";
import useSWR from "swr";

import { NewsPanel } from "../news-panel";

jest.mock("swr", () => ({
  __esModule: true,
  default: jest.fn()
}));

const useSWRMock = useSWR as unknown as jest.Mock;

describe("NewsPanel", () => {
  beforeEach(() => {
    useSWRMock.mockReturnValue({
      data: [
        {
          id: 1,
          title: "Mercados al alza",
          url: "https://example.com/news",
          source: "Ejemplo",
          summary: "Resumen de prueba",
          published_at: new Date("2024-01-01T00:00:00Z").toISOString()
        }
      ],
      error: undefined,
      isLoading: false
    });
  });

  afterEach(() => {
    useSWRMock.mockReset();
  });

  it("muestra las noticias recibidas", () => {
    render(<NewsPanel token="token" />);

    expect(screen.getByText(/mercados al alza/i)).toBeInTheDocument();
    expect(screen.getByText(/ejemplo/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /leer noticia/i })).toHaveAttribute(
      "href",
      "https://example.com/news"
    );
  });
});
