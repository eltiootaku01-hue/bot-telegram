-- -*- coding: utf-8 -*-
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    telegram_id TEXT PRIMARY KEY,
    username TEXT,
    chocolates_balance INTEGER NOT NULL DEFAULT 0 CHECK (chocolates_balance >= 0),
    daily_free_uses INTEGER NOT NULL DEFAULT 2 CHECK (daily_free_uses BETWEEN 0 AND 2),
    last_daily_reset TEXT
);

CREATE TABLE IF NOT EXISTS user_inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT NOT NULL,
    item_type TEXT NOT NULL CHECK (item_type IN ('CARD','DRINK','SPECIAL')),
    item_name TEXT NOT NULL,
    rarity TEXT NOT NULL CHECK (rarity IN ('N','R','SR','SSR')),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 0),
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
    UNIQUE (telegram_id, item_type, item_name, rarity)
);

CREATE TABLE IF NOT EXISTS waitresses (
    waitress_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('novice','supervisor')),
    shift_type TEXT NOT NULL CHECK (shift_type IN ('DAY','NIGHT','ALL_NIGHT')),
    shift_start_hour INTEGER NOT NULL CHECK (shift_start_hour BETWEEN 0 AND 23),
    shift_end_hour INTEGER NOT NULL CHECK (shift_end_hour BETWEEN 0 AND 23),
    is_busy INTEGER NOT NULL DEFAULT 0 CHECK (is_busy IN (0,1)),
    is_resting INTEGER NOT NULL DEFAULT 0 CHECK (is_resting IN (0,1)),
    last_ticket_at TEXT,
    personality_prompt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS active_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT NOT NULL,
    waitress_id TEXT NOT NULL,
    session_type TEXT NOT NULL CHECK (session_type IN ('STANDARD_3MIN','FAVORITE_5MIN')),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
    FOREIGN KEY (waitress_id) REFERENCES waitresses(waitress_id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_active_session_user
ON active_sessions(telegram_id) WHERE is_active = 1;

CREATE UNIQUE INDEX IF NOT EXISTS ux_active_session_waitress
ON active_sessions(waitress_id) WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS ix_inventory_user
ON user_inventory(telegram_id, item_type, rarity);

CREATE INDEX IF NOT EXISTS ix_sessions_user
ON active_sessions(telegram_id, is_active, end_time);

CREATE INDEX IF NOT EXISTS ix_sessions_waitress
ON active_sessions(waitress_id, is_active, end_time);

CREATE TABLE IF NOT EXISTS supervisor_directives (
    directive_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_waitress_id TEXT NOT NULL,
    directive_text TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    FOREIGN KEY (target_waitress_id) REFERENCES waitresses(waitress_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_directives_waitress
ON supervisor_directives(target_waitress_id, is_active, applied_at);

INSERT OR IGNORE INTO waitresses
(waitress_id,display_name,role,shift_type,shift_start_hour,shift_end_hour,is_busy,is_resting,personality_prompt)
VALUES
('cari','Cari','novice','DAY',10,18,0,0,'Profesional, atenta, servicial, amigable y algo novata.'),
('luna','Luna','novice','DAY',10,18,0,0,'Amable, tranquila, servicial y cordial durante todo el turno.'),
('scarlet','Scarlet','novice','NIGHT',18,2,0,0,'Profesional, despierta, directa y amable durante el turno nocturno.'),
('chloe','Chloe','novice','NIGHT',18,2,0,0,'Alegre, sociable, servicial y energética durante el turno nocturno.'),
('mama_mia','Mama Mia','supervisor','ALL_NIGHT',0,0,0,0,'Supervisora firme, protectora y orientada a mantener seguridad, rol y continuidad.');


CREATE TABLE IF NOT EXISTS telegram_outbox (
    update_id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    payload TEXT NOT NULL,
    next_chunk INTEGER NOT NULL DEFAULT 0 CHECK (next_chunk >= 0),
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'DELIVERED', 'FAILED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_telegram_outbox_status
ON telegram_outbox(status, created_at);
