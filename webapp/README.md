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

## Creador de cartas IA

La sección `CREADOR DE BARAJAS & CARTAS IA` de `index.html` se muestra únicamente después de que el backend confirme que el usuario autenticado coincide con `ADMIN_USER_ID`. El formulario envía una imagen JPG/PNG/WEBP y metadatos; el backend genera el ID de la carta, guarda el arte en `CARD_ASSETS_DIR` y crea una fila en `card_definitions` con `active=true`. El comando Telegram `/roll` consulta ese catálogo activo en cada ejecución, por lo que una carta nueva queda disponible sin reiniciar el bot ni editar un JSON paralelo.

El registro persistido conserva el contrato equivalente a:

```json
{
  "id": "asuna-summer-ssr-02",
  "character_id": "asuna",
  "character_name": "Asuna (Verano)",
  "anime_origin": "Sword Art Online",
  "rarity": "SSR",
  "image_url": "assets/cards/asuna_summer_ssr.jpg",
  "source_provider": "IA (PixAI/Midjourney)",
  "collection_points": 150,
  "active": true
}
```

El endpoint administra únicamente el catálogo; la carta obtenida por `/roll` también se registra en `game_card_collections` y la misma tirada se enlaza con `card_roll_claims` para evitar duplicados cuando Telegram reintenta el mismo mensaje.

## Monetización

La UI de tienda está preparada para productos digitales. Las compras reales deben ser creadas y verificadas por el backend mediante Telegram Stars (XTR).

## Referidos

La UI muestra el objetivo de 3 usuarios nuevos para obtener 1 Ticket Premium. El conteo y la concesión deben vivir en servidor y ser idempotentes.


## Backend TMA API

El cliente usa `js/api.js` y envía el valor crudo de `Telegram.WebApp.initData` en el header `X-Telegram-Init-Data`. El backend rechaza cada GET/POST sin una firma HMAC válida o con `auth_date` fuera de la ventana configurada.

Rutas implementadas:

- `GET /api/combat/init` — identidad autenticada, comunidad autorizada, roster y contrato de assets.
- `GET /api/admin/cards` — lista el pool activo de cartas; requiere `ADMIN_USER_ID` autenticado por Telegram `initData`.
- `POST /api/admin/cards` — recibe multipart con imagen, personaje, anime, rareza, proveedor y puntos de colección; persiste la definición en SQLite y activa la carta inmediatamente para `/roll`.
- `GET /api/cards/assets/<filename>` — sirve los artes de cartas cargados desde `CARD_ASSETS_DIR`.
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

## Demo TCG 3D — perspectiva NIKKE

`nikke_tcg_demo.html` es una demo independiente para probar la mano de cartas TCG con una escena Three.js en tercera persona.

No reemplaza `index.html`. Se abre directamente como:

`webapp/nikke_tcg_demo.html`

La página carga desde CDN:

- Three.js r128
- GLTFLoader r128
- OrbitControls r128

No requiere instalar paquetes JavaScript.

El módulo reutilizable está en:

`webapp/js/equipment_system.js`

El sistema indexa los huesos de un modelo GLTF/GLB y puede montar un arma o accesorio sobre un hueso como `spine`, `hand.r` o `shoulder.l`. También protege contra una carrera en la que el jugador desequipa una carta mientras el asset 3D todavía se está cargando.

Para usar un modelo real, coloca o publica:

`webapp/assets/models/waifu_base.gltf`

y para el cañón:

`webapp/assets/production/models/equipment/shoulder_cannon.gltf`

La demo usa un maniquí local como fallback si el modelo de personaje no existe. Los efectos de cartas son visuales; la autoridad real de inventario, puntos y combate sigue perteneciendo al backend.

### Catálogo de equipamiento TCG

El catálogo oficial de cartas de equipamiento de la demo 3D está en:

`webapp/data/cards_equipment.json`

Cada entrada contiene dos contratos en paralelo:

- **Gameplay:** `rarity`, `cost` y `gameplay_effects`.
- **3D:** `model_url`, `target_bone`, `socket_name`, `offset_position`, `offset_rotation` y `scale`.

El loader reutilizable está en `webapp/js/equipment_catalog.js`. Valida el esquema, evita `card_id` duplicados y convierte la entrada `3d_attachment` al formato esperado por `EquipmentSystem.attachEquipment()`.

La demo `nikke_tcg_demo.html` genera la mano de equipamiento desde ese JSON. Al seleccionar una carta, el navegador usa su `card_id` para montar o desmontar el modelo correspondiente; no existe una segunda configuración hardcodeada del arma.

Los cuatro modelos y cuatro artes indicados por el catálogo todavía deben incorporarse al repositorio/LFS para que los montajes sean visibles con assets reales:

`webapp/assets/production/models/equipment/shoulder_cannon.gltf`
`webapp/assets/production/models/equipment/cyber_wings.gltf`
`webapp/assets/production/models/equipment/vibro_katana.gltf`
`webapp/assets/production/models/equipment/cyber_visor.gltf`

`webapp/assets/production/cards/eq_cannon.jpg`
`webapp/assets/production/cards/eq_wings.jpg`
`webapp/assets/production/cards/eq_katana.jpg`
`webapp/assets/production/cards/eq_visor.jpg`

La ausencia de esos archivos no rompe la demo: `EquipmentSystem` rechaza la carga del asset y la interfaz conserva el estado seguro en lugar de dejar equipamiento fantasma. La lógica de juego autoritativa sigue en backend.

