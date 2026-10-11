# Telegram Account Webhook

Vincule contas Telegram e receba mensagens em tempo real via webhook.

## O que faz

- **Vincular conta Telegram**: phone_number + código de verificação
- **Receber mensagens**: webhook URL para cada conta
- **Gerenciar múltiplas contas**: painel unificado

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                        Easypanel VPS                        │
│                                                             │
│  ┌─────────────┐              ┌─────────────────────────┐  │
│  │  PocketBase │              │    FastAPI + Telethon   │  │
│  │  (Container)│◄────────────►│       (Container)       │  │
│  │    :8090   │   HTTP/WS    │         :8000          │  │
│  └──────┬──────┘              └───────────┬─────────────┘  │
│         │                                  │               │
│         ▼                                  ▼               │
│  ┌─────────────┐                   ┌─────────────┐        │
│  │   Vue Web   │                   │   Cliente   │        │
│  │   (Static) │                   │  (Webhook)  │        │
│  └─────────────┘                   └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Container 1: PocketBase
- Database e autenticação
- Serve o frontend Vue (SPA)
- Porta: 8090

### Container 2: FastAPI (Python)
- Gerencia sessões Telethon
- Escuta eventos em tempo real
- Forward para webhooks dos clientes
- Porta: 8000

## Tech Stack

| Camada      | Tecnologia                    |
|-------------|-------------------------------|
| Frontend    | Vue 3 + TypeScript + Tailwind |
| Backend API | Python + FastAPI + Telethon   |
| Database    | PocketBase                    |
| Deploy      | Easypanel (VPS)              |

## Desenvolvimento Local

```bash
# Backend Python
cd backend
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (em outro terminal)
cd apps/web
npm install
npm run dev

# PocketBase
./pocketbase/pocketbase serve
```

## Deploy no Easypanel

### Container 1: PocketBase
- **Imagem**: `ghcr.io/edsonlcandido/telegram-account-webhook:latest`
- **Porta**: 8090
- **Volume**: `pb_data`

### Container 2: FastAPI
- **Imagem**: `python:3.11-slim`
- **Porta**: 8000
- **Build**: `docker build -f backend/Dockerfile -t fastapi-telegram .`

### Configuração

Defina a variável de ambiente:
```
POCKETBASE_URL=http://<ip-vps>:8090
```

## Status

⚠️ **Em desenvolvimento**

## License

MIT
