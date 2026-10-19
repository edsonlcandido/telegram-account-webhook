# PRD — Token de integração (API key estilo *impersonate* do PocketBase)

> **Status:** implementado em `backend/main.py` + `apps/web/src/`
> **Rota da UI:** `/docs` (seção 2 — "POST pra responder"), sem rota nova.
> **Endpoint novo:** `POST /api/integration-token` (FastAPI do Telegram service).

---

## Summary

Permitir que o usuário **logado no painel gere o próprio token de
autenticação do PocketBase** e o **copie** para usar em **outro sistema**
(n8n, Make, backend próprio) como header `Authorization: <token>` na chamada
`POST /api/send-message`.

**Decisões-chave:**

- **O token é gerado no backend, não no frontend.** O endpoint `impersonate` do
  PocketBase exige **superuser**, e o frontend só tem o JWT do próprio usuário.
  O FastAPI já possui o superuser em mãos (`_ensure_pb_service_token()`), então
  ele funciona como proxy que minta o token.
- **Reaproveita o endpoint nativo do PB:** `POST
  /api/collections/users/impersonate/{id}` com body `{"duration": <segundos>}`.
  Sem inventar formato de token, sem crypto manual, sem collection nova.
- **O token é sempre do próprio usuário logado** — o `user_id` vem do JWT já
  verificado, **nunca do body**. Isso elimina escalação de privilégio.
- **UI dentro de `ApiDocsView.vue`**, como primeiro bloco da seção 2, porque é
  exatamente onde o placeholder `SEU_TOKEN_PB` aparece hoje. Sem rota nova, sem
  mexer no `AppNav`.
- **O `curl` de exemplo passa a ser copiável com o token real** depois de gerado —
  que é o clique final: gerar → copiar → colar no outro sistema.
- **Sem migration, sem hook, sem dependência nova.** O token não é persistido
  em lugar nenhum (é stateless no PB).

---

## Goal

O usuário entra no painel em `/docs` e resolve, sozinho, o envio de mensagem a
partir de um sistema externo — sem precisar abrir o Admin UI do PocketBase,
copiar token de superuser, nem lembrar como o `impersonate` funciona.

Caminho desejado, do ponto de vista dele:

1. Abrir `/docs`.
2. Escolher a validade (30 dias por padrão) e clicar **Gerar token**.
3. Copiar o token (ou o `curl` já com o token dentro).
4. Colar no n8n e enviar.

---

## Non-goals

- **Não** cria collection nova, migration, hook ou campo no PB.
- **Não** cria token com escopo restrito a `/api/send-message` — o `impersonate`
  devolve um token de **usuário completo**. Restringir exigiria uma camada de API
  key própria (hash no PB + middleware) — evolução futura, ver "Unresolved".
- **Não** implementa revogação individual de token: o PB é stateless e **não tem**
  endpoint de logout. Ver "Riscos".
- **Não** cria rota nova (`/app/token`).
- **Não** guarda o token em `localStorage`, Pinia, PB ou log.
- **Não** altera o comportamento do `/api/send-message` (nem o `verify_pb_auth`).
- **Não** toca em `apps/landing/`, `requirements.txt`, Dockerfiles ou
  `docker-compose.yml`.
- **Sem** refresh automático do token (o PB não permite — token de impersonate
  é estático).

---

## Arquivos afetados

### Criados

- `docs/prd/integration-token.md` — este PRD
- `apps/web/src/components/IntegrationTokenCard.vue` — card de geração do token

### Modificados

- `backend/main.py` — `IntegrationTokenRequest` (Pydantic) + rota
  `POST /api/integration-token`
- `apps/web/src/services/telegram.ts` — tipos + `createIntegrationToken()`
- `apps/web/src/views/ApiDocsView.vue` — importa o card na seção 2; `CURL_REPLY`
  passa de `const` para `computed` (usa o token gerado)
- `README.md` — endpoint na tabela + nota na seção "Enviar mensagem"

### NÃO modificados

- `pocketbase/pb_migrations/*` — nenhuma migration nova
- `pocketbase/pb_hooks/*` — nenhum
- `apps/web/src/router/index.ts` e `apps/web/src/components/AppNav.vue` — sem rota
  nova, sem item novo no menu
- `apps/landing/*`, `backend/requirements.txt`, `Dockerfile.*`, `docker-compose.yml`

---

## Layout (dentro da seção 2 de `/docs`)

```
┌─ 2. POST pra responder — /api/send-message ───────────────────────┐
│                                                                     │
│  ┌─ 🔑 Token de integração ─────────────────────────────────────┐   │
│  │ Para chamar esse endpoint de outro sistema (n8n, Make,      │   │
│  │ backend), você precisa de um token no header Authorization. │   │
│  │ Gere o seu abaixo e copie.                                    │   │
│  │                                                               │   │
│  │ Validade: [ 30 dias ▾ ]        [ 🔑 Gerar token ]            │   │
│  │                                                               │   │
│  │ (após gerar)                                                  │   │
│  │  eyJh…k3f  [Copiar] [Revelar] [Copiar curl completo]          │   │
│  │  expira em 18/11/2026 22:15 (UTC-3)                           │   │
│  │  ⚠ token estático, não renovável, revogá-lo exige trocar     │   │
│  │    a senha do usuário no Admin UI do PB.                      │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Request .......................................................... │
│  Body (JSON) ...................................................... │
│  Resposta (200) ................................................... │
│  Exemplo com curl  ← passa a usar o token real ................... │
│  Modos suportados .................................................. │
└─────────────────────────────────────────────────────────────────────┘
```

---

## End-to-end flow

### Gerar token

1. User logado abre `/docs` e rola até a seção 2.
2. O card "🔑 Token de integração" aparece **antes** do bloco "Request".
3. Ele escolhe a validade no select (1 hora / 24 horas / 7 dias / 30 dias /
   1 ano — default **30 dias**) e clica **Gerar token**.
4. `IntegrationTokenCard` chama `telegramApi.createIntegrationToken({ duration })`,
   que injeta o JWT do usuário logado no header `Authorization`.
5. Backend:
   - `verify_pb_auth` valida o caller e devolve o record do usuário;
   - `_ensure_pb_service_token()` garante o superuser (lazy + auto-refresh);
   - `POST {PB}/api/collections/users/impersonate/{user.id}` com
     `{"duration": N}` e o superuser no header (cru, sem `Bearer` — é o que o PB
     aceita);
   - decodifica o `exp` do token retornado com o helper `_jwt_exp`;
   - devolve `{ success, token, expires_at, duration, user }`.
6. O card mostra o token **mascarado** (`••••••••` + últimos 8 chars), a data de
   expiração e os botões **Copiar**, **Revelar/ocultar** e **Copiar curl
   completo**.
7. O `CURL_REPLY` do pai passa a conter o token real no lugar de
   `SEU_TOKEN_PB`.
8. Sair da página descarta o estado — o token não é persistido em lugar nenhum.

### Usar em outro sistema

1. Clica **Copiar** (só o token) ou **Copiar curl completo**.
2. Cola no HTTP Request node do n8n apontando para
   `https://api-telegram.ehtudo.app/api/send-message`.
3. O `verify_pb_auth` valida o token e o `send_message` despacha pelo Telethon.

### Falhas

- **503 do backend** (superuser do PB ausente/indisponível) → banner vermelho
  inline com a mensagem do backend; o select e o botão continuam utilizáveis.
- **502** (PB recusou o impersonate) → banner vermelho com o detalhe devolvido.
- **Token expirado no sistema externo** → o `/api/send-message` responde
  `401 "Token inválido ou expirado"` (comportamento atual, inalterado). O card
  orienta a gerar outro.
- **Falha de rede** → banner vermelho; o token anterior, se existir, continua
  válido e visível (nenhum estado parcial é criado).

---

## Contrato da API

### `POST /api/integration-token`

**Auth:** `verify_pb_auth` (mesma dependency das demais rotas autenticadas).

**Request body (opcional):**

```json
{ "duration": 2592000 }
```

**Validação:** `duration` opcional; **clamp** entre `MIN_DURATION = 300`
(5 min) e `MAX_DURATION = 31_536_000` (365 dias); default `2_592_000`
(30 dias). Valor fora da faixa é ajustado, não rejeitado.

**Response 200:**

```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_at": 1792966160,
  "duration": 2592000,
  "user": { "id": "abc123", "email": "user@exemplo.com" }
}
```

**Erros:** `401` não autenticado · `404` record do usuário não encontrado no PB ·
`502` PB recusou o impersonate · `503` superuser do PB não configurado ou
indisponível.

**Logging:** registra `user.id`, `user.email`, `duration` e `expires_at`.
**Nunca** registra o token — nem em sucesso, nem em exceção, nem em traceback.

### Modelo Pydantic

```python
class IntegrationTokenRequest(BaseModel):
    duration: Optional[int] = None
```

---

## State, ownership, concurrency

- **Dono do estado:** `IntegrationTokenCard` é autocontido. `integrationToken`
  é `ref` local do componente e some quando a página descarrega. O pai só
  compartilha o `ref` do token para que o `CURL_REPLY` use o valor real.
- **Concorrência:** `isGenerating` desabilita o botão durante a chamada —
  segundo clique não dispara request duplicado. Trocar o select durante o
  request é inofensivo: o valor usado é o do momento do clique.
- **Idempotência:** não existe "renovar". Cada clique gera um token **novo**, e
  tokens antigos continuam válidos até o próprio `exp`. A UI diz isso
  explicitamente.
- **Falha:** sem estado parcial — ou o token novo substitui o antigo, ou o
  antigo continua intacto.
- **Backend:** uma única chamada HTTP ao PB por request. O service token já tem
  controle de refresh próprio (`_ensure_pb_service_token` / refresh em 401).

---

## Segurança

- **Sem escalação de privilégio:** o endpoint **não aceita `user_id` no body**.
  O id vem do JWT verificado, então um usuário comum só consegue gerar token
  para si mesmo.
- **Escopo do token:** o `impersonate` devolve um token de **usuário completo**,
  não restrito ao `/api/send-message`. Quem tiver o token também pode criar e
  deletar webhooks e sessões. Isso está escrito no card, não escondido.
- **Não logar o token.**
- **Duração com limite:** default 30 dias, teto de 365 dias, piso de 5 minutos.
- **Só HTTPS e memória:** o token trafega por HTTPS e vive em memória; nunca é
  gravado.

---

## Tests & acceptance criteria

### Validação estática (antes de qualquer commit)

```powershell
# Área 3 — backend (sem output = OK)
python -c "import ast; ast.parse(open(r'backend\main.py', encoding='utf-8').read())"

# Área 1 — frontend (exit 0 + "✓ built in X.XXs")
cmd.exe /c "cd /d D:\repos\telegram-account-webhook\apps\web && npm run build"
```

`npm run build` = `vue-tsc && vite build`. Qualquer `TS6133`, import não
resolvido ou erro de parse de SFC ⇒ **não commitar**.

### Funcional (manual no browser)

1. `/docs` sem token gerado: card aparece e o `curl` mostra `SEU_TOKEN_PB`.
2. Selecionar "30 dias" → **Gerar token** → token mascarado, expiração correta,
   banner de aviso visível.
3. **Revelar** mostra o JWT completo; **Copiar** escreve na clipboard.
4. **Copiar curl completo** → colar no terminal, trocar `chat_id`/`session_id` por
   valores reais de uma conta ativa → a mensagem chega no Telegram.
5. O bloco "Exemplo com curl" passa a exibir o token real.
6. Gerar de novo com outra duração → novo token, expiração diferente; os tokens
   antigos continuam válidos (comportamento esperado do PB).
7. `/api/send-message` sem header `Authorization` → `401` (inalterado).
8. Token expirado → `401 "Token inválido ou expirado"`.
9. Recarregar `/docs` → o card volta ao estado inicial e o token sumiu.
10. Contexto não seguro (`navigator.clipboard` indisponível) → o fallback com
    `execCommand` assume (caminho já existente no `ApiDocsView`).

### Critérios de aceite globais

1. Build do `apps/web` passa.
2. Nenhum arquivo de migration ou hook tocado.
3. Nenhuma dependência nova.
4. O token **nunca** aparece em log nem é persistido.
5. Backend sem `user_id` no body — id sempre derivado do JWT.
6. README e este PRD descrevem o endpoint novo.

### Não verificável antes do deploy

O comportamento do PB 0.40.5 no endpoint `impersonate` **em runtime** só pode ser
confirmado contra o PocketBase real — o backend deste ambiente tem escrita, não
execução. A fumaça (gerar token no painel e rodar o `curl`) é o passo pós-deploy.

---

## Riscos

| Risco | Mitigação |
|---|---|
| **Token não pode ser revogado individualmente.** O PB é stateless, não tem logout. Tokens antigos continuam válidos até o `exp`. | Duração com teto (365 dias), aviso explícito na UI, e a orientação de que o caminho real de revogação é **trocar a senha do usuário no Admin UI do PB** (rotaciona o `tokenKey` e invalida todos os tokens dele). |
| **Token vazado dá acesso de usuário completo**, não só a enviar mensagem. | Aviso no card + aviso na seção 4 das docs + neste PRD. Escopo restrito é evolução futura. |
| **Superuser do PB não configurado** → `503`. | Mensagem de erro explícita; o backend já tem as duas estratégias (JWT fixo no env ou login automático). |
| **Service token expirado** (caminho "JWT fixo do env") → o impersonate retorna 401. | O backend faz `force_refresh_pb_service_token()` e tenta uma vez; se ainda falhar, `503` com mensagem clara. |
| Vazamento por `console.log` no frontend. | Nenhum `console.log` no card; o token só existe no `<pre>` e na clipboard por ação explícita do usuário. |

---

## Unresolved decisions (resolvidos na impl)

- **Card separado vs. bloco inline:** escolhido **componente separado**
  (`IntegrationTokenCard.vue`), porque o `ApiDocsView.vue` já tem 589 linhas e o
  estado do token precisa ser compartilhado com o `CURL_REPLY` da seção 2 — o pai
  mantém o `ref` e o card emite.
- **Duração default:** 30 dias (`2_592_000`).
- **Auditoria de emissão:** fora do v1. O log do backend já cobre "quem gerou,
  quando, por quanto tempo" — sem migration.
- **Escopo do token:** não restringido neste PRD (ver Non-goals). Token escopado
  é outro PRD, se um dia for preciso.
- **Rota dedicada:** não. `/docs` é onde o usuário procura "como chamar isso de
  fora" e já contém o placeholder do token.
- **Mostrar o token mascarado por padrão:** sim, com botão "Revelar". Evita
  shoulder-surfing e screenshot acidental no campo de tela cheia.