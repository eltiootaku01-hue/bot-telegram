# Telegram Mini App — puente Python/Java

## Arquitectura

```
Telegram Mini App
      |
      | HTTPS + Telegram.WebApp.initData
      v
GitHub Pages (webapp/)
      |
      | X-Telegram-Init-Data
      v
Bot Manager / aiohttp
      |
      +--> HMAC + auth_date + CORS
      |
      +--> SQLite / GameProfile / GameCollection / SetupSession
      |
      +--> WaifuMonJavaEngine
      |        |
      |        +--> WaifuMonRuleEngine.java
      |
      +--> Telegram Bot API (Stars)
```

## Contrato de autenticación

El navegador nunca envía un ID de usuario como credencial. En cada GET/POST protegido envía el valor crudo de `Telegram.WebApp.initData`. Python recalcula el HMAC con el token del bot configurado en `TMA_BOT_IDENTITY` y rechaza firmas inválidas o `auth_date` fuera de la ventana configurada.

El frontend puede utilizar `initDataUnsafe` solamente para presentación local, como nombre visible o tema; las decisiones de autorización del servidor usan exclusivamente el contexto validado por HMAC.

## Endpoints

### GET /api/combat/init

Entrega:

- versión de contrato;
- `player_id` validado por Telegram;
- comunidad configurada y autorizada;
- equipo derivado de `GameCollection`;
- oponente de entrenamiento cuando todavía no existe una colección;
- contrato de assets con rutas de cartas y sprites;
- tamaño de sprite: 128×128;
- poses: idle / attack / hit.

### POST /api/combat/action

Recibe:

- acción `attack|special|defend`;
- atacante;
- defensor;
- `turn_id`;
- clave de idempotencia.

El servidor verifica propiedad del atacante y genera una clave de idempotencia con usuario + comunidad antes de delegar al motor Java. El Python no recalcula el daño.

La respuesta conserva:

- daño;
- crítico;
- HP restante;
- versión de estado;
- IDs de eventos;
- IDs de recompensas.

### POST /api/store/invoice

Genera una factura digital mediante `createInvoiceLink`:

- moneda: `XTR`;
- un solo precio `LabeledPrice`;
- `provider_token` omitido para Stars;
- payload asociado al usuario validado.

La entrega del producto todavía no se realiza en este endpoint: el siguiente bloque de monetización debe manejar `pre_checkout_query`, `successful_payment` y persistir el identificador de cobro antes de acreditar Tickets Premium.

## Assets

El servidor devuelve rutas bajo:

`<TMA_FRONTEND_BASE_URL>/assets/production/cards/`

y

`<TMA_FRONTEND_BASE_URL>/assets/production/sprites/`

El workflow de Pages copia `assets/production` a `webapp/assets/production` antes de subir el artifact, de modo que las mismas rutas estén disponibles en el sitio publicado.

## Red y despliegue

Bot Manager escucha en `TMA_API_HOST:TMA_API_PORT`. Para usarlo desde GitHub Pages en producción, el API debe ser accesible mediante HTTPS desde Internet. El puerto local de aiohttp está pensado para estar detrás de un reverse proxy/TLS o túnel controlado. `TMA_ALLOWED_ORIGINS` debe contener únicamente los orígenes reales del frontend.

No se debe colocar ningún token de Telegram en JavaScript ni dentro del artifact de Pages.

## Verificación

La integración automatizada valida:

- HMAC válido;
- HMAC alterado;
- `auth_date` expirado;
- presencia de `signature` dentro del conjunto HMAC del backend;
- rechazo sin initData;
- CORS/origen;
- DTO de combate;
- propagación de usuario/comunidad/idempotencia al motor;
- flujo HTTP contra el engine Java real cuando el JAR ya fue compilado;
- invoice XTR sin provider token;
- sintaxis JavaScript de `main.js`, `combat.js` y `api.js`;
- empaquetado Windows del Bot Manager, cuatro bots, WorldBot y runtime Java.
