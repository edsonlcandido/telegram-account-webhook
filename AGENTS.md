# Telegram Account Webhook - Agent Guide

## Overview

Sistema para vincular contas Telegram e receber mensagens via webhook.

## Architecture

```
Usuário → Frontend (Vue) → Backend (Python) → Telegram API
                          ↓
                    PocketBase (store)
                          ↓
                    Webhook (cliente)
```

## Stack

- **Frontend**: Vue 3 + TypeScript + Vite
- **Backend**: Python + FastAPI + Telethon
- **Database**: PocketBase (https://iptv.ehtudo.app)

## Project Structure

```
telegram-account-webhook/
├── src/                          # Vue Frontend
│   ├── main.ts                   # Entry point
│   ├── App.vue                   # Root component (tabs navigation)
│   ├── api/index.ts              # API clients (PocketBase + Backend)
│   ├── types/index.ts            # TypeScript interfaces
│   ├── composables/
│   │   └── useTelegram.ts        # Auth & account management
│   └── components/
│       ├── AccountForm.vue       # Link Telegram account (phone + api_id/hash)
│       ├── SessionList.vue       # List linked accounts
│       └── WebhookConfig.vue     # Configure webhook URL + filter
├── backend/
│   ├── main.py                   # FastAPI app (routes)
│   ├── telethon_manager.py       # Telethon client management
│   └── webhook_sender.py         # HTTP webhook delivery
├── index.html
├── package.json
├── Dockerfile
└── AGENTS.md
```

## Features

- ✅ Vincular conta Telegram via api_id/api_hash
- ✅ Verificação em 2 fatores
- ✅ Configurar webhook para receber mensagens
- ✅ Filtrar por tipo de chat (pessoal/grupo/canal)
- ✅ Testar webhook
- ✅ Gerenciar múltiplas contas

## Environment Variables

### Backend (.env)
```env
POCKETBASE_URL=https://iptv.ehtudo.app
POCKETBASE_TOKEN=***
SESSION_DIR=/app/sessions
```

### Frontend (.env)
```env
VITE_PB_URL=https://iptv.ehtudo.app
VITE_PB_TOKEN=***
VITE_BACKEND_URL=http://localhost:8000
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/send-code | Send verification code |
| POST | /api/auth/verify | Verify code and create session |
| GET | /api/session/status | Session status |
| POST | /api/webhook/configure | Configure webhook |
| POST | /api/webhook/test | Test webhook |
| POST | /api/session/disconnect | Disconnect session |
| GET | /health | Health check |

## PocketBase Collections

- `telegram_accounts`: Stores account credentials
- `telegram_sessions`: Session metadata
- `telegram_webhooks`: Webhook configurations
- `telegram_messages`: Received messages

## Key Files

### Frontend Components

1. **AccountForm.vue**: 3-step wizard
   - Step 1: Enter phone + api_id + api_hash
   - Step 2: Enter verification code
   - Step 3: Success

2. **SessionList.vue**: Displays linked accounts with delete option

3. **WebhookConfig.vue**: Configure webhook URL + chat type filter

### Backend (telethon_manager.py)

- Manages Telethon client sessions
- Handles auth flow (send_code → verify_code)
- Monitors messages and forwards to webhook
- In-memory session storage

## Development

```bash
# Frontend
npm install
npm run dev

# Backend
cd backend
pip install -r requirements.txt
python main.py
```

## Deploy

Webhook endpoint for auto-deploy:
```
http://82.112.244.9:3000/api/deploy/d08148ad7475ab169bc6b4baac629cc1c0e18c900b11d525
```

Push to `main` branch triggers deploy automatically.

## Important Notes

1. Sessions stored in `/app/sessions` directory (Docker volume)
2. Backend runs on port 8000
3. CORS enabled for all origins
4. Webhook filter types: `pessoal`, `grupo`, `canal`, `all`
5. Telegram API credentials required from https://my.telegram.org
