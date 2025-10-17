# Frontend Notes

## Login form rate limiting

El formulario de inicio de sesión ahora aplica varias protecciones en el cliente:

- Si la API responde con `429`, se muestra el mensaje traducido de “Demasiados intentos…” con la cuenta regresiva aproximada y se deshabilitan campos y botón hasta que expire el tiempo.
- Mientras dura el enfriamiento no se envían peticiones adicionales; al terminar vuelve a habilitarse el formulario automáticamente.
- Los envíos consecutivos se limitan a una petición por segundo y, si el usuario intenta reenviar antes, la petición anterior se cancela para evitar duplicados.
- Se registra el evento `login_rate_limited_ui` en la capa de analítica para que el equipo pueda monitorear estos bloqueos sin exponer PII.

Para ejecutar los tests relacionados usa `pnpm test --filter login-form` desde la carpeta `frontend`.
