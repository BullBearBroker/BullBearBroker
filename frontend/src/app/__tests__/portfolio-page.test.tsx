import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SWRConfig } from "swr";

import PortfolioPage from "../portfolio/page";
import { createMockPortfolioHandlers } from "@/tests/msw/handlers";
import { server } from "@/tests/msw/server";

jest.mock("@/components/providers/auth-provider", () => ({
  useAuth: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

const { useAuth } = jest.requireMock("@/components/providers/auth-provider");
const { useRouter } = jest.requireMock("next/navigation");

const mockedUseAuth = useAuth as jest.Mock;
const mockedUseRouter = useRouter as jest.Mock;

function renderPortfolioPage() {
  mockedUseRouter.mockReturnValue({ replace: jest.fn() });
  mockedUseAuth.mockReturnValue({
    user: { id: "1", email: "trader@example.com", name: "Trader" },
    token: "secure-token",
    loading: false,
  });

  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <PortfolioPage />
    </SWRConfig>
  );
}

describe("PortfolioPage", () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it("renderiza el panel de portafolio con datos iniciales", async () => {
    server.use(
      ...createMockPortfolioHandlers({
        initialItems: [
          { symbol: "ETHUSDT", amount: 2 },
        ],
      })
    );

    renderPortfolioPage();

    expect(await screen.findByText(/tu portafolio/i)).toBeInTheDocument();
    expect(await screen.findByText("ETHUSDT")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Total: \$240.00/)).toBeInTheDocument();
    });
  });

  it("permite agregar y eliminar activos desde la interfaz", async () => {
    server.use(
      ...createMockPortfolioHandlers({
        initialItems: [
          { id: "1", symbol: "BTCUSDT", amount: 0.5, price: 50000, value: 25000 },
        ],
        defaultPrice: 100,
      })
    );

    const user = userEvent.setup();
    renderPortfolioPage();

    expect(await screen.findByText("BTCUSDT")).toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText(/Activo/),
      "aapl"
    );
    await user.type(screen.getByPlaceholderText(/Cantidad/), "3");
    await user.click(screen.getByRole("button", { name: /Agregar activo/i }));

    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("$300.00")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /Eliminar AAPL/i }));

    await waitFor(() => {
      expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
      expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
      expect(screen.getByText(/Total: \$25,000.00/)).toBeInTheDocument();
    });
  });
});
