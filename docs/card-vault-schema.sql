-- Card Vault / Café Coins control-plane schema.
-- SQLite is configured by app.db.database with foreign_keys=ON and WAL.
-- The application also adds compatibility columns to existing databases.

CREATE TABLE IF NOT EXISTS card_definitions (
    id TEXT PRIMARY KEY,
    card_code TEXT UNIQUE,
    character_id TEXT NOT NULL,
    character_name TEXT NOT NULL,
    anime_origin TEXT NOT NULL,
    rarity TEXT NOT NULL CHECK (rarity IN ('C','R','SR','SSR','UR')),
    image_url TEXT,
    asset_path TEXT,
    thumbnail_path TEXT,
    asset_sha256 TEXT,
    source_provider TEXT NOT NULL DEFAULT 'local',
    collection_points INTEGER NOT NULL DEFAULT 0 CHECK (collection_points >= 0),
    coin_value INTEGER NOT NULL DEFAULT 0 CHECK (coin_value >= 0),
    telegram_protected INTEGER NOT NULL DEFAULT 1 CHECK (telegram_protected IN (0,1)),
    custom_emoji_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS card_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL REFERENCES card_definitions(id) ON DELETE CASCADE,
    holder_type TEXT NOT NULL CHECK (holder_type IN ('user','bank','bot')),
    holder_key TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 0,
    locked_quantity INTEGER NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL,
    CHECK (quantity >= 0 AND locked_quantity >= 0 AND locked_quantity <= quantity),
    UNIQUE(holder_type, holder_key, card_id)
);

CREATE TABLE IF NOT EXISTS bot_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_identity TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL DEFAULT 'automatic' CHECK (mode IN ('manual','automatic')),
    status TEXT NOT NULL DEFAULT 'idle',
    zone_key TEXT NOT NULL DEFAULT 'cafe',
    table_key TEXT,
    chat_id INTEGER,
    message_thread_id INTEGER,
    position_x INTEGER NOT NULL DEFAULT 0,
    position_y INTEGER NOT NULL DEFAULT 0,
    energy INTEGER NOT NULL DEFAULT 100 CHECK (energy >= 0),
    cooldown_until DATETIME,
    state_json TEXT NOT NULL DEFAULT '{}',
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS transaction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT NOT NULL UNIQUE,
    transaction_type TEXT NOT NULL,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    target_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    card_id TEXT REFERENCES card_definitions(id) ON DELETE SET NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    coin_delta INTEGER NOT NULL DEFAULT 0,
    card_delta INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'system',
    reference_type TEXT,
    reference_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at DATETIME NOT NULL,
    CHECK (coin_delta <> 0 OR card_delta <> 0),
    CHECK (card_delta = 0 OR card_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_card_inventory_user
    ON card_inventory(user_id, card_id);

CREATE INDEX IF NOT EXISTS idx_card_inventory_holder
    ON card_inventory(holder_type, holder_key);

CREATE INDEX IF NOT EXISTS idx_transaction_history_card
    ON transaction_history(card_id, created_at);

CREATE INDEX IF NOT EXISTS idx_transaction_history_actor
    ON transaction_history(actor_user_id, created_at);

-- Audit history is append-only. The runtime additionally creates these triggers.
CREATE TRIGGER IF NOT EXISTS trg_transaction_history_no_update
BEFORE UPDATE ON transaction_history
BEGIN
    SELECT RAISE(ABORT, 'transaction_history is immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_transaction_history_no_delete
BEFORE DELETE ON transaction_history
BEGIN
    SELECT RAISE(ABORT, 'transaction_history is immutable');
END;
