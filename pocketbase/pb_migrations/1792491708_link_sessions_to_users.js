/// <reference path="../pb_data/types.d.ts" />

// =============================================================================
// VÍNCULO DE SESSÕES COM O USUÁRIO (isolamento multi-tenant)
// =============================================================================
//
// PROBLEMA: até aqui as 3 coleções (telegram_sessions, telegram_webhooks,
// telegram_messages) usavam a rule permissiva `@request.auth.id != ''`.
// Isso significa que QUALQUER usuário autenticado do PocketBase conseguia
// listar, ler, editar e apagar sessões, webhooks e histórico de mensagens
// de OUTROS usuários. Pior: o backend FastAPI listava as sessões a partir
// dos ARQUIVOS em disco, ignorando as rules — então o vazamento acontecia
// mesmo com a API.
//
// SOLUÇÃO: `telegram_sessions.owner` (relation → `users`) vira a fonte
// única de verdade de "quem é o dono da sessão".
//
//   - `telegram_sessions`     → dono no próprio record (`owner`)
//   - `telegram_webhooks`     → dono DERIVADO por join (`session.owner`)
//   - `telegram_messages`     → dono DERIVADO por join (`session.owner`)
//
// Por que derivar em vez de copiar o campo? Porque a reatribuição das
// sessões legadas é MANUAL (no Admin UI do PB). Com o join, o usuário
// preenche `owner` UMA VEZ e a permissão propaga sozinha pros webhooks e
// pro histórico de mensagens daquela sessão — sem backfill de centenas de
// registros.
//
// As escritas (create/update/delete) ficam `null` = bloqueadas pra
// qualquer um que não seja superuser. O FastAPI (que roda com service
// token de superuser) é o único escritor, e ele valida o dono ANTES de
// cada escrita. Isso fecha o vetor de "criar webhook apontando pra
// sessão de outro" via chamada direta na API do PB.
//
// ATENÇÃO — SEM BACKFILL: os records legados ficam com `owner` vazio
// (campo nullable). Isso é intencional: o dono das sessões já existentes
// é decidido manualmente pelo admin, no Admin UI do PB (aba
// `telegram_sessions` → campo `owner`). Sessão sem dono = invisível
// para todos (rules negam) até ser reatribuída. O forwarding dos webhooks
// NÃO depende de dono — a conta continua ativa no Telegram.
//
// Ordem de deploy: backend primeiro (ele detecta a ausência do campo
// `owner` e mantém o comportamento permissivo), depois esta migration.
// =============================================================================

migrate((app) => {
  const users = app.findCollectionByNameOrId("users");
  const sessions = app.findCollectionByNameOrId("telegram_sessions");
  const hooks = app.findCollectionByNameOrId("telegram_webhooks");
  const messages = app.findCollectionByNameOrId("telegram_messages");

  // ---------------------------------------------------------------------------
  // 1) Campo de dono em telegram_sessions
  // ---------------------------------------------------------------------------
  // `required: false` de propósito — os records legados ficam sem dono até
  // a reatribuição manual. `cascadeDelete: true` faz apagar o usuário
  // apagar a sessão, que cascateia em webhooks e mensagens.
  //
  // IMPORTANTE: sem `app.save(collection)` o PB descarta as alterações — a
  // migration é registrada como aplicada e o schema NÃO muda. (Armadilha
  // clássica: "migration aplicada" ≠ "schema atualizado".)
  let changed = false;

  if (!sessions.fields.getByName("owner")) {
    sessions.fields.add(
      new Field({
        name: "owner",
        type: "relation",
        required: false,
        collectionId: users.id,
        cascadeDelete: true,
        minSelect: 1,
        maxSelect: 1,
      })
    );
    changed = true;
  }

  // ---------------------------------------------------------------------------
  // 2) Índice de suporte às rules por dono
  // ---------------------------------------------------------------------------
  if (!sessions.indexes.some((i) => i.includes("idx_telegram_sessions_owner"))) {
    sessions.indexes.push(
      "CREATE INDEX IF NOT EXISTS idx_telegram_sessions_owner ON telegram_sessions (owner)"
    );
    changed = true;
  }

  // ---------------------------------------------------------------------------
  // 3) Rules por dono
  // ---------------------------------------------------------------------------
  // `owner = @request.auth.id` → relação single: o valor do campo É o id do
  // record relacionado, então compara direto com o id do usuário logado.
  //
  // `session.owner = @request.auth.id` → join de 2 níveis (webhook/mensagem
  // → sessão → dono). Necessário porque webhook e mensagem não têm campo
  // de dono próprio.
  //
  // `null` = negar para não-superuser. Superuser ignora a rule.
  sessions.listRule = "owner = @request.auth.id";
  sessions.viewRule = "owner = @request.auth.id";
  sessions.createRule = null;
  sessions.updateRule = null;
  sessions.deleteRule = null;

  hooks.listRule = "session.owner = @request.auth.id";
  hooks.viewRule = "session.owner = @request.auth.id";
  hooks.createRule = null;
  hooks.updateRule = null;
  hooks.deleteRule = null;

  messages.listRule = "session.owner = @request.auth.id";
  messages.viewRule = "session.owner = @request.auth.id";
  messages.createRule = null;
  messages.updateRule = null;
  messages.deleteRule = null;

  // Persiste as alterações (fields + indexes + rules). Sem isso o PB
  // descarta tudo em memória.
  if (changed) {
    app.save(sessions);
  }
  app.save(hooks);
  app.save(messages);
});
