// 🧩 Bloque 8B
import { render, screen, fireEvent } from "@testing-library/react";

import NotificationCenterCard from "../notification-center-card";

describe("NotificationCenterCard", () => {
  const originalNotification = window.Notification;

  beforeEach(() => {
    localStorage.clear();
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

    expect(screen.getByText("Centro de Notificaciones")).toBeInTheDocument();

    fireEvent.click(screen.getByText("🧪 Enviar Test"));
    expect(await screen.findByText(/Notificación de prueba/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText("🧹 Limpiar"));
    expect(screen.getByText(/Sin notificaciones aún/i)).toBeInTheDocument();
  });
});
