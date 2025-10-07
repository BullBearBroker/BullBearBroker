// [Codex] nuevo - Ajuste de expectativas a textos reales
import useSWR from "swr";
import { customRender, screen, within } from "@/tests/utils/renderWithProviders";
import { axe } from "jest-axe";

import { NewsPanel } from "../NewsPanel";

jest.mock("swr", () => {
  const actual = jest.requireActual("swr");
  return {
    __esModule: true,
    ...actual,
    default: jest.fn(),
  };
});

const mockedUseSWR = useSWR as jest.MockedFunction<typeof useSWR>;

describe("NewsPanel", () => {
  beforeEach(() => {
    mockedUseSWR.mockReset();
  });

  it("muestra el estado de carga inicial", () => {
    mockedUseSWR.mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: true,
    } as never);

    customRender(<NewsPanel token="token" />);

    expect(screen.getByTestId("news-loading")).toBeInTheDocument();
    expect(screen.getAllByTestId("skeleton")).toHaveLength(9);
  });

  it("muestra las noticias recibidas ordenadas", async () => {
    mockedUseSWR.mockReturnValue({
      data: [
        {
          id: "2",
          title: "Mercados al alza",
          summary: "Ejemplo",
          url: "https://example.com/news",
          source: "Ejemplo",
          published_at: "2024-05-02T10:00:00Z",
        },
        {
          id: "1",
          title: "Reporte semanal",
          summary: "Otro",
          url: "https://example.com/other",
          source: "Otro",
          published_at: "2024-05-01T10:00:00Z",
        },
      ],
      error: undefined,
      isLoading: false,
    } as never);

    const { container } = customRender(<NewsPanel token="token" />);

    const articles = screen.getAllByRole("article");
    expect(within(articles[0]).getByText("Mercados al alza")).toBeInTheDocument();
    expect(within(articles[0]).getByRole("link", { name: /leer noticia/i })).toHaveAttribute(
      "href",
      "https://example.com/news"
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("muestra estado vacío cuando no hay datos", () => {
    mockedUseSWR.mockReturnValue({
      data: [],
      error: undefined,
      isLoading: false,
    } as never);

    customRender(<NewsPanel token="token" />);

    const emptyState = screen.getByTestId("empty-state");
    expect(within(emptyState).getByText(/no hay noticias disponibles/i)).toBeInTheDocument();
  });

  it("muestra estado de error ante fallas en el fetch", () => {
    mockedUseSWR.mockReturnValue({
      data: undefined,
      error: new Error("Fallo en noticias"),
      isLoading: false,
    } as never);

    customRender(<NewsPanel token="token" />);

    const emptyState = screen.getByTestId("empty-state");
    expect(within(emptyState).getByText(/no se pudieron cargar las noticias/i)).toBeInTheDocument();
    expect(within(emptyState).getByText(/fallo en noticias/i)).toBeInTheDocument();
  });

  it("usa texto por defecto cuando faltan la fuente y la fecha", () => {
    mockedUseSWR.mockReturnValue({
      data: [
        {
          id: "1",
          title: "Sin fuente",
          summary: null,
          url: "https://example.com",
          source: null,
          published_at: null,
        },
      ],
      error: undefined,
      isLoading: false,
    } as never);

    customRender(<NewsPanel token="token" />);

    expect(screen.getByText("Sin fuente")).toBeInTheDocument();
    expect(screen.getByText("Fuente desconocida")).toBeInTheDocument();
    expect(screen.queryByText(/\d{4}/)).not.toBeInTheDocument();
  });
});
