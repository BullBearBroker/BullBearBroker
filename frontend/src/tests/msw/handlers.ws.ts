import { ws } from "msw";

export const wsHandlers = [
  ws.link("ws://localhost:8000/api/realtime/ws"),
  ws.link("ws://localhost/ws/notifications"),
];
