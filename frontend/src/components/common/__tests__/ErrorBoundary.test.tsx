import { customRender, screen } from "@/tests/utils/renderWithProviders";

import { ErrorBoundary } from "../ErrorBoundary";

describe("ErrorBoundary", () => {
  it("muestra el fallback cuando un componente lanza un error", () => {
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    function Problematic(): JSX.Element {
      throw new Error("boom");
    }

    try {
      customRender(
        <ErrorBoundary fallback={<span>Ha ocurrido un error crítico</span>}>
          <Problematic />
        </ErrorBoundary>,
      );
    } finally {
      consoleSpy.mockRestore();
    }

    expect(screen.getByText("Ha ocurrido un error crítico")).toBeInTheDocument();
  });

  // QA: cubrimos la lógica de reset para subir la cobertura del boundary.
  it("restablece el estado cuando cambian las resetKeys", () => {
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    const Thrower = ({ shouldThrow }: { shouldThrow: boolean }) => {
      if (shouldThrow) {
        throw new Error("boom");
      }
      return <p>Recuperado</p>;
    };

    const { rerender } = customRender(
      <ErrorBoundary resetKeys={["v1"]}>
        <Thrower shouldThrow />
      </ErrorBoundary>,
    );

    expect(
      screen.getByText("Ha ocurrido un error inesperado. Intenta recargar esta sección."),
    ).toBeInTheDocument();

    rerender(
      <ErrorBoundary resetKeys={["v2"]}>
        <Thrower shouldThrow={false} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Recuperado")).toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
