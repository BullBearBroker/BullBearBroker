## BullBearBroker

### Configuración de entorno

La API utiliza JWT para autenticar a los usuarios. Define una clave secreta fuerte antes de ejecutar el backend creando un archivo `.env` en la raíz del proyecto (o configurando las variables de entorno en tu plataforma de despliegue) con el siguiente contenido:

```env
BULLBEARBROKER_SECRET_KEY="coloca_aquí_una_clave_aleatoria_segura"
# Opcional: BULLBEARBROKER_JWT_ALGORITHM="HS256"
```

> 💡 Puedes generar una cadena segura ejecutando en tu terminal `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

Si la clave no está definida, el backend generará automáticamente una de un solo uso al iniciarse, lo cual es útil para desarrollo pero invalidará los tokens emitidos previamente tras cada reinicio.

### Registro de nuevas fuentes de datos y API keys

Los servicios de mercado comparten una arquitectura basada en _helpers_ reutilizables y caché para acceder a distintos proveedores. Para integrar una nueva fuente (por ejemplo, otra API de precios o noticias) sigue estos pasos:

1. **Declara la clave** en `.env` (p. ej. `NUEVA_API_KEY=...`) y expórtala desde `backend/utils/config.py` o el diccionario `api_keys` de `backend/services/market_service.py`.
2. **Implementa un método asíncrono** en el servicio correspondiente (`CryptoService`, `StockService` o `MarketService`) que devuelva datos en el formato estándar (`price`, `change`, `high`, `low`, `volume`, etc.). Puedes inspirarte en `_format_price_payload` para mantener la homogeneidad.
3. **Registra la fuente en el helper** adecuado (`get_crypto_price`, `get_stock_price` o `get_news`) añadiendo la función a la cadena de _fallbacks_. El helper se encargará de controlar las excepciones y de poblar la caché compartida.
4. **Actualiza las pruebas** añadiendo _stubs_ o _fixtures_ que simulen respuestas exitosas y fallos de red para la nueva fuente.

Con esta estructura, cualquier consumidor del servicio recibirá un payload consistente sin importar el proveedor elegido.

### Ejecución local

1. Instala las dependencias con `npm install`.
2. Para levantar el frontend estático, ejecuta `npm run start` y accede a [http://localhost:8080](http://localhost:8080).
3. En otra terminal, inicia el backend con `npm run backend`, lo que lanza el servidor FastAPI en [http://localhost:8000](http://localhost:8000).

Detén cada proceso con `Ctrl+C` cuando termines.
