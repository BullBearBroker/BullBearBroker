import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { LoginForm } from "../login-form";

// ✅ Mock Router
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

// ✅ Mock Auth Provider
const mockLoginUser = jest.fn();
jest.mock("@/components/providers/auth-provider", () => {
  return {
    useAuth: () => ({
      loginUser: mockLoginUser,
    }),
    __esModule: true,
  };
});

describe("LoginForm", () => {
  beforeEach(() => {
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush });
    jest.clearAllMocks();
  });

  it("muestra error si el email no es válido", async () => {
    render(<LoginForm />);
    fireEvent.change(screen.getByPlaceholderText("Correo electrónico"), {
      target: { value: "invalido" },
    });
    fireEvent.change(screen.getByPlaceholderText("Contraseña"), {
      target: { value: "123456" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Iniciar Sesión" }));

    expect(
      await screen.findByText("Debe ingresar un correo válido")
    ).toBeInTheDocument();
  });

  it("redirige al dashboard tras login exitoso", async () => {
    mockLoginUser.mockResolvedValueOnce({});
    render(<LoginForm />);
    fireEvent.change(screen.getByPlaceholderText("Correo electrónico"), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Contraseña"), {
      target: { value: "123456" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Iniciar Sesión" }));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/dashboard"));
  });
});
