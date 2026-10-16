# PRD — Página de Mensagens (visualizar + enviar)

> **Status:** implementado em `apps/web/src/views/MessagesView.vue`
> (revisão #2 do plano, após feedback do usuário).
> **Rota:** `/messages/:sessionId?`

---

## Summary

Criar uma página em `apps/web` com **layout estilo Telegram Web** (sidebar
esquerda com lista de chats, painel central com mensagens do chat
selecionado, composer fixo na parte inferior) que:

1. **Lê diretamente da collection PocketBase `telegram_messages`** via SDK do
   PB no frontend (`pb.collection('telegram_messages').getList(...)`). **Sem
   novo endpoint no FastAPI** — o usuário explicitamente não quer que a
   leitura passe pelo FastAPI/Telethon; os dados já estão no PB (a session
   é que está conectada, o handler Telethon grava no PB).
2. **Agrupa mensagens por `chat_id`/`chat_title`** pra formar a lista de
   chats na sidebar (mesma fonte de dados, agrupamento client-side).
3. **Envia mensagens via endpoint já existente** `POST /api/send-message`
   (única forma de falar com o Telethon). Sem mudança de backend.
4. **Composer inferior** com:
   - input de texto
   - toggle **plain / html**
   - ícone de imagem que expande um campo de **URL de imagem**
   - botão Enviar

**Decisões-chave:**

- **Sem backend novo.** Toda a leitura vai pelo PocketBase SDK. O service
  token do PB (`POCKETBASE_SERVICE_TOKEN`) já existe no backend pra INSERT
  do audit, mas o frontend só precisa do user JWT normal.
- **Send continua pelo FastAPI** (`telegramApi.sendMessage()`). Isso não é
  "conectar com Telethon no frontend" — é só uma chamada HTTP pro endpoint
  existente que já trata tudo (resolve session, valida URL, suprime
  anti-loop, etc).
- **Sidebar de chats = agrupamento client-side** dos records de
  `telegram_messages` por `chat_id` (com fallback em `chat_title` se
  faltarem). Sem collection nova.
- **Auto-refresh via polling** (15s) com `since` pra request barata.
- **Layout responsivo:** desktop = sidebar fixa; mobile = lista cheia.
- **Filtro de sessão no topo** — dropdown com as contas do user
  (`telegramStore.sessions`). Sem sessão selecionada = empty state com CTA.

---

## Goal

Dar ao usuário uma visão de **conversa** (audit log completo) por chat
dentro de uma conta Telegram, com:

- Sidebar à esquerda listando todos os chats que tiveram mensagens
  (ordenados pela mensagem mais recente).
- Painel central mostrando as mensagens do chat selecionado (incoming +
  outgoing, em ordem cronológica).
- Composer inferior pra enviar mensagem nova (texto + opcionalmente imagem
  + escolha de formato).
- Filtros: por conta (topo), direção (chips all/incoming/outgoing), busca
  textual.
- Auto-refresh pra refletir novas mensagens em ≤ 15s.

## Non-goals

- **Sem novo endpoint no FastAPI.** Toda a leitura é direta no PB.
- **Sem SSE/WebSocket.** Polling de 15s basta.
- **Sem mídia exibida** (só o campo `text`).
- **Sem export CSV/PDF.**
- **Sem broadcast em massa.** 1-para-1 ou 1-para-chat.
- **Sem migração nova** / mudança de schema / mudança de hook.
- **Sem mudança na `listRule` da `telegram_messages`** (continua
  permissivo, padrão atual do projeto).

## Arquivos afetados

### Criados

- `apps/web/src/views/MessagesView.vue` — view principal (Telegram Web
  layout)
- `apps/web/src/services/messages.ts` — wrapper PB + tipos + grouping
- `docs/prd/messages-page.md` — este PRD

### Modificados

- `apps/web/src/router/index.ts` — rota `/messages/:sessionId?`
- `apps/web/src/views/DashboardView.vue` — botão "Mensagens" por sessão
  (router.push)
- `apps/web/src/stores/telegram.ts` — `messagesBySession`,
  `chatsBySession`, `fetchMessages`, `prependMessages`,
  `invalidateMessages`

### NÃO modificados

- `backend/main.py` — **zero mudança** (conforme pedido)
- `pocketbase/pb_migrations/*` — nenhuma
- `pocketbase/pb_hooks/*` — nenhum
- `apps/landing/*` — nenhum
- `docker-compose.yml` / Dockerfiles — nenhum
- `apps/web/src/services/pocketbase.ts` — sem mudança (já é exportado
  como default `pb`)

---

## Layout (estilo Telegram Web)

```
┌──────────────────────────────────────────────────────────────────────┐
│ Header:  [← Voltar]  Mensagens · {accountLabel}     [Atualizar]      │
│ Seletor de conta (se /messages sem :sessionId)                       │
├─────────────────────────┬────────────────────────────────────────────┤
│ Sidebar (esq, 320px)    │ Main Panel                                 │
│ ─ Busca                 │ ─ Header do chat: title, type, total       │
│ ─ Chips all/in/out      │ ─ Lista de mensagens (scroll)              │
│ ─ Lista de chats        │   • incoming: balão à esquerda (cinza)     │
│   ▣ Chat title (12)     │   • outgoing: balão à direita (azul)       │
│   ▣ Outro chat (3)      │   • timestamp embaixo                      │
│   ▣ ...                 │   • sender_name pra grupos                 │
│   (ordenados por        │ ─ Composer fixo embaixo                    │
│    última msg desc)     │   [🖼] [textarea] [plain▾] [Enviar]        │
│                         │   ↳ se 🖼 clicado, expande input de URL    │
├─────────────────────────┴────────────────────────────────────────────┤
│ Footer com hint: "Atualiza a cada 15s" + "⏸ auto-refresh" toggle    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## End-to-end flow

### Carregar página

1. User acessa `/messages` ou `/messages/{sessionId}`.
2. Router guard valida auth (`meta.requiresAuth`).
3. `MessagesView.vue` `onMounted`:
   - Se `telegramStore.sessions` vazio → `telegramStore.fetchSessions()`.
   - Define `currentSessionId` (do param da rota ou primeira sessão
     ativa). Se não tem sessão ativa, mostra empty state com CTA
     "Adicionar conta".
   - `telegramStore.fetchMessages(currentSessionId, { perPage: 200 })` —
     pega 200 mensagens iniciais (a coleção tende a ser razoável;
     ajustar se virem volume >5k).
4. Render: sidebar (chats agrupados) + main panel (vazio se nenhum
   chat selecionado).

### Selecionar chat

1. User clica num chat da sidebar.
2. `selectedChatId` seta; main panel filtra `messages.filter(m =>
   m.chat_id === selectedChatId)`, ordena por `created` asc.
3. Scroll auto pro final (última mensagem visível).
4. Sidebar marca o chat ativo com bg destacado.

### Enviar mensagem

1. User digita texto no composer inferior.
2. Opcional: clica no ícone 🖼 → campo de URL expande abaixo do textarea.
3. Opcional: alterna o select `plain` ↔ `html`.
4. Clica "Enviar":
   - `telegramApi.sendMessage({ session_id, chat_id, text, parse_mode,
     image_url? })` — POST pro FastAPI.
   - Botão fica disabled, mostra spinner.
   - Em success: limpa composer, mostra toast "Enviada". Não adiciona
     à lista local (próximo poll traz ela do PB em ≤ 15s — comportamento
     simples e autoritativo).
   - Em error: mostra erro inline (banner vermelho), composer mantém
     o texto.
5. Próximo `fetchMessages` (≤ 15s) traz a versão autoritativa do PB
   e atualiza a lista.

### Auto-refresh

- `setInterval(refresh, 15000)` enquanto `autoRefresh = true` E aba
  visível (`document.visibilityState === 'visible'`).
- `refresh` faz `telegramStore.prependMessages(currentSessionId)`, que
  internamente faz `pb.collection('telegram_messages').getList(filter:
  'session.session_id = "..."' + ' && created > "since"', perPage: 100)`.
- `since` = `created` da msg mais recente em cache.
- Dedupe por `id` no client; prepend mantendo ordem cronológica.
- Cancela interval no `onUnmounted`.
- `visibilitychange` handler faz refresh imediato quando a aba volta
  de background.

### Empty / Error states

- Sem sessões: "Adicione uma conta Telegram primeiro" → `/add-telegram`.
- Sessão sem mensagens: ilustração + "Nenhuma mensagem ainda. A primeira
  mensagem vai aparecer aqui assim que chegar."
- Chat sem mensagens (estado inconsistente): "Nenhuma mensagem neste
  chat."
- Erro de rede: banner vermelho com botão "Tentar novamente".

---

## State, ownership, concurrency

- **Estado da página:** local (refs do `setup script`) + cache no store
  (`messagesBySession`).
- **Concorrência:** flag `inFlight` (`messagesInFlight`) por session_id
  no store; chamadas sobrepostas descartadas.
- **Reconciliação:** dedupe por `id` no prepend. `created` é string ISO
  do PB, comparação é lexicográfica (funciona pra ISO 8601 UTC).
- **Composer state** totalmente local (textarea/image_url/parse_mode).
  Reset após sucesso.
- **Sem optimistic-update** no envio — UI espera o próximo poll.

---

## Tests & acceptance criteria

### Build estático

- `cmd.exe /c "cd /d D:\repos\telegram-account-webhook\apps\web && npm run
  build` — exit 0, sem erros de `vue-tsc`, sem warnings de TS6133.
- TypeScript estrito: nenhum `any` adicionado, nenhum unused var.

### Funcional (manual no browser)

- `/messages` sem `:sessionId` → mostra seletor de conta; escolher uma
  carrega chats.
- `/messages/{sessionId}` direto → carrega direto.
- Sidebar lista chats (agrupados por `chat_id`), ordenados por msg mais
  recente.
- Clicar num chat → main panel mostra só as mensagens dele, em ordem
  cronológica, scrollável.
- Filtro "Só recebidas" esconde outgoing.
- Filtro "Só enviadas" esconde incoming.
- Busca textual: typing em "busca" filtra.
- Composer: digitar texto + clicar Enviar → POST 200, msg aparece no
  próximo poll.
- Composer: alternar pra `html` + enviar `<b>oi</b>` → chega bold.
- Composer: clicar 🖼 → campo URL aparece; colar URL + texto + Enviar
  → manda foto com caption.
- Auto-refresh: deixar aba aberta 30s, simular nova msg (insert manual
  no PB), ver aparecer em ≤ 15s.
- Empty state: sessão sem mensagens → ilustração.
- Responsivo: 375px (mobile) — sidebar colapsa; main full-width;
  composer fixo embaixo.
- Navegação: clicar "Voltar" no header → `/dashboard`. Browser back
  funciona.
- Deep-link: cold start em `/messages/abc` carrega tudo.

### Critérios de aceite globais

1. Build não quebra.
2. Nenhum arquivo de backend, migration ou hook foi tocado.
3. Sidebar estilo Telegram Web (lista vertical com nome do chat, badge
   com count ou last message preview).
4. Painel central estilo Telegram Web (balões esquerda/direita com
   timestamp).
5. Composer fixo inferior com 🖼 + textarea + plain/html + Enviar.
6. Auto-refresh funciona.
7. Envio end-to-end funciona (UI → FastAPI → Telethon → audit).
8. Sem `any` no TypeScript estrito.

---

## Unresolved decisions (resolvidos na impl)

- **Volume inicial:** 200 messages por sessão na primeira carga.
- **Mobile:** lista cheia (sidebar oculta se tela pequena) — usando
  `md:grid-cols-[320px_1fr]`, mobile fica full-width. Decidir drawer
  numa v2.
- **Tema de cores dos balões:** paleta do projeto (cinza incoming,
  azul-roxo gradient outgoing) em vez das cores Telegram oficiais.
- **Timestamp formato:** absoluto no balão ("15/10 21:46") + relativo na
  sidebar ("há 5 min").
- **Grouping na sidebar:** flat, com ícone indicando o tipo de chat
  (UserIcon/UserGroupIcon/MegaphoneIcon). Sem agrupar por chat_type.
- **Auto-refresh on focus:** sim, `visibilitychange` handler dispara
  `prependMessages` imediato quando aba volta de background.

---

## Anexo: schema de `telegram_messages` (referência)

```
session         relation → telegram_sessions (cascadeDelete)
chat_id         number
chat_type       select [private, group, supergroup, channel, unknown]
chat_title      text (max 200)
direction       select [incoming, outgoing]
sender_id       number
sender_name     text (max 200)
sender_username text (max 200, opcional) — @username sem o @
text            text (max 5000)
raw             json (opcional, debug)
delivered_count number (opcional, hook-only)
delivery_error  text (opcional, hook-only)
created         datetime (auto)
```

Migration: `pocketbase/pb_migrations/1791990597_create_telegram_messages.js`.

`listRule`: `"@request.auth.id != ''"` (qualquer user autenticado lê).
