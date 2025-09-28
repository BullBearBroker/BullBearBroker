import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { RegisterForm } from "../register-form";

// ✅ Mock Router
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

// ✅ Mock Auth Provider
const mockRegisterUser = jest.fn();
jest.mock("@/components/providers/auth-provider", () => {
  return {
    useAuth: () => ({
      registerUser: mockRegisterUser,
    }),
    __esModule: true,
  };
});

describe("RegisterForm", () => {
  beforeEach(() => {
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush });
    jest.clearAllMocks();
  });

  it("muestra error si las contraseñas no coinciden", async () => {
    render(<RegisterForm />);
    fireEvent.change(screen.getByPlaceholderText("Nombre"), {
      target: { value: "Luis" },
    });
    fireEvent.change(screen.getByPlaceholderText("Correo electrónico"), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Contraseña"), {
      target: { value: "123456" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirmar contraseña"), {
      target: { value: "654321" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Registrarse" }));

    expect(
      await screen.findByText("Las contraseñas no coinciden")
    ).toBeInTheDocument();
  });

  it("redirige al login tras registro exitoso", async () => {
    mockRegisterUser.mockResolvedValueOnce({});
    render(<RegisterForm />);
    fireEvent.change(screen.getByPlaceholderText("Nombre"), {
      target: { value: "Luis" },
    });
    fireEvent.change(screen.getByPlaceholderText("Correo electrónico"), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Contraseña"), {
      target: { value: "123456" },
    });
    fireEvent.change(screen.getByPlaceholderText("Confirmar contraseña"), {
      target: { value: "123456" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Registrarse" }));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/login"));
  });
});
