/**
 * QA: Variables mínimas para que el frontend no falle en Jest.
 * No se usan en producción: sólo en entorno de pruebas.
 */
process.env.NEXT_PUBLIC_API_URL ||= 'http://localhost:8000/api';
process.env.NEXT_PUBLIC_WS_URL ||= 'ws://localhost:8000';
process.env.NEXT_PUBLIC_REALTIME_WS_PATH ||= '/api/realtime/ws';

// VAPID dummy coherente entre frontend/backend en test
process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY ||= 'DUMMY_VAPID_KEY';
process.env.NEXT_PUBLIC_VAPID_KEY ||= process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
process.env.VAPID_PUBLIC_KEY_BACKEND ||= process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
