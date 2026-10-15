---
name: pocketbase-migrations
description: |
  Create, verify, and debug PocketBase JS migrations in this project
  (pocketbase/pb_migrations/*.js, PB 0.40.5). Covers the two non-obvious
  rules that always bite on first deploy: (1) a migration must NEVER be
  edited after commit — corrections go in a NEW migration with a higher
  timestamp, (2) field options go directly on the field in PB 0.40+ (not
  nested in `options: {}` like in older versions). Trigger on requests
  that mention migration, schema change, new collection, new field,
  add field, PocketBase, PB schema, pb_migrations, types.d.ts.
---

# PocketBase Migrations (this project)

This project uses JS migrations in `pocketbase/pb_migrations/*.js` against
PocketBase v0.40.5. Two rules below have caused real deploy rollbacks in
this repo — they're not pedantic, they're load-bearing.

## Rule 1 — never edit a migration after commit

PocketBase tracks applied migrations in `pb_data/_migrations` (SQLite table).
Once a file is committed and the deploy runs it, the file is **frozen**:

- If the migration succeeded → entry in `_migrations`, no re-run. Editing the
  file does nothing in prod.
- If the migration failed and left partial state → entry may or may not be
  written depending on where the failure happened. **The only safe fix is a
  new migration.**

If you find yourself wanting to "fix" a committed migration, do this:

```bash
# 1. Pick a new timestamp (Unix epoch, BRT-as-UTC — see below)
[DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - 3*3600
#    → e.g. 1791930807

# 2. Write the new file with the corrective logic. Make it idempotent:
#    - "if field X doesn't exist, add it"
#    - "if collection Y doesn't exist, create it"
#    - "if migration N-1 left partial state, finish it"
```

The new file does NOT replace the old one. Both stay in `pb_migrations/`.
The old one is just a tombstone (PB will skip it on next startup because
the file is still there but already in `_migrations`, or because it didn't
make it that far). For migrations that **never made it to prod**, you can
delete the file locally before committing — that's a normal "revert an
uncommitted change", not "edit a migration".

## Rule 2 — PB 0.40+ field syntax

In PB 0.40+ the field options go **directly on the field object** (NOT
inside `options: {}` like PB <0.22). Wrongo vs certo:

```js
// ❌ WRONG (PB 0.22 / pre-0.27): options nested
{ name: "filter_direction", type: "select", required: false,
  options: { maxSelect: 1, values: ["all", "incoming"] } }
//   ↑ In prod you get: "(values: cannot be blank.)"

// ✅ RIGHT (PB 0.40+): options direct
{ name: "filter_direction", type: "select", required: false,
  values: ["all", "incoming", "outgoing"], maxSelect: 1 }
```

By type:

| Type | Fields (on the field, NOT in `options`) |
|---|---|
| `text` | `max`, `min`, `pattern`, `required` |
| `url` | `exceptDomains`, `onlyDomains`, `required` |
| `bool` | `required` |
| `select` | `values: string[]`, `maxSelect`, `required` |

## Rule 3 — Record queries em JS migrations (PB 0.40+)

`findAllRecords(collection, { filter: "..." })` e `$app.filter(...)` **NÃO
EXISTEM** no PB 0.40+ JSVM. As funções disponíveis:

```js
// 1) Sem filter: traz TUDO
const all = app.findAllRecords("telegram_sessions")

// 2) Com dbx expressions (variádico, não objeto):
app.findAllRecords("telegram_webhooks",
  dbx.NewExp("session = {:sid}", { sid: "abc" })
)
// Ou com HashExp pra equality:
app.findAllRecords("telegram_webhooks",
  dbx.HashExp({ enabled: true, name: "foo" })
)

// 3) Com string filter e params no final:
app.findRecordsByFilter("telegram_webhooks",
  "session = {:sid} && enabled = true",
  "",      // sort (vazio = padrão)
  500,     // limit
  0,       // offset
  { sid: "abc" }  // dbx.Params
)
```

**Sintoma do erro:** query retorna `[]` silenciosamente (sem throw) OU
`TypeError: Object has no member 'filter'`. A migração parece aplicar
mas não faz o trabalho de migration de dados. **Sempre teste com
`sqlite3 pb_data/data.db "SELECT * FROM ..."` pra confirmar que os
dados foram migrados.** Bug que eu cometi em 2026-10-14 nos exemplos
desta skill — corrigido em 2026-10-14 também.
| `relation` | `collectionId`, `cascadeDelete`, `minSelect`, `maxSelect`, `required` |

## Adding a field to an existing collection

You **must** use the `Field` class — passing a plain object literal fails:

```js
// ❌ WRONG: collection.fields.add({...})
collection.fields.add({ name: "name", type: "text", max: 60 })
//   ↑ "could not convert [object Object] to core.Field"

// ✅ RIGHT: new Field({...})
collection.fields.add(
  new Field({ name: "name", type: "text", max: 60, required: false })
)
```

Shorthand `collection.fields.add("name")` also works and creates a
`TextField` with defaults — useful when you don't need `max`/`min` and
will edit the field after.

## Timestamps

Filename = Unix epoch in seconds, **BRT-as-UTC** (not raw UTC). This keeps
filenames in "wall clock BRT" order when sorted.

```powershell
# Current BRT-as-UTC timestamp in PowerShell
[DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - 3*3600
# → e.g. 1791930807 (at 22:36 BRT on 2026-10-13)
```

Just one number, not the `1791` prefix you sometimes see — the full epoch
goes in the filename. Must be **strictly greater** than the last
migration. Check before creating:

```bash
ls pocketbase/pb_migrations/ | sort -n | tail -1
```

## Full skeleton: idempotent "add name + new collection + migrate legacy"

```js
/// <reference path="../pb_data/types.d.ts" />

// Migration 1791929716 tried to do X but failed with (collectionId: cannot
// be blank.) because options were nested in `options: {}`. This migration
// is the corrected, idempotent version. Schema reference:
//   telegram_sessions: +name (text, max 60)
//   telegram_webhooks:  new collection (relation + name + url + enabled
//                       + 3 selects for filters + text for filter value)

migrate((app) => {
  // 1. Add field to existing collection (idempotent)
  const sessions = app.findCollectionByNameOrId("telegram_sessions")
  if (!sessions.fields.getByName("name")) {
    sessions.fields.add(
      new Field({ name: "name", type: "text", max: 60, required: false }),
    )
    app.save(sessions)
  }

  // 2. Create new collection (idempotent — try/catch in case it exists)
  let webhooks
  try { webhooks = app.findCollectionByNameOrId("telegram_webhooks") } catch { webhooks = null }
  if (!webhooks) {
    webhooks = new Collection({
      name: "telegram_webhooks",
      type: "base",
      listRule: "@request.auth.id != ''",
      viewRule: "@request.auth.id != ''",
      createRule: "@request.auth.id != ''",
      updateRule: "@request.auth.id != ''",
      deleteRule: "@request.auth.id != ''",
      fields: [
        { name: "session", type: "relation", required: true,
          collectionId: sessions.id, cascadeDelete: true,
          minSelect: 1, maxSelect: 1 },
        { name: "name", type: "text", max: 60, required: false },
        { name: "url", type: "url", required: true },
        { name: "enabled", type: "bool", required: false },
        { name: "filter_direction", type: "select", required: false,
          values: ["all", "incoming", "outgoing"], maxSelect: 1 },
        { name: "filter_chat_type", type: "select", required: false,
          values: ["all", "private", "group", "supergroup", "channel"], maxSelect: 1 },
        { name: "filter_text_match_operator", type: "select", required: false,
          values: ["none", "equals", "contains"], maxSelect: 1 },
        { name: "filter_text_match_value", type: "text", max: 200, required: false },
      ],
      indexes: [
        "CREATE INDEX idx_telegram_webhooks_session ON telegram_webhooks (session)",
      ],
    })
    app.save(webhooks)
  }

  // 3. Migrate legacy data (idempotent — skip if a webhook already exists)
  for (const r of app.findAllRecords("telegram_sessions")) {
    const url = r.getString("webhook_url")
    if (!url) continue
    const existing = app.findAllRecords("telegram_webhooks", {
      filter: `session = "${r.id}"`,
    })
    if (existing.length > 0) continue
    const wh = new Record(webhooks, {
      session: r.id,
      name: "Webhook legado",
      url, enabled: true,
      filter_direction: "all", filter_chat_type: "all",
      filter_text_match_operator: "none", filter_text_match_value: "",
    })
    app.save(wh)
  }
}, (app) => {
  // down — best-effort, ignore missing collection
  try { app.delete(app.findCollectionByNameOrId("telegram_webhooks")) } catch {}
  try {
    const s = app.findCollectionByNameOrId("telegram_sessions")
    if (s.fields.getByName("name")) { s.fields.removeByName("name"); app.save(s) }
  } catch {}
})
```

## Verify a migration BEFORE committing

This project uses Easypanel + a long rebuild. If a migration fails in prod,
the webapp returns 502 and the user gets zero indication of why. **Always
test locally first.** Procedure that works on Windows + PowerShell:

```bash
# 1) Download + extract PB (scripts/pocketbase.js uses PowerShell
#    Expand-Archive because `unzip` is not on Windows by default)
cd pocketbase
node ../scripts/pocketbase.js

# 2) Reset pb_data — gets a clean slate, no leftover state
mavis-trash pb_data
# (or `rm -- pocketbase/pb_data` — runtime routes through mavis-trash)

# 3) Start PB. It applies every migration in pb_migrations/ on startup
./pocketbase.exe serve --http=127.0.0.1:8090

# 4) Inspect the result. The two checks that catch 95% of problems:
sqlite3 pb_data/data.db "SELECT file FROM _migrations ORDER BY file"
#    → should list every migration in pb_migrations/, in order

sqlite3 pb_data/data.db "PRAGMA table_info(telegram_webhooks)"
#    → column list of the collection you just created/modified
```

If startup prints `failed to apply migration 1791930807_*.js: <error>`,
**do not commit**. Read the error, fix the file, and rerun from step 2.

**Quicker smoke test** (no auth needed): just look at the start log.
`Server started at http://127.0.0.1:8090` = good. Any `failed to apply
migration` line = bad. The PB stays running even on migration failure in
some cases, so always check for the error line, not just the listen line.

## Common error → fix table

| Error in `pb_data/data.db` startup log | Cause | Fix |
|---|---|---|
| `could not convert [object Object] to core.Field` | `fields.add({...})` with plain object | Use `fields.add(new Field({...}))` |
| `(collectionId: cannot be blank.)` | `options: { collectionId: ... }` (PB 0.22 syntax) | Move `collectionId` to top of field |
| `(values: cannot be blank.)` | `options: { values: [...] }` (PB 0.22 syntax) | Move `values` to top of field |
| `(min: cannot be blank.)` mid-deploy | A prior migration was rolled back, this one ran twice | Check `sqlite3 pb_data/data.db "SELECT file FROM _migrations"` — ensure no duplicates |
| `notNull constraint failed: <table>.<col>` | Down migration tried to drop a column that was required to null out first | Reorder down: set nulls first, then drop |

## After the migration is in

1. `npm run build` in `apps/web` (the build catches TypeScript errors in
   any code that consumes the new collection).
2. `git add` the migration + AGENTS.md / skill changes.
3. Push, trigger the Easypanel deploy (see AGENTS.md "Deploy não é 100%
   automático" — `autoDeploy: false`, webhook or `deployAppService` MCP).
4. After ~45s verify: `curl -s https://telegram-webhook.ehtudo.app/` should
   return 200 (not 502). If 502, the new collection probably failed to
   create — read the previous step's "always check `failed to apply
   migration` line" advice.

## Migration filenames seen in this repo (cheat sheet)

- `1640988000_aux_init.go` — PB internal
- `1640988000_init.go` — PB internal (users, etc.)
- `1717233556_v0.23_migrate*.go` — PB upgrade migrations
- `1791780600_create_telegram_sessions.js` — first custom migration
- `1791930807_fix_session_name_and_webhooks.js` — fix-up after a failed
  earlier file; shows the "new file, never edit" pattern

If you add a new migration, put it after the latest number in this list.
