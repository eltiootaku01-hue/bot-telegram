# Card Vault + Casa de Comando

## Topología

Casa de Comando (GUI 2D) -> loopback HTTP JSON -> Card Vault
Casa de Comando (GUI 2D) -> TelegramGateway -> Telegram Bot API
Card Vault -> SQLite + data/card_assets + data/card_thumbnails

## Cuatro tablas principales

### card_definitions
Catálogo autoritativo de cartas. Incluye ID interno, card_code (#001), personaje, anime, rareza, asset_path, thumbnail_path, SHA-256, valor en Café Coins, política de protección y custom_emoji_id.

Valores iniciales: C=1, R=5, SR=15, SSR=40, UR=100.

### card_inventory
Representa inventario de usuario, pozo de Banca o inventario de una bot. holder_type distingue user, bank y bot; locked_quantity permite reservar cartas para partidas.

### bot_states
Persiste modo manual/automático, estado, zona, mesa, chat_id, message_thread_id, posición 2D, energía y cooldown.

### transaction_history
Ledger append-only. Cada operación relevante usa una idempotency_key única. SQLite impide UPDATE y DELETE mediante triggers.

## Clases

CardVaultService: valida y registra assets, crea thumbnails, consulta inventarios y ejecuta transferencias idempotentes.
VaultApiServer: API local en 127.0.0.1:8765.
CardVaultClient: cliente asíncrono de la Casa de Comando.
TelegramGateway: encapsula send_chat_action, send_message, send_photo y autodestrucción de mensajes.
CommandCenterService: capa de aplicación para mover avatares, cambiar modo, enviar acciones manuales y consultar Bóveda.

## Protección Telegram
Para publicar una carta protegida el adapter debe enviar protect_content=True. Telegram devuelve has_protected_content como propiedad del mensaje protegido; no es un argumento de envío.

## Waifu Poker
locked_quantity reserva cartas durante una mano. Si una carta se pierde contra una bot, el destino lógico puede ser holder_type=bank para su recirculación.
## API local para el runner Multi-Bot

La Bóveda expone, además de sus rutas /v1, compatibilidad para el runner multibot:

- GET /api/inventory/{user_id} — inventario de un jugador.
- POST /api/cards/transfer — movimiento de cartas; acepta idempotency_key y lo convierte en la referencia durable del ledger.
- GET /api/cards/lock-status — cantidad total, bloqueada y disponible por holding.
- GET /api/balance/{user_id} — saldo derivado del ledger de Café Coins.
- GET /v1/cards — catálogo activo de definiciones.

En la configuración actual, Telegram Mini App usa 127.0.0.1:8765 y la Bóveda usa 127.0.0.1:8766. El puerto de Bóveda es configurable mediante VAULT_API_URL.

El runner multibot no accede directamente a SQLite para entregar cartas: consulta a la Bóveda y utiliza transferencias idempotentes.
