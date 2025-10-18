// Vars mínimas para entorno de pruebas
process.env.NEXT_PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
process.env.NEXT_PUBLIC_WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
// Clave pública VAPID dummy (debe alinear con mock backend en tests)
process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY =
  process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || 'BB-DUMMY-VAPID-KEY';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
if (typeof global !== 'undefined') {
  (global as any).IS_REACT_ACT_ENVIRONMENT = true;
}

// Nota: no exportar nada; Jest solo evalúa este archivo como setup.
