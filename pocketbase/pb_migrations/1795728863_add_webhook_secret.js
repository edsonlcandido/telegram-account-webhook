/// <reference path="../pb_data/types.d.ts" />

// =============================================================================
// SEGREDO POR WEBHOOK (header `X-Webhook-Secret`)
// =============================================================================
//
// PROBLEMA: o POST de entrega do webhook vai SEM NENHUMA credencial —
// `client.post(url, json=payload)` (backend/main.py). Esse é o contrato atual
// do telegram-account-webhook: o receiver (n8n, backend próprio, qualquer
// cliente) pode autenticar o request do jeito que quiser, MAS não tem como
// provar que o request veio daqui.
//
// CONSEQUÊNCIA: qualquer um que descubra a URL do webhook consegue POSTar
// payload forjado. Num receiver que transforma payload em EFEITO (criar
// lançamento, acionar automação, mover dinheiro), isso é brecha de injeção.
//
// SOLUÇÃO: campo `secret` por webhook. Se preenchido, o FastAPI manda o
// valor no header `X-Webhook-Secret` em TODA entrega — inclusive no POST de
// teste (`/api/webhooks/{id}/test`). O receiver compara com o valor que o
// dono do webhook configurou.
//
// REGRAS:
//   - `secret` VAZIO = nenhum header é enviado. Os receivers atuais
//     continuam recebendo o payload idêntico (zero breaking change).
//   - O valor é do DONO do webhook: a rule da collection é
//     `session.owner = @request.auth.id`, então outro cliente do
//     telegram-account-webhook NÃO enxerga o segredo alheio.
//   - NÃO marcar como `hidden`: o dono precisa ler o valor pra configurar
//     o receiver dele (e o FastAPI lê com service token de superuser).
//   - NÃO é `max: 60` como o `name`: o segredo é token (43 chars do
//     `secrets.token_urlsafe(32)`), mas o dono pode colar um valor próprio
//     maior. 128 dá folga sem abrir pra payload gigante.
//
// ORDEM DE DEPLOY: aplicar ESTA migration ANTES do backend novo. A migration
// é 100% backward compatible (só adiciona um campo opcional) — o backend
// velho ignora o campo, e o backend novo, se rodar antes dela, cai no
// `wh.get("secret")` → None → nenhum header enviado. Por isso o backend
// novo também tolera o campo ausente (ver `_assert_webhook_owned` no
// backend: se o record não tem a chave `secret`, o PATCH não envia o campo).
// =============================================================================

migrate((app) => {
  const hooks = app.findCollectionByNameOrId("telegram_webhooks");

  let changed = false;

  if (!hooks.fields.getByName("secret")) {
    hooks.fields.add(
      new Field({
        name: "secret",
        type: "text",
        required: false,
        max: 128,
      })
    );
    changed = true;
  }

  // Persiste as alterações. Sem isso o PB descarta tudo em memória —
  // "migration aplicada" ≠ "schema atualizado" (armadilha clássica).
  if (changed) {
    app.save(hooks);
  }
});
