-- Migration: Create telegram_sessions table
-- Created: 2026-10-12 01:50:00 BRT (1791780600)

CREATE TABLE "telegram_sessions" (
    "id"          TEXT NOT NULL DEFAULT '',
    "phone"       TEXT NOT NULL,
    "session_id"  TEXT NOT NULL,
    "phone_code_hash" TEXT NOT NULL DEFAULT '',
    "webhook_url" TEXT NOT NULL DEFAULT '',
    "active"      INTEGER NOT NULL DEFAULT 1,
    "api_id"      INTEGER NOT NULL DEFAULT 0,
    "api_hash"    TEXT NOT NULL DEFAULT '',
    "created"     TEXT NOT NULL DEFAULT (datetime('now')),
    "updated"     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY ("id")
);

-- Index para session_id único
CREATE UNIQUE INDEX "idx_telegram_sessions_session_id" ON "telegram_sessions" ("session_id");

-- Index para phone único
CREATE UNIQUE INDEX "idx_telegram_sessions_phone" ON "telegram_sessions" ("phone");

-- Trigger para atualizar 'updated' automaticamente
CREATE TRIGGER "telegram_sessions_updated_at" 
AFTER UPDATE ON "telegram_sessions" 
BEGIN
    UPDATE "telegram_sessions" SET "updated" = datetime('now') WHERE "id" = NEW."id";
END;
