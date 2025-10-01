import { customRender, screen } from "@/tests/utils/renderWithProviders";

import { ErrorBoundary } from "../ErrorBoundary";

describe("ErrorBoundary", () => {
  it("muestra el fallback cuando un componente lanza un error", () => {
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    function Problematic() {
      throw new Error("boom");
    }

    try {
      customRender(
        <ErrorBoundary fallback={<span>Ha ocurrido un error crítico</span>}>
          <Problematic />
        </ErrorBoundary>
      );
    } finally {
      consoleSpy.mockRestore();
    }

    expect(screen.getByText("Ha ocurrido un error crítico")).toBeInTheDocument();
  });
});
