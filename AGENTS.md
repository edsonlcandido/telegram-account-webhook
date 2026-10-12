# Telegram Account Webhook

Sistema para conectar contas Telegram e enviar mensagens em tempo real via webhook.

## Arquitetura

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Easypanel VPS                               │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Serviço 1: Application                                         │ │
│  │  ────────────────────────────────────────────────────────────   │ │
│  │  • PocketBase :8090                                            │ │
│  │  • Landing Page /                                              │ │
│  │  • Web App /app/                                              │ │
│  │                                                                 │ │
│  │  TELEGRAM_API_URL=http://telegram-api:8000                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                              │                                      │
│                              │ HTTP (interno)                        │
│                              ▼                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Serviço 2: Telegram API                                       │ │
│  │  ────────────────────────────────────────────────────────────   │ │
│  │  • FastAPI :8000                                               │ │
│  │  • Telethon                                                    │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

## Estrutura

```
telegram-account-webhook/
├── Dockerfile.Application          # PocketBase + Frontend Vue
├── Dockerfile.Telegram             # FastAPI + Telethon
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── apps/
│   ├── landing/                    # Landing page
│   └── web/                        # Web app Vue
├── pocketbase/
│   ├── pb_hooks/                  # SPA routing hooks
│   │   └── main.pb.js
│   └── pb_migrations/
├── .agents/
│   └── skills/
│       └── pocketbase-gotchas.md   # PocketBase 0.40.x gotchas
├── docker-compose.yml
└── README.md
```

## Deploy

**Webhook para deploy automático:**
```
http://82.112.244.9:3000/api/deploy/d08148ad7475ab169bc6b4baac629cc1c0e18c900b11d525
```

Push para `main` = deploy automático via Easypanel.

## Variáveis de Ambiente

### Serviço Application (PocketBase)

```env
TELEGRAM_API_URL=http://telegram-api:8000    # URL do Telegram API (interno Docker)
```

### Serviço Telegram API

```env
POCKETBASE_URL=http://pocketbase:8090         # URL do PocketBase (interno Docker)
TG_API_ID=123456
TG_API_HASH=abc123...
```

## Coleções PocketBase

- `users`: Usuários (auth nativo)
- `telegram_accounts`: phone, api_id, api_hash, is_authorized
- `webhooks`: webhook_url, filter_tipo, account_id

## API Backend

| Method | Endpoint | Descrição |
|--------|----------|-----------|
| POST | /api/auth/send-code | Envia código Telegram |
| POST | /api/auth/verify | Verifica código |
| POST | /api/webhook/configure | Configura webhook |
| GET | /health | Health check |

## Comandos

```bash
# Dev
npm run dev          # Roda tudo

# Build
npm run build        # Builda landing + web

# Preview
npm run preview      # Preview do PocketBase
```

## Importante

- Deploy via Easypanel (VPS)
- Backend Python FastAPI em `backend/`
- PocketBase 0.40.5 standalone
- Rede Docker interna para comunicação entre serviços
