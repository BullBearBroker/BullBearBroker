import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";

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
