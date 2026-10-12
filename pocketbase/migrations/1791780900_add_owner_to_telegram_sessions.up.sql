-- Migration: Add owner relation to telegram_sessions
-- Created: 2026-10-12 01:55:00 BRT (1791780900)

-- Adiciona coluna owner (relaciona com users)
ALTER TABLE "telegram_sessions" ADD COLUMN "owner" TEXT DEFAULT '';

-- Cria índice para buscar sessões por usuário
CREATE INDEX "idx_telegram_sessions_owner" ON "telegram_sessions" ("owner");

-- Adiciona constraint de foreign key (ignora erro se já existir)
-- A constraint será criada separadamente via API do PocketBase
