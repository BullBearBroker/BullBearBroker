## BullBearBroker

### Configuración de entorno

La API utiliza JWT para autenticar a los usuarios. Define una clave secreta fuerte antes de ejecutar el backend creando un archivo `.env` en la raíz del proyecto (o configurando las variables de entorno en tu plataforma de despliegue) con el siguiente contenido:

```env
BULLBEARBROKER_SECRET_KEY="coloca_aquí_una_clave_aleatoria_segura"
# Opcional: BULLBEARBROKER_JWT_ALGORITHM="HS256"
```

> 💡 Puedes generar una cadena segura ejecutando en tu terminal `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

Si la clave no está definida, el backend generará automáticamente una de un solo uso al iniciarse, lo cual es útil para desarrollo pero invalidará los tokens emitidos previamente tras cada reinicio.
