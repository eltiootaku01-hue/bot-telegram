# Multi-Bot aiogram 3.x — ejecución opcional

Este repositorio conserva el modo principal de cuatro procesos independientes, pero también incluye un runner multibot opcional basado en un único Dispatcher de aiogram 3.x.

## Estructura equivalente en el repositorio

app/multibot/config.py — CARI_BOT_TOKEN, SUNNA_BOT_TOKEN, CAMI_BOT_TOKEN, CHIE_BOT_TOKEN y VAULT_API_URL.
app/multibot/vault_client.py — cliente aiohttp asíncrono para la Bóveda local.
app/multibot/dialogues/manager.py — adaptador del catálogo local config/dialogues.json.
app/multibot/handlers/sunna.py — /roll y claim:{card_id}.
app/multibot/handlers/cari.py — /poker y /desafio.
app/multibot/handlers/cami.py — /inventario y /catalogo.
app/multibot/handlers/chie.py — /campana, /saldo y /banco.
app/multibot/main.py — crea cuatro Bot, resuelve sus IDs y ejecuta un único Dispatcher.

## Arranque

Instalá el proyecto con `pip install -e .` y asegurá los cuatro tokens. Podés usar los nombres solicitados CARI_BOT_TOKEN, SUNNA_BOT_TOKEN, CAMI_BOT_TOKEN y CHIE_BOT_TOKEN; el runner también acepta BOT_TOKEN_CARI, BOT_TOKEN_SUNNA, BOT_TOKEN_CAMI y BOT_TOKEN_CHIE.

Después ejecutá `community-telegram-multibot` o `python -m app.multibot.main`.

## Aislamiento

Cada router recibe un BotIdentityFilter asociado al ID real obtenido con getMe. Un `/roll` recibido por Cari no entra al router de Sunna aunque ambos compartan el mismo Dispatcher.

El middleware ChatAccessMiddleware y MemberSyncMiddleware siguen aplicándose al Dispatcher para conservar la política central de autorización y sincronización.

## Bóveda

En la arquitectura actual TMA ocupa 127.0.0.1:8765 y la Bóveda ocupa 127.0.0.1:8766 por defecto para evitar una colisión de puertos. `VAULT_API_URL` sigue siendo configurable, de modo que una instalación que reserve 8765 para la Bóveda puede apuntarlo allí.

Compatibilidad de API agregada:

GET /api/inventory/{user_id}
POST /api/cards/transfer con `idempotency_key`
GET /api/cards/lock-status
GET /api/balance/{user_id}
GET /v1/cards

Las transferencias continúan delegadas al ledger autoritativo de la Bóveda y no manipulan inventario directamente desde los handlers.

## Diálogos

`config/dialogues.json` es local y editable. La carga no necesita internet ni IA. El editor de Casa de Comando escribe el JSON mediante reemplazo atómico.

## Nota de despliegue

El modo multibot y el modo actual de cuatro procesos no deben ejecutarse simultáneamente con los mismos tokens: Telegram no permite múltiples procesos de polling concurrentes para un mismo token.

El build Windows existente continúa empaquetando el modo operativo principal y la Casa de Comando; el runner multibot queda disponible como entrada Python para despliegues alternativos.