/// <reference path="../pb_data/types.d.ts" />

// FIX: collection `telegram_messages` foi criada via
// `new Collection({fields: [...]})` na migration 1791990597 SEM os
// system fields `created`/`updated` que o PB adiciona quando a
// collection é criada via admin UI.
//
// Consequência: a coluna `created` não existe no schema SQLite.
// `sort=-created` retorna "invalid sort field \"created\"" (log do
// PB 0.40.5) e o filter `created>"<since>"` (usado no poll
// incremental do frontend) também não funciona.
//
// Esta migration é defensiva e idempotente: adiciona `created` e
// `updated` como AutodateField (mesmo tipo que PB usa internamente
// pra esses campos). O framework auto-popula em todo INSERT/UPDATE.
//
// Registros existentes ficam com `created`/`updated` = null até
// serem atualizados (framework popula em updates). O frontend usa
// `sort=-id` como ordering primário, então os registros antigos
// continuam aparecendo normalmente — só vão pro fim se a ordenação
// for explicitamente por `created`.

migrate(
  (app) => {
    let messages
    try {
      messages = app.findCollectionByNameOrId("telegram_messages")
    } catch {
      return // collection não existe ainda — sem erro
    }
    if (!messages) return

    let changed = false
    if (!messages.fields.getByName("created")) {
      messages.fields.add(
        new AutodateField({
          name: "created",
          onCreate: true,
          onUpdate: false,
        }),
      )
      changed = true
    }
    if (!messages.fields.getByName("updated")) {
      messages.fields.add(
        new AutodateField({
          name: "updated",
          onCreate: true,
          onUpdate: true,
        }),
      )
      changed = true
    }
    if (changed) {
      app.save(messages)
    }
  },
  (app) => {
    // down — best-effort remove
    try {
      const messages = app.findCollectionByNameOrId("telegram_messages")
      let changed = false
      if (messages.fields.getByName("created")) {
        messages.fields.removeByName("created")
        changed = true
      }
      if (messages.fields.getByName("updated")) {
        messages.fields.removeByName("updated")
        changed = true
      }
      if (changed) {
        app.save(messages)
      }
    } catch {}
  },
)
