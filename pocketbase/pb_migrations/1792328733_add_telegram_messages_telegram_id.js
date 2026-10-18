/// <reference path="../pb_data/types.d.ts" />

// Adiciona `telegram_message_id` em `telegram_messages` — o ID da mensagem
// no Telegram (`event.id` / `sent.id` do Telethon), que é diferente do `id`
// do record no PocketBase.
//
// Por que importa: hoje o único identificador da mensagem no audit log é o
// `id` do PB (string de 15 chars, tipo `pbc_xxx`). Isso não dá como
// referenciar a mensagem de volta no Telegram — que é o que o app precisa
// pra montar deep-link (`tg://openmessage?user_id=<id>&message_id=<id>`),
// responder (`reply_to_message_id`) ou localizar a mensagem depois de um
// restart, quando o histórico do client Telethon é perdido.
//
// Escopo do ID no Telegram: `message_id` é único **por chat**, não global.
// Por isso o índice é composto `(session, chat_id, telegram_message_id)` e
// deliberadamente NÃO é UNIQUE — o mesmo id (ex: 1, 2, 3...) reaparece em
// todos os chats novos.
//
// Backfill: registros legados ficam com `telegram_message_id` NULL. O campo
// é opcional (`required: false`), então o PB não rejeita nada, e o frontend
// trata ausência. Não há como recuperar o id retroativamente — ele só
// existia em memória no handler do Telethon, nunca foi persistido.

migrate(
  (app) => {
    let messages
    try {
      messages = app.findCollectionByNameOrId("telegram_messages")
    } catch {
      return // collection não existe ainda (ordem de migration) — sem erro
    }
    if (!messages) return

    let changed = false

    // 1) Campo — number, opcional. `new Field({...})` é obrigatório em
    //    PB 0.40+; object literal falha com "could not convert [object
    //    Object] to core.Field".
    if (!messages.fields.getByName("telegram_message_id")) {
      messages.fields.add(
        new Field({
          name: "telegram_message_id",
          type: "number",
          required: false,
          // Telegram message_id é int32 positivo.
          onlyInt: true,
          min: 0,
        }),
      )
      changed = true
    }

    // 2) Índice composto (session, chat_id, telegram_message_id) pra
    //    localizar/deduplicar uma mensagem específica sem varrer o chat.
    const idxName = "idx_telegram_messages_tg_id"
    if (!messages.indexes.some((i) => i.includes(idxName))) {
      messages.indexes.push(
        `CREATE INDEX IF NOT EXISTS ${idxName} ON telegram_messages (session, chat_id, telegram_message_id)`,
      )
      changed = true
    }

    if (changed) {
      app.save(messages)
    }
  },
  (app) => {
    // down — best-effort
    try {
      const messages = app.findCollectionByNameOrId("telegram_messages")
      const idxName = "idx_telegram_messages_tg_id"
      messages.indexes = messages.indexes.filter((i) => !i.includes(idxName))
      if (messages.fields.getByName("telegram_message_id")) {
        messages.fields.removeByName("telegram_message_id")
      }
      app.save(messages)
    } catch {}
  },
)