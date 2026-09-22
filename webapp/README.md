# WaifuMon Telegram Mini App

Frontend estático sin framework para GitHub Pages.

## Estructura

- `index.html` — shell de la Mini App y carga del SDK oficial de Telegram.
- `css/style.css` — layout mobile-first, tema dinámico y safe areas.
- `js/main.js` — inicialización Telegram, equipo, acciones visuales, tienda y referidos.
- `js/combat.js` — Canvas 2D, carga de sprites 128×128 y cut-in HD de 1.5 s.
- `js/effects.js` — partículas y destellos de combate originales, con límite de 96 partículas y sin dependencias externas.
- `index.html` + `css/style.css` + `js/main.js` — carta TCG holográfica bōsōzoku: marco recortado, foil violeta/rojo y control por puntero o DeviceOrientation con permiso explícito cuando el navegador lo exige.

Los assets de combate se resuelven desde:

`assets/production/sprites/<id>_<idle|attack|hit>.png`

Las cartas HD se resuelven desde:

`assets/production/cards/<id>--normal.jpg`

El frontend no contiene la autoridad del combate, puntos, inventario ni pagos.

## GitHub Pages

El workflow `.github/workflows/deploy-pages.yml` publica `webapp/` en cada push a `main`.

La primera activación debe hacerse una vez en el repositorio: **Settings → Pages → Build and deployment → Source → GitHub Actions**. GitHub documenta esta configuración como requisito para publicar mediante un workflow personalizado.

Una vez habilitado Pages, los pushes posteriores a `main` activan automáticamente el despliegue.

## Telegram

Configura esta URL como Main Mini App o como botón/menu del bot cuando el sitio esté publicado. Telegram pasa `initData` a la Mini App; el backend debe validar esa cadena antes de confiar en identidad o referidos.

El cliente puede leer `initDataUnsafe` para presentación, pero no debe usarlo como autoridad de autenticación.

## Monetización

La UI de tienda está preparada para productos digitales. Las compras reales deben ser creadas y verificadas por el backend mediante Telegram Stars (XTR).

## Referidos

La UI muestra el objetivo de 3 usuarios nuevos para obtener 1 Ticket Premium. El conteo y la concesión deben vivir en servidor y ser idempotentes.


## Backend TMA API

El cliente usa `js/api.js` y envía el valor crudo de `Telegram.WebApp.initData` en el header `X-Telegram-Init-Data`. El backend rechaza cada GET/POST sin una firma HMAC válida o con `auth_date` fuera de la ventana configurada.

Rutas implementadas:

- `GET /api/combat/init` — identidad autenticada, comunidad autorizada, roster y contrato de assets.
- `POST /api/combat/action` — acción de combate validada por el servidor y delegada al motor Java.
- `POST /api/store/invoice` — genera una invoice de producto digital en Telegram Stars (XTR).

La URL del backend puede fijarse mediante la variable de repositorio `TMA_API_BASE_URL`. El workflow de GitHub Pages la inyecta durante el build; solamente se aceptan URLs absolutas HTTPS. No existe un override por query-string para impedir que un enlace arbitrario redirija `initData` a un tercero. No se guarda ningún token en el frontend.

### Bot Manager

Bot Manager levanta el servicio aiohttp cuando `TMA_API_ENABLED=true`. El host y puerto salen de `TMA_API_HOST` y `TMA_API_PORT`; para un backend accesible desde GitHub Pages se necesita exponer ese servicio detrás de HTTPS y configurar `TMA_ALLOWED_ORIGINS` con el origen exacto de Pages.

### Telegram Mini App auth

No uses `initDataUnsafe` como credencial. El servidor recalcula el HMAC-SHA-256 de `initData`, comprueba `auth_date` y extrae el `user.id` validado. Ese ID es el que se propaga al motor Java para el contexto del turno.

El preflight CORS `OPTIONS` es una operación de navegador, no una llamada de negocio: se responde sin HMAC para que el navegador pueda negociar el header personalizado. Todas las rutas de negocio GET/POST siguen obligatoriamente el middleware HMAC.

### Telegram Stars

La API usa `createInvoiceLink` con `currency="XTR"` y precio entero en Stars. Para productos digitales Telegram exige XTR y no requiere un `provider_token`. El endpoint devuelve únicamente el enlace de pago; la entrega de Tickets Premium todavía debe ocurrir después de procesar `pre_checkout_query` y `successful_payment` en el bot y persistir el identificador de la transacción antes de acreditar el producto.
