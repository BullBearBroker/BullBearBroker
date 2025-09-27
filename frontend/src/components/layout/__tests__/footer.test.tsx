import { render } from "@testing-library/react";
import { axe } from "jest-axe";

import { SiteFooter } from "../footer";

describe("SiteFooter", () => {
  it("renderiza enlaces básicos", () => {
    const { getByText } = render(<SiteFooter />);
    expect(getByText(/términos/i)).toHaveAttribute("href", "/terminos");
    expect(getByText(/privacidad/i)).toHaveAttribute("href", "/privacidad");
    expect(getByText(/contacto/i)).toHaveAttribute("href", "/contacto");
  });

  it("cumple reglas básicas de accesibilidad", async () => {
    const { container } = render(<SiteFooter />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
