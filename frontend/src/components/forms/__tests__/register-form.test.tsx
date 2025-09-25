import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { RegisterForm } from "../register-form";

const registerMock = jest.fn();

jest.mock("@/components/providers/auth-provider", () => ({
  useAuth: () => ({
    register: registerMock
  })
}));

describe("RegisterForm", () => {
  beforeEach(() => {
    registerMock.mockReset();
  });

  it("muestra error cuando las contraseñas no coinciden", async () => {
    render(<RegisterForm />);

    fireEvent.input(screen.getByLabelText(/correo electrónico/i), {
      target: { value: "user@example.com" }
    });

    fireEvent.input(screen.getByLabelText(/^contraseña$/i), {
      target: { value: "password" }
    });

    fireEvent.input(screen.getByLabelText(/confirmar contraseña/i), {
      target: { value: "otra" }
    });

    fireEvent.click(screen.getByRole("button", { name: /registrarse/i }));

    expect(
      await screen.findByText(/las contraseñas no coinciden/i)
    ).toBeInTheDocument();
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("envía los datos válidos", async () => {
    render(<RegisterForm />);

    fireEvent.input(screen.getByLabelText(/nombre/i), {
      target: { value: "Jane" }
    });

    fireEvent.input(screen.getByLabelText(/correo electrónico/i), {
      target: { value: "jane@example.com" }
    });

    fireEvent.input(screen.getByLabelText(/^contraseña$/i), {
      target: { value: "password" }
    });

    fireEvent.input(screen.getByLabelText(/confirmar contraseña/i), {
      target: { value: "password" }
    });

    fireEvent.click(screen.getByRole("button", { name: /registrarse/i }));

    await waitFor(() => {
      expect(registerMock).toHaveBeenCalledWith({
        name: "Jane",
        email: "jane@example.com",
        password: "password"
      });
    });
  });
});
