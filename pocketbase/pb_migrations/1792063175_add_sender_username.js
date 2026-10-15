/// <reference path="../pb_data/types.d.ts" />

// Adiciona `sender_username` (string, opcional) à collection
// `telegram_messages`. Armazena o @username do Telegram do sender
// (ex: "fulano_telegram") se ele tiver um. Vem vazio/null quando:
// - Sender é um canal (canais não têm @username tradicional)
// - Sender é um user sem @username (apenas first_name/last_name)
// - Sender é anônimo (evento sem .sender preenchido)
//
// Por que agora: consumer do webhook (ex: n8n) precisa identificar
// unicamente o sender em mensagens PRIVADAS. sender_id é numérico
// e não muda; sender_name pode mudar (user altera o first_name
// no Telegram). @username é o identificador mais estável.
//
// Regra de migration: nunca editar migration já commitada. Essa é
// nova, defensiva (idempotente), e o número é maior que
// 1791990597 (criação da collection).

migrate(
  (app) => {
    const messages = app.findCollectionByNameOrId("telegram_messages")
    if (!messages) {
      throw new Error("Collection telegram_messages não existe (esperada pela migration 1791990597)")
    }

    // Idempotente: só adiciona se ainda não existir
    const exists = messages.fields.getByName("sender_username")
    if (!exists) {
      messages.fields.add(new Field({
        name: "sender_username",
        type: "text",
        max: 100,
        required: false,
      }))
      app.save(messages)
    }
  },
  (app) => {
    // down — best-effort
    try {
      const messages = app.findCollectionByNameOrId("telegram_messages")
      if (messages) {
        const f = messages.fields.getByName("sender_username")
        if (f) {
          messages.fields.remove(f)
          app.save(messages)
        }
      }
    } catch {}
  },
)
