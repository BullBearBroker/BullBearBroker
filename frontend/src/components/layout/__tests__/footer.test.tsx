import { customRender } from "@/tests/utils/renderWithProviders";
import { axe } from "jest-axe";

import { SiteFooter } from "../footer";

describe("SiteFooter", () => {
  it("renderiza enlaces básicos", () => {
    const { getByText } = customRender(<SiteFooter />);
    expect(getByText(/términos/i)).toHaveAttribute("href", "/terminos");
    expect(getByText(/privacidad/i)).toHaveAttribute("href", "/privacidad");
    expect(getByText(/contacto/i)).toHaveAttribute("href", "/contacto");
  });

  it("cumple reglas básicas de accesibilidad", async () => {
    const { container } = customRender(<SiteFooter />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
