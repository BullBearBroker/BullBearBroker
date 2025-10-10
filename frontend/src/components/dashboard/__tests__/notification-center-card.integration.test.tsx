// 🧩 Bloque 8B
import { render, screen, fireEvent } from "@testing-library/react";

// 🧩 Bloque 9B
jest.mock("@/components/providers/auth-provider", () => ({
  useAuth: jest.fn(() => ({ token: null })),
}));
// 🧩 Bloque 9B
const { useAuth: mockUseAuth } = jest.requireMock("@/components/providers/auth-provider") as {
  useAuth: jest.Mock;
};
// 🧩 Bloque 9B
jest.mock("@/hooks/useLiveNotifications", () => ({
  useLiveNotifications: jest.fn(() => ({ events: [], status: "fallback" })),
}));
// 🧩 Bloque 9B
const { useLiveNotifications: mockUseLiveNotifications } = jest.requireMock(
  "@/hooks/useLiveNotifications",
) as {
  useLiveNotifications: jest.Mock;
};

import NotificationCenterCard from "../notification-center-card";

describe("NotificationCenterCard", () => {
  const originalNotification = window.Notification;

  beforeEach(() => {
    localStorage.clear();
    mockUseAuth.mockReturnValue({ token: null });
    mockUseLiveNotifications.mockReturnValue({ events: [], status: "fallback" });
    class MockNotification {
      static permission: NotificationPermission = "granted";
      static async requestPermission() {
        return this.permission;
      }
    }
    // @ts-expect-error - mock constructor
    window.Notification = MockNotification;
  });

  afterEach(() => {
    window.Notification = originalNotification;
  });

  it("renders and handles push actions", async () => {
    render(<NotificationCenterCard />);

    expect(screen.getByText("Notificaciones en vivo")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Enviar prueba/i }));
    expect(await screen.findByText(/Notificación de prueba/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Limpiar/i }));
    expect(screen.getByText(/Sin notificaciones aún/i)).toBeInTheDocument();
  });

  // 🧩 Bloque 9B
  it("shows live connection state indicator", () => {
    render(<NotificationCenterCard />);
    expect(screen.getByText(/Canal en modo seguro/i)).toBeInTheDocument();
  });
});
