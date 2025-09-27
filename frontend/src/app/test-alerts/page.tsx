import { AlertsPanel } from "@/components/alerts/alerts-panel";

export default function TestAlertsPage() {
  return (
    <div className="p-6 font-sans">
      <h1 className="mb-4 text-xl font-bold">🔔 Test Alertas</h1>
      {/* Aquí inyectamos el componente con un token de prueba si hace falta */}
      <AlertsPanel token="demo-token" />
    </div>
  );
}
