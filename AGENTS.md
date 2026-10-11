# Telegram Account Webhook

Sistema para conectar contas Telegram e enviar mensagens em tempo real via webhook.

## Arquitetura

```
Usuário → Frontend (Vue) → Backend (FastAPI) → Telegram API (Telethon)
                                       ↓
                              Webhook → Cliente (seu servidor)
```

## Stack

- **Frontend**: Vue 3 + TypeScript + Vite
- **Backend**: Python + FastAPI + Telethon
- **Auth**: JWT tokens (gerados no backend)

## Projeto NÃO usa PocketBase

Este é um projeto independente. Não usa banco de dados externo.
Os dados são armazenados em memória (RAM) no backend + arquivos de sessão do Telethon.

## Estrutura

```
telegram-account-webhook/
├── src/                          # Frontend Vue
│   ├── main.ts
│   ├── App.vue                   # Landing page + Dashboard
│   ├── views/
│   │   ├── LandingView.vue       # Landing page (descrição do serviço)
│   │   └── DashboardView.vue    # Painel após login
│   ├── components/
│   │   ├── AccountForm.vue      # Vincular conta Telegram
│   │   ├── SessionList.vue      # Lista de contas
│   │   └── WebhookConfig.vue    # Configurar webhook
│   ├── api/
│   │   └── index.ts             # API client (backend)
│   ├── types/
│   │   └── index.ts
│   └── composables/
│       └── useTelegram.ts
├── backend/
│   ├── main.py                  # FastAPI app
│   ├── telethon_manager.py      # Gerencia sessões Telethon
│   ├── webhook_sender.py        # Envia mensagens para webhook
│   └── auth.py                  # JWT authentication
├── Dockerfile
└── AGENTS.md
```

## Funcionalidades

- ✅ Vincular conta Telegram via phone + api_id/api_hash
- ✅ Verificação em 2 fatores (código SMS/Telegram)
- ✅ Configurar URL de webhook
- ✅ Filtrar por tipo: pessoal, grupo, canal, todos
- ✅ Testar se webhook está respondendo
- ✅ Múltiplas contas por usuário
- ✅ Landing page para apresentar o serviço

## Fluxo de Uso

1. Usuário acessa landing page
2. Faz login/cadastro (simples, sem banco)
3. Vincula conta Telegram
4. Recebe código no Telegram/SMS
5. Configura URL do webhook
6. Sistema começa a enviar mensagens em tempo real

## API Endpoints (Backend)

| Method | Endpoint | Descrição |
|--------|----------|-----------|
| POST | /api/auth/register | Cadastro simples |
| POST | /api/auth/login | Login (retorna JWT) |
| POST | /api/telegram/send-code | Envia código Telegram |
| POST | /api/telegram/verify | Verifica código |
| GET | /api/telegram/accounts | Lista contas do usuário |
| DELETE | /api/telegram/accounts/:id | Remove conta |
| POST | /api/webhook/configure | Configura webhook |
| POST | /api/webhook/test | Testa webhook |
| GET | /health | Health check |

## Payload Enviado ao Webhook

```json
{
  "event": "new_message",
  "account_id": "user_123",
  "chat_id": -100123456,
  "chat_name": "Nome do Grupo",
  "chat_type": "grupo",
  "message_id": 123,
  "from_name": "João Silva",
  "from_id": 999,
  "text": "Olá!",
  "date": "2024-01-15T10:30:00Z",
  "has_media": false
}
```

## Configuração Telethon

O Telethon usa:
- `api_id` e `api_hash` (obtidos em https://my.telegram.org)
- Arquivos de sessão salvos em `/app/sessions/`
- Scopes:读取 mensajes,enviar mensajes

## Desenvolvimento

```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend
npm install
npm run dev
```

## Deploy (Docker)

```bash
docker build -t telegram-webhook .
docker run -p 8000:8000 -v ./sessions:/app/sessions telegram-webhook
```

## Variáveis de Ambiente

```env
# Backend
JWT_SECRET=your-secret-key
SESSION_DIR=/app/sessions

# Frontend  
VITE_API_URL=http://localhost:8000
```

## Importante

- Sistema stateless (sem banco de dados)
- Sessões Telethon persistidas em disco
- JWT para autenticação simples
- Webhook é only-envio (não recebe comandos de volta)
