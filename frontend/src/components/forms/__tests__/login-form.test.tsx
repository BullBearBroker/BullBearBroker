import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { LoginForm } from "../login-form";

const loginMock = jest.fn();

jest.mock("@/components/providers/auth-provider", () => ({
  useAuth: () => ({
    login: loginMock
  })
}));

describe("LoginForm", () => {
  beforeEach(() => {
    loginMock.mockReset();
  });

  it("muestra mensajes de validación cuando el formulario está vacío", async () => {
    render(<LoginForm />);

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(await screen.findByText(/correo válido/i)).toBeInTheDocument();
    expect(
      await screen.findByText(/la contraseña debe tener al menos 6 caracteres/i)
    ).toBeInTheDocument();
  });

  it("envía los datos correctamente", async () => {
    render(<LoginForm />);

    fireEvent.input(screen.getByLabelText(/correo electrónico/i), {
      target: { value: "user@example.com" }
    });

    fireEvent.input(screen.getByLabelText(/contraseña/i), {
      target: { value: "password" }
    });

    fireEvent.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith({
        email: "user@example.com",
        password: "password"
      });
    });
  });
});
