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
- `telegram_sessions`: phone, session_id, name (alias opcional, editável)
  - Credencial `StringSession` **NÃO** fica aqui — só no `/app/sessions/*.json`.
  - Credenciais do app Telegram (`api_id`/`api_hash`) ficam nos env vars do container (single-app).
- `telegram_webhooks`: name, enabled, url + filtros (direction, chat_type, text_match)
  - Relation com `telegram_sessions` (cascadeDelete). Vários webhooks por sessão.

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

## Workflow obrigatório (build → commit → deploy)

**REGRA: antes de qualquer `git commit` + `git push` que toque em `apps/web/src/**` ou `apps/landing/src/**`, SEMPRE rodar build local. Se quebrar, NÃO COMITAR.**

```bash
# Em PowerShell (npm é bloqueado por ExecutionPolicy; usar cmd.exe /c)
cmd.exe /c "cd /d apps\web && npm run build"
cmd.exe /c "cd /d apps\landing && npm run build"   # só se mexeu na landing
```

O `npm run build` = `vue-tsc && vite build` (TS check + Vite). Se o TS reclamar, o build falha e o deploy do Easypanel (Dockerfile.Application) também vai falhar — usuário fica sem saber.

### Validação no navegador depois do deploy

1. Forçar reload da página (cache do navegador pode segurar o bundle antigo mesmo com hash novo): abrir com `?v=novo` na URL ou `Ctrl+Shift+R`.
2. Confirmar que o `index.html` aponta pro bundle novo:
   ```bash
   curl -s https://telegram-webhook.ehtudo.app/app/ | grep assets
   ```
3. Procurar texto único do que foi mudado no bundle novo:
   ```bash
   curl -s https://telegram-webhook.ehtudo.app/app/assets/index-XXXXX.js | grep "texto único"
   ```

### Deploy não é 100% automático

O `autoDeploy: false` no Easypanel pra `telegram-account-webhook`. Push pro `main` sozinho NÃO dispara rebuild. É preciso disparar o webhook de deploy manualmente:

```bash
$body = '{}'
Invoke-WebRequest -Method POST -Uri 'http://82.112.244.9:3000/api/deploy/d08148ad7475ab169bc6b4baac629cc1c0e18c900b11d525' -ContentType 'application/json' -Body $body -UseBasicParsing
```

Ou via MCP do Easypanel: `deployAppService` com `{projectName: "eh-tudo", serviceName: "telegram-account-webhook"}` (precisa de `execute_destructive`, não `execute_mutation`).

## Pegadinhas conhecidas (Vue 3 SFC + vue-tsc)

- **`</script>` literal dentro de template string JS quebra o parser SFC** (ele fecha o bloco de script no primeiro `</script>` que achar). Atinge também `</template>` e `</style>`. Soluções:
  - Unicode escape: `<\u002Fscript>` (parser não vê, JS engine converte em runtime)
  - Concatenar: `'</' + 'script>'`
  - Dividir em array: `['<', '/script>'].join('')`
- **Expressões com `$` no template Vue** (ex: `{{$json.body.x}}` pra documentar n8n) são interpretadas como propriedade da instância. Soluções:
  - Mover pra constante JS e renderizar via `{{ MINHA_CONSTANTE }}`
  - Ou usar `v-pre` no elemento que contém o texto literal
- **TS6133 "declared but never read"** se uma constante foi usada só em comentário ou removida do template — deletar a declaração (vue-tsc é estrito).
- **Bundle JS tem cache agressivo** no navegador do usuário final: depois de deploy, pode aparecer a versão antiga mesmo com hash novo. Sempre validar via `curl` no asset, não só no HTML.

## Migrations PocketBase (PB 0.40+)

**Referência completa: `.agents/skills/pocketbase-migrations/SKILL.md`** —
cobre em detalhe: regra "nunca editar, sempre criar nova", sintaxe de
Field em PB 0.40+ (options diretas no field, não em `options: {}`),
timestamps BRT-as-UTC, idempotência, procedimento de teste local com
`pb_data` + `sqlite3`, e tabela de erros comuns.

TL;DR (sempre ler a skill antes de mexer em `pb_migrations/`):

- **NUNCA editar uma migration depois de commitada.** O PB registra as
  migrations em `pb_data/_migrations` e não reaplica se você mudar o
  conteúdo. Se uma migration falhou em prod e ficou estado parcial, crie
  uma **nova** migration com timestamp maior, defensiva (idempotente).
- **Timestamps de migration** usam epoch Linux com timezone -3 (BRT-as-UTC).
  PowerShell: `[DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - 3*3600`.
  Sempre maior que o último em `pocketbase/pb_migrations/`.
- **Sintaxe de Field em PB 0.40+** — opções vão **direto no field**
  (`values`, `collectionId`, `cascadeDelete`, `minSelect`, `maxSelect`),
  NÃO dentro de `options: {}`. Errado = `could not convert [object Object] to core.Field`
  ou `(values/collectionId: cannot be blank.)`.
- **Adicionar field em collection existente** precisa da classe wrapper:
  `col.fields.add(new Field({...}))`. Objeto literal falha.
- **SEMPRE testar migrations localmente** antes de commit/deploy:

  ```bash
  cd pocketbase
  mavis-trash pb_data    # resetar estado local
  node ../scripts/pocketbase.js   # baixa e roda PB
  # verificar `pb_data/_migrations` no SQLite (ou `pocketbase admin`)
  ```

  Se o startup do PB imprimir `failed to apply migration ...`, **não commit**.
  Corrigir a migration e voltar pro passo 1.

