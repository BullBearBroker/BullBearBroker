// [Codex] nuevo - Stub mínimo para interceptores WebSocket en entorno de pruebas
import { EventEmitter } from "events";

export class WebSocketInterceptor extends EventEmitter {
  apply() {
    // No-op en pruebas: no necesitamos interceptar WebSockets
  }

  dispose() {
    this.removeAllListeners();
  }
}
