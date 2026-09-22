# Auditoría — TMA API, puente Python/Java y Telegram Stars

Fecha: 2026-09-21

## Resultado

El puente de Telegram Mini App ya forma parte de `main` y está integrado con el Bot Manager.

Flujo:

```text
Telegram Mini App
    |
    | X-Telegram-Init-Data
    v
BotManager / aiohttp
    |
    +--> HMAC Telegram + auth_date + CORS
    |
    +--> SQLite / perfil / colección / comunidad
    |
    +--> WaifuMonJavaEngine
    |        |
    |        +--> WaifuMonRuleEngine.java
    |
    +--> Telegram Bot API / Stars (XTR)
```

## Seguridad TMA

Cada ruta de negocio GET/POST exige `Telegram.WebApp.initData` válida.

El middleware:

- rechaza initData ausente o alterada;
- recalcula el HMAC con el token del bot configurado en `TMA_BOT_IDENTITY`;
- comprueba `auth_date` y una ventana máxima configurable;
- comprueba origen CORS contra `TMA_ALLOWED_ORIGINS`;
- nunca usa `initDataUnsafe` como autoridad;
- devuelve `Cache-Control: no-store` y cabeceras básicas anti-sniff/referrer.

`OPTIONS` queda fuera de la autenticación de negocio porque es el preflight CORS del navegador. Las rutas reales de aplicación continúan protegidas.

## Endpoint de inicialización

`GET /api/combat/init`

Entrega `CombatInitDTO` con:

- identidad validada por Telegram;
- comunidad configurada y autorizada;
- hasta tres personajes de la colección del usuario;
- combatiente tutorial determinista cuando no existe colección;
- tres oponentes deterministas;
- `CombatAssetContractDTO`;
- sprites de 128×128;
- poses `idle`, `attack`, `hit`;
- rutas de cartas `<character-id>--normal.jpg`.

## Endpoint de combate

`POST /api/combat/action`

Valida:

- acción `attack|special|defend`;
- IDs de combatientes;
- propiedad del atacante;
- comunidad asociada al usuario;
- clave de idempotencia.

Python no recalcula el daño. La operación se delega al motor Java mediante el contrato NDJSON existente.

El bridge expone `combat_async()` y ejecuta el I/O bloqueante del subprocess en `asyncio.to_thread()`, evitando bloquear el event loop de aiohttp.

La respuesta se normaliza a `TurnResultDTO` con daño, crítico, HP, versión de estado y eventos/recompensas.

## Telegram Stars

`POST /api/store/invoice`

Usa `TmaStarsService` para crear enlaces de factura con:

- moneda `XTR`;
- precio entero en Stars;
- `LabeledPrice`;
- payload ligado al usuario autenticado;
- sin token de proveedor para el producto digital.

Este componente solo crea invoices. La entrega de Tickets Premium debe permanecer en el flujo de pagos posterior y persistir de forma idempotente el identificador de cobro antes de acreditar el producto.

## GitHub Pages

El workflow de Pages copia los assets de combate y puede inyectar una URL pública mediante la variable de repositorio:

`TMA_API_BASE_URL`

Cuando está definida, el workflow exige:

- URL absoluta;
- esquema HTTPS;
- sin query;
- sin fragment.

El frontend no recibe ningún token.

La variable no se inventa ni se escribe automáticamente porque depende de la infraestructura pública real que el operador elija. Mientras esté vacía, el artifact de Pages queda deliberadamente desacoplado del backend.

## Red

BotManager escucha ahora en `127.0.0.1:8765` por defecto.

Para una Mini App accesible desde Internet se necesita un reverse proxy o túnel HTTPS que publique el API y reenvíe hacia ese listener. `TMA_ALLOWED_ORIGINS` debe contener el origen exacto del frontend de Pages.

## Verificación

CI debe cubrir Maven/JUnit, Ruff, Pytest, validadores de assets y sintaxis JavaScript.

Windows debe cubrir el JAR Java, runtime Java empaquetado, cinco ejecutables, smoke test de BotManager, instalador, ZIP portable y checksums.

La ejecución de Pages debe desplegar el artifact desde el mismo SHA.

## Evidencia del ciclo

SHA objetivo del ciclo:

`44ced2c3d69ba8c25e8e6b5efbae1f60fe9b5217`

Pages:

- workflow #89
- resultado: SUCCESS
- URL del entorno: `https://eltiootaku01-hue.github.io/bot-telegram/`

Las ejecuciones CI y Windows deben verificarse sobre el mismo SHA antes de declarar el ciclo completamente validado.

## Pendientes explícitos

- configurar `TMA_API_BASE_URL` con la URL pública HTTPS real del backend;
- desplegar el reverse proxy/túnel;
- implementar el flujo de `pre_checkout_query` y `successful_payment` con persistencia idempotente de cobros y acreditación de Tickets Premium;
- convertir `state_version` del combate en una versión durable del estado cuando el backend persistente de combate esté listo.
