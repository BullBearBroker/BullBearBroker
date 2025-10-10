import { customRender, screen } from "@/tests/utils/renderWithProviders";
import { axe } from "jest-axe";

jest.mock("../navbar", () => ({
  Navbar: () => <nav data-testid="navbar">nav</nav>,
}));

jest.mock("../footer", () => ({
  SiteFooter: () => <footer data-testid="footer">footer</footer>,
}));

import { AppChrome } from "../app-chrome";

describe("AppChrome", () => {
  it("incluye navbar, contenido y footer", () => {
    customRender(
      <AppChrome>
        <p>Contenido principal</p>
      </AppChrome>,
    );

    expect(screen.getByTestId("navbar")).toBeInTheDocument();
    expect(screen.getByText(/contenido principal/i)).toBeInTheDocument();
    expect(screen.getByTestId("footer")).toBeInTheDocument();
  });

  it("cumple reglas básicas de accesibilidad", async () => {
    const { container } = customRender(
      <AppChrome>
        <p>Contenido a11y</p>
      </AppChrome>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });
});
