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
│  │  • PocketBase :8090   (DB + Auth + Admin UI)                   │ │
│  │  • Landing Page /                                              │ │
│  │  • Web App /app/                                              │ │
│  │                                                                 │ │
│  │  Hook do PB: NO-OP (loga INSERT em telegram_messages,          │ │
│  │  mas NÃO faz forwarding — ver Serviço 2 abaixo)                │ │
│  │                                                                 │ │
│  │  TELEGRAM_API_URL=http://telegram-api:8000                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                              │                                      │
│                              │ HTTP (rede Docker interna)            │
│                              ▼                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Serviço 2: Telegram API                                       │ │
│  │  ────────────────────────────────────────────────────────────   │ │
│  │  • FastAPI :8000                                               │ │
│  │  • Telethon                                                    │ │
│  │                                                                 │ │
│  │  Responsável pelo FORWARDING de webhooks:                       │ │
│  │   1) Telethon recebe nova mensagem                             │ │
│  │   2) FastAPI consulta `telegram_webhooks` no PB                │ │
│  │   3) Filtra direction/chat_type/text_match in-process          │ │
│  │   4) httpx.post em cada um com timeout 10s                     │ │
│  │   5) INSERT em `telegram_messages` (audit log completo)        │ │
│  │                                                                 │ │
│  │  POCKETBASE_URL=http://pocketbase:8090                          │ │
│  │  POCKETBASE_SERVICE_TOKEN=<jwt-de-superuser>                    │ │
│  │     (ou POCKETBASE_ADMIN_EMAIL + PASSWORD p/ login auto)        │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

**Por que FastAPI faz o forwarding e não o hook do PB:**

O container do PB no Easypanel pode ter egress restrito pra certos IPs externos (network ACL) — `$http.send` trava indefinidamente. O container do Telethon service tem egress liberado pra internet (fala com Telegram API, PB, e IPs externos). Python `httpx` com timeout limpo vence PB JSVM síncrono nesse cenário.

## Estrutura

```
telegram-account-webhook/
├── Dockerfile.Application          # PocketBase + Frontend Vue
├── Dockerfile.Telegram             # FastAPI + Telethon
├── backend/
│   ├── main.py                     # FastAPI: auth, webhooks, forwarding, send-message
│   ├── requirements.txt
│   └── .env.example
├── apps/
│   ├── landing/                    # Landing page
│   └── web/                        # Web app Vue
├── pocketbase/
│   ├── pb_hooks/
│   │   └── main.pb.js              # no-op (forwarding é no FastAPI)
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
<easypanel-host>/api/deploy/<token-do-servico-application>
```

O `<easypanel-host>` é o servidor onde o painel Easypanel está rodando (ex: `painel.ehtudo.app` ou IP da VPS). O token fica nas configs do serviço no painel. **NÃO commitar o IP/host do servidor nem o token** — esses são sensíveis e mudam por projeto.

Push para `main` = deploy automático via Easypanel (manual via webhook — ver abaixo).

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

# Autenticação do FastAPI no PB (uma das duas):
POCKETBASE_SERVICE_TOKEN=<jwt>               # Opção A: JWT pronto, sem senha no env
# OU
POCKETBASE_ADMIN_EMAIL=service@eh-tudo.app   # Opção B: login automático no startup
POCKETBASE_ADMIN_PASSWORD=...                # Auto-refresh: re-autentica 5min antes do exp
```

## Coleções PocketBase

- `users`: Usuários (auth nativo)
- `telegram_sessions`: phone, session_id, name (alias opcional, editável)
  - Credencial `StringSession` **NÃO** fica aqui — só no `/app/sessions/*.json`.
  - Credenciais do app Telegram (`api_id`/`api_hash`) ficam nos env vars do container (single-app).
- `telegram_webhooks`: name, enabled, url + filtros (direction, chat_type, text_match)
  - Relation com `telegram_sessions` (cascadeDelete). Vários webhooks por sessão.
  - **Esta é a lista que o FastAPI consulta no `handle_new_message` pra fazer o forwarding.**
- `telegram_messages`: audit log. Append-only (updateRule/deleteRule = null). Schema: `session` (relation), `chat_id`, `chat_type`, `chat_title`, `direction` (incoming|outgoing), `sender_id`, `sender_name`, `sender_username` (@username sem @, opcional), `text`, `created`. O FastAPI insere TODA mensagem (incoming + outgoing) que chega via Telethon. O hook do PB é no-op (não duplica o forwarding).

## API Backend

Endpoints principais do FastAPI (Telegram service). Lista completa no README.

| Method | Endpoint | Descrição |
|--------|----------|-----------|
| POST | /api/send-code | Envia código Telegram (signup) |
| POST | /api/verify-code | Verifica código + cria sessão |
| GET | /api/sessions | Lista sessões + webhooks_count |
| POST | /api/sessions/{id}/webhooks | Cria webhook |
| PATCH | /api/webhooks/{id} | Edita webhook (URL/filtros/enabled) |
| DELETE | /api/webhooks/{id} | Remove webhook |
| POST | /api/webhooks/{id}/toggle | Liga/desliga sem deletar |
| POST | /api/webhooks/{id}/test | POSTa payload de teste na URL (FastAPI direto, não exercita o forwarding real) |
| POST | /api/send-message | Envia mensagem via sessão Telegram. Body: `{session_id, chat_id (int ou @username), text?, parse_mode? (plain\|html), image_url? (URL pública validada SSRF), reply_to_message_id?}`. Schema completo + erros comuns + fluxo anti-loop no README. |
| GET | /health | Health check (`active_sessions`, `saved_sessions`) |
| GET | /api/admin/sessions | Debug — lista arquivos `/app/sessions/*.json` |

**Schema do payload** que o `handle_new_message` envia pros webhooks (e que o `/api/webhooks/{id}/test` replica): ver seção "Webhook payload" no README. Estrutura de alto nível:

- `event`: sempre `"telegram.message"`
- `webhook_id` / `webhook_name`: identificação do webhook que recebeu
- `session`: conta Telegram que recebeu/mandou (com `session.user` = própria conta)
- `from`: quem mandou (User object completo; `null` se for canal)
- `chat`: onde chegou (User/Group/Supergroup/Channel; `title` polimórfico)
- `message`: a mensagem em si (campos legados + `reply_to_msg_id`)

Detecção de direction (`incoming` vs `outgoing`) usa OR entre `event.outgoing` (Telethon) e `from.id == session.user.id` (cobre mensagens enviadas via outro client do mesmo user).

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
Invoke-WebRequest -Method POST -Uri '<easypanel-host>/api/deploy/<token-do-servico-application>' -ContentType 'application/json' -Body $body -UseBasicParsing
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

## Workflows por área (validate → commit → deploy)

Este projeto tem 3 áreas independentes, cada uma com seu próprio ciclo
de validação local + deploy. **Não assuma que o commit tá OK só porque
o git aceitou** — o build/migration/syntax check PODE falhar.

São 2 serviços no Easypanel (mesmo projeto `eh-tudo`):
- `telegram-account-webhook` (PB + frontend) → deployar **só** quando
  mexeu em `pocketbase/**` ou `apps/web/**` ou `apps/landing/**`
- `telegram-account-webhook-telegram` (FastAPI/Telethon) → deployar
  **só** quando mexeu em `backend/**`

### Área 1 — Frontend (apps/web ou apps/landing)

**Quando rodar:** qualquer mudança em `apps/web/src/**` ou `apps/landing/src/**`,
incluindo tipos TypeScript, imports, CSS, ou templates Vue.

```powershell
# 1) Validate (build local) — OBRIGATÓRIO antes do commit
#    npm.ps1 é bloqueado pela ExecutionPolicy do Windows → cmd.exe /c
cmd.exe /c "cd /d apps\web && npm run build"
cmd.exe /c "cd /d apps\landing && npm run build"   # só se mexeu na landing
#    Sinal verde: exit 0 + "✓ built in X.XXs"
#    Sinal vermelho: vue-tsc erro (TS6133, import não resolvido) ou
#      Vite erro de parse SFC — NÃO COMMITAR, consertar antes

# 2) Validate browser-side (deploy só ajuda se foi publicado)
#    Após deploy, forçar reload: Ctrl+Shift+R ou ?v=novo na URL

# 3) Commit
git add apps/web/src apps/landing/src
git commit -m "fix(ui): descrição da mudança"
#    Lembrete: subject em PT-BR é ok aqui (user não usa Conventional
#    Commits estrito). Mas PR description se for pra review externa
#    deve ser Conventional.

# 4) Push (NÃO dispara deploy sozinho — autoDeploy: false)
git push

# 5) Deploy — dispara rebuild do serviço Application no Easypanel
#    Via MCP (preferido, não precisa de token):
mcp__easypanel-bleach execute_destructive({
  projectName: "eh-tudo",
  serviceName: "telegram-account-webhook",   # NÃO usar "telegram-account-webhook-telegram"
  forceRebuild: true,
})
#    Espera 3-5min e checa se subiu:
curl -sS -m 10 https://telegram-webhook.ehtudo.app/api/health
#    (esse endpoint é servido pelo PB 0.40 — NÃO é /health, que dá 404)
#    (se o build tiver quebrado vai dar 502 ou não responder)
```

> **Como confirmar que o bundle novo (e não o antigo, servido do cache do
> navegador) está no ar:** pegue o hash do build local em `apps/web/dist/`
> e compare com o que o HTML referencia. Só o **CSS** tem hash idêntico ao
> local — o JS diverge porque o build dentro do container inlineia env vars
> diferentes. Para checar o conteúdo de vez, faça grep do token:
>
> ```bash
> curl -s https://telegram-webhook.ehtudo.app/app/assets/index-XXXX.css | grep -c 'color-brand-500:#229ed9'
> curl -s https://telegram-webhook.ehtudo.app/app/assets/index-YYYY.js  | grep -c 'bg-brand-500'
> curl -s https://telegram-webhook.ehtudo.app/css/style.css           | grep -c 'color-accent-500:#7c5cfc'
> ```

### Área 2 — PocketBase (pocketbase/**)

**Quando rodar:** qualquer mudança em `pocketbase/pb_migrations/*.js`
(nova collection, novo field, migração de dados) ou `pocketbase/pb_hooks/*.pb.js`
(handler, routerAdd, etc).

```powershell
# 1) Limpar pb_data local (estado limpo, garante que a migration
#    roda do zero — não pula nenhuma)
cmd.exe /c "C:\Users\edson\.minimax\bin\mavis-trash.cmd -- pocketbase\pb_data"
#    Equivalente: rm -- pocketbase/pb_data (runtime routes via mavis-trash)

# 2) Subir PB local. Aplica TODAS as migrations em pb_migrations/.
#    Roda em background (PB serve indefinitely).
cd pocketbase
.\pocketbase.exe serve --http=127.0.0.1:8090
#    OU se o binary não tá lá: node ../scripts/pocketbase.js

# 3) Inspecionar o startup
#    Sinal verde: "Server started at http://127.0.0.1:8090" + nada de
#      "Error: failed to apply migration ..."
#    Sinal vermelho: SyntaxError, "could not convert [object Object] to
#      core.Field", "values/collectionId: cannot be blank" → NÃO
#      COMMITAR, ler .agents/skills/pocketbase-migrations/SKILL.md

# 4) Verificações de sanidade (sqlite3 no pb_data):
#    (a) Lista de migrations aplicadas (deve bater com arquivos):
sqlite3 pb_data/data.db "SELECT file FROM _migrations ORDER BY file"
#    (b) Schema da collection que você modificou/criou:
sqlite3 pb_data/data.db "PRAGMA table_info(telegram_messages)"
#    (c) Pra collection nova, conferir que existe:
sqlite3 pb_data/data.db "SELECT name FROM _collections ORDER BY name"

# 5) Parar o PB local (Ctrl+C)

# 6) Commit
git add pocketbase/pb_migrations/ pocketbase/pb_hooks/
git commit -m "feat(pb): descrição"

# 7) Push
git push

# 8) Deploy — rebuild do serviço Application
mcp__easypanel-bleach execute_destructive({
  projectName: "eh-tudo",
  serviceName: "telegram-account-webhook",
  forceRebuild: true,
})
#    Verificar que a migration rodou: log do Easypanel (se acessível)
#    ou admin UI do PB em https://telegram-webhook.ehtudo.app/_/
```

### Área 3 — Backend Telethon (backend/**)

**Quando rodar:** qualquer mudança em `backend/main.py`,
`backend/requirements.txt`, ou arquivos novos em `backend/`.

```powershell
# 1) Validate (syntax check estático) — Python não tem build step
python -c "import ast; ast.parse(open(r'backend\main.py', encoding='utf-8').read())"
#    Sinal verde: sem output (AST parse OK)
#    Sinal vermelho: SyntaxError com linha/coluna do erro — NÃO
#      COMMITAR, consertar antes

# 2) (Opcional) Validar imports do requirements.txt
#    Se mudou requirements.txt, vale instalar local pra confirmar
#    que nada quebrou:
python -m pip install -r backend/requirements.txt
python -c "import fastapi, telethon, httpx, pydantic; print('imports OK')"
#    Cuidado: pode poluir o venv global. Rodar em venv dedicado:
#    python -m venv .venv-validate && .venv-validate\Scripts\activate

# 3) Commit
git add backend/
git commit -m "fix(api): descrição"

# 4) Push
git push

# 5) Deploy — rebuild do serviço Telegram API
mcp__easypanel-bleach execute_destructive({
  projectName: "eh-tudo",
  serviceName: "telegram-account-webhook-telegram",  # DIFERENTE do Application!
  forceRebuild: true,
})
#    Verificar que subiu e o service token está OK (sem isso o
#    container crasha no lifespan):
curl -sS -m 10 https://api-telegram.ehtudo.app/health
#    Esperado: {"status":"ok","active_sessions":1,...}
#    Se "active_sessions":0: Telethon não conectou, mas subiu.
#    Se não responder: container crashou — provavelmente faltou
#    POCKETBASE_SERVICE_TOKEN ou POCKETBASE_ADMIN_EMAIL/PASSWORD
#    no env do serviço (ver Easypanel → serviço → Env).
```

### Detecção de qual área você mexeu

Antes de commitar, sempre rodar:

```powershell
git status --short
#    Saída típica:
#      M apps/web/src/views/DashboardView.vue        ← Área 1 (web)
#      M backend/main.py                            ← Área 3 (telethon)
#      M pocketbase/pb_migrations/1792063175_...js  ← Área 2 (pb)
#
# Cada path mapeia pra uma área:
#   apps/web/**, apps/landing/**        → Área 1
#   pocketbase/**                       → Área 2
#   backend/**                          → Área 3
#   *.md, .agents/**, scripts/**        → Não-deploy (docs/agents só)
#   Dockerfile*, docker-compose.yml     → Área 1 + Área 2 (Dockerfile
#                                         é shared; build roda pra
#                                         o serviço especificado)
```

### Validação completa (todas as áreas de uma vez)

```powershell
# Antes de um commit grande (mudança em múltiplas áreas), rodar:
git status --short
# ... baseado nos paths, rodar só os checks que se aplicam:

if (Test-Path backend/main.py) { python -c "import ast; ast.parse(open(r'backend\main.py', encoding='utf-8').read())" }
if (Test-Path pocketbase/pb_migrations) {
    # sobe PB local (ver Área 2)
}
if (Test-Path apps/web/src) { cmd.exe /c "cd /d apps\web && npm run build" }
if (Test-Path apps/landing/src) { cmd.exe /c "cd /d apps\landing && npm run build" }
```

### O que NÃO fazer

- ❌ **Commit sem validar local** — vai deployar código quebrado e
  usuário vai ficar sem saber. O Easypanel demora 3-5min pra detectar
  falha, e o log do container muitas vezes não é acessível.
- ❌ **Push sem deploy** — `autoDeploy: false` no Easypanel. Push
  sozinho NÃO rebuilda. Sempre disparar o `deployAppService` via MCP
  (ou webhook de deploy com token).
- ❌ **Deployar serviço errado** — `telegram-account-webhook` é o PB
  + frontend, `telegram-account-webhook-telegram` é o FastAPI. Trocar
  o nome deploya o serviço errado e o que você mexeu não vai pra prod.
- ❌ **Editar migration commitada** — PB não reaplica migrations já
  aplicadas. Se errou, criar migration nova (ver skill
  pocketbase-migrations).
- ❌ **Token/URL pública em commit** — `POCKETBASE_SERVICE_TOKEN`,
  easypanel-host, deploy tokens. Usar placeholders (`<token>`) na
  documentação e ler do env em runtime.


