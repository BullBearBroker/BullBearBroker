import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

const mockedUseTheme = jest.fn();

jest.mock("next-themes", () => ({
  useTheme: () => mockedUseTheme(),
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { ThemeToggle } from "../theme-toggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    mockedUseTheme.mockReset();
  });

  it("mantiene la estructura visual esperada", () => {
    const setTheme = jest.fn();
    mockedUseTheme.mockReturnValue({
      theme: "dark",
      resolvedTheme: "dark",
      setTheme,
    });

    const { container } = render(<ThemeToggle />);

    const button = container.querySelector("button");
    const summary = {
      tag: button?.tagName,
      ariaLabel: button?.getAttribute("aria-label"),
      className: button?.getAttribute("class"),
      iconClass: button?.querySelector("svg")?.getAttribute("class"),
    };

    expect(summary).toMatchInlineSnapshot(`
      {
        "ariaLabel": "Cambiar tema",
        "className": "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ring-offset-background border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 w-10",
        "iconClass": "h-4 w-4",
        "tag": "BUTTON",
      }
    `);
  });

  it("no presenta violaciones de accesibilidad básicas", async () => {
    const setTheme = jest.fn();
    mockedUseTheme.mockReturnValue({
      theme: "light",
      resolvedTheme: "light",
      setTheme,
    });

    const { container } = render(<ThemeToggle />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("cambia a tema claro cuando el actual es oscuro", async () => {
    const setTheme = jest.fn();
    mockedUseTheme.mockReturnValue({ theme: "system", resolvedTheme: "dark", setTheme });

    const user = userEvent.setup();
    render(<ThemeToggle />);

    await user.click(screen.getByRole("button", { name: /cambiar tema/i }));
    expect(setTheme).toHaveBeenCalledWith("light");
  });

  it("cambia a tema oscuro cuando el actual es claro", async () => {
    const setTheme = jest.fn();
    mockedUseTheme.mockReturnValue({ theme: "light", resolvedTheme: "light", setTheme });

    const user = userEvent.setup();
    render(<ThemeToggle />);

    await user.click(screen.getByRole("button", { name: /cambiar tema/i }));
    expect(setTheme).toHaveBeenCalledWith("dark");
  });
});
