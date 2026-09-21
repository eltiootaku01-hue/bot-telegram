# WaifuMon Telegram Mini App

Frontend estático sin framework para GitHub Pages.

## Estructura

- `index.html` — shell de la Mini App y carga del SDK oficial de Telegram.
- `css/style.css` — layout mobile-first, tema dinámico y safe areas.
- `js/main.js` — inicialización Telegram, equipo, acciones visuales, tienda y referidos.
- `js/combat.js` — Canvas 2D, carga de sprites 128×128 y cut-in HD de 1.5 s.

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
