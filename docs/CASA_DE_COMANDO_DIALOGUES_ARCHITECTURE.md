# Casa de Comando — diálogos locales y control del Café Otaku

## Objetivo

La conversación de rutina no depende de un servicio generativo. Las frases authored están en config/dialogues.json, se cargan desde disco y se seleccionan localmente.

Esto permite cero llamadas LLM para la selección de frases, funcionamiento con la IA desactivada, edición sin recompilar Python, placeholders explícitos y escritura atómica.

## Eventos soportados

ON_CAMPANA_RUNG, ON_CARD_ROLL, ON_WAIFU_ENCOUNTER, ON_WAIFU_POKER, ON_WELCOME y ON_COOLDOWN.

Identidades válidas: cari, sunna, cami, chie.

## Flujo

Casa de Comando -> DialogueStore -> config/dialogues.json -> DialogueRenderer -> TelegramGateway -> mensaje temporal.

## Clases de diálogo

DialogueEvent: vocabulario cerrado de eventos.
DialogueEntry: frase individual validada.
DialogueCatalog: catálogo validado en memoria.
DialogueStore: lectura, escritura atómica y CRUD.
DialogueRenderer: selección local y expansión segura de variables.

CommandCenterService expone add_dialogue, edit_dialogue, delete_dialogue, dialogue_catalog, render_dialogue y send_dialogue.
TelegramGateway encapsula send_chat_action, send_message, send_photo y autodestrucción temporal.

## Cuatro tablas principales de la Bóveda

### card_definitions

CREATE TABLE card_definitions (id TEXT PRIMARY KEY, card_code TEXT UNIQUE, character_id TEXT NOT NULL, character_name TEXT NOT NULL, anime_origin TEXT NOT NULL, rarity TEXT NOT NULL CHECK (rarity IN ('C','R','SR','SSR','UR')), image_url TEXT, asset_path TEXT, thumbnail_path TEXT, asset_sha256 TEXT, source_provider TEXT NOT NULL DEFAULT 'local', collection_points INTEGER NOT NULL DEFAULT 0 CHECK (collection_points >= 0), coin_value INTEGER NOT NULL DEFAULT 0 CHECK (coin_value >= 0), telegram_protected INTEGER NOT NULL DEFAULT 1 CHECK (telegram_protected IN (0,1)), custom_emoji_id TEXT, active INTEGER NOT NULL DEFAULT 1, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL);

### card_inventory

CREATE TABLE card_inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT NOT NULL REFERENCES card_definitions(id) ON DELETE CASCADE, holder_type TEXT NOT NULL CHECK (holder_type IN ('user','bank','bot')), holder_key TEXT NOT NULL, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, quantity INTEGER NOT NULL DEFAULT 0, locked_quantity INTEGER NOT NULL DEFAULT 0, updated_at DATETIME NOT NULL, CHECK (quantity >= 0 AND locked_quantity >= 0 AND locked_quantity <= quantity), UNIQUE(holder_type, holder_key, card_id));

### bot_states

CREATE TABLE bot_states (id INTEGER PRIMARY KEY AUTOINCREMENT, bot_identity TEXT NOT NULL UNIQUE, mode TEXT NOT NULL DEFAULT 'automatic' CHECK (mode IN ('manual','automatic')), status TEXT NOT NULL DEFAULT 'idle', zone_key TEXT NOT NULL DEFAULT 'cafe', table_key TEXT, chat_id INTEGER, message_thread_id INTEGER, position_x INTEGER NOT NULL DEFAULT 0, position_y INTEGER NOT NULL DEFAULT 0, energy INTEGER NOT NULL DEFAULT 100 CHECK (energy >= 0), cooldown_until DATETIME, state_json TEXT NOT NULL DEFAULT '{}', updated_at DATETIME NOT NULL);

### transaction_history

CREATE TABLE transaction_history (id INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT NOT NULL UNIQUE, transaction_type TEXT NOT NULL, actor_user_id INTEGER, target_user_id INTEGER, card_id TEXT, quantity INTEGER NOT NULL DEFAULT 0, coin_delta INTEGER NOT NULL DEFAULT 0, card_delta INTEGER NOT NULL DEFAULT 0, source TEXT NOT NULL DEFAULT 'system', reference_type TEXT, reference_id TEXT, metadata_json TEXT NOT NULL DEFAULT '{}', created_at DATETIME NOT NULL, CHECK (coin_delta <> 0 OR card_delta <> 0), CHECK (card_delta = 0 OR card_id IS NOT NULL));

El ledger es append-only mediante triggers SQLite; transferencias y recompensas usan claves idempotentes.

## Clases de conexión

Casa de Comando: CommandCenterService + TelegramGateway + CardVaultClient + DialogueStore/DialogueRenderer.
Bot Bóveda: VaultApiServer + CardVaultService.
SQLite: BotState, CardInventory y TransactionHistory, junto con CardDefinition.

Casa de Comando no escribe directamente el inventario de cartas: usa CardVaultClient. La Bóveda mantiene la autoridad sobre cartas, assets, thumbnails, inventario y ledger.

## Protección de cartas

TelegramGateway.send_card usa protect_content=True por defecto. El valor persistido telegram_protected indica la política de la carta; la API de Telegram devuelve la propiedad has_protected_content en el mensaje.

## Límite deliberado

dialogues.json controla frases authored y eventos operativos; no sustituye el canon narrativo. La IA, cuando exista, permanece fuera de la ruta crítica de conversación authored.