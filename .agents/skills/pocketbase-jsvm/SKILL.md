---
name: pocketbase-jsvm
description: |
  Write, debug, or modify PocketBase JavaScript hooks in `pocketbase/pb_hooks/*.pb.js`
  (this project). Covers event hooks (`onRecordAfterCreateRequest`, etc.) and
  custom routes (`routerAdd("POST", "/api/...", ...)`). Trigger when the user
  mentions a hook, pb_hooks, $http, $app, $tokens, $os.getenv, JSVM, routerAdd,
  or any PocketBase-side JS that calls an external API or touches a collection.
  Project-specific: PB 0.40.5 (>=0.27, body e Uint8Array), hooks deployed via
  Easypanel on the `telegram-account-webhook` service (Dockerfile.Application).
---

# PocketBase JSVM Hooks (this project)

PocketBase v0.20+ runs JS in a Goja VM. Hooks live in `pocketbase/pb_hooks/*.pb.js`
(extension **case-sensitive** — `*.js` not `*.pb.txt`; `*.js` not `*.pb.go`).
The JSVM is **single-purpose**: globals are `$http`, `$app`, `$os`, `$tokens`,
`toString`, `toBytes`, `readerToString`, `DynamicModel`, `Record`, plus
`routerAdd` and `onRecordAfterXxxRequest` registration helpers.

**This project is on PB 0.40.5** (>= 0.27), so:

- `resp.body` from `$http.send` is a `Uint8Array` — use `resp.json` or
  `toString(resp.body)`. Never concatenate it as a string.
- `$app.dao().X()` does NOT exist — call `$app.X()` directly.
- `$tokens` is removed — use `record.newAuthToken()` etc.

## Hooks in this repo

```
pocketbase/pb_hooks/
├── main.pb.js            # SPA routing (landing em /, webapp em /app/*)
└── 00-api-proxy.pb.js    # Proxy reverso: /api/* -> FastAPI via $http.send
```

The `00-` prefix is intentional — PB processes hook files in alphabetical
order, and `00-api-proxy.pb.js` registers its `routerAdd` handlers **before**
`main.pb.js`'s `/{path...}` catch-all, so `/api/send-code` matches the proxy
and not the static fallback.

## Workflow

1. **Confirm PB version first** — this project is 0.40.5 (>= 0.27 + >= 0.23),
   so the code patterns below apply directly. If the project ever downgrades
   to <0.23, the Dao migration in this doc kicks in.

2. **Get the request body or context** with `e.requestInfo().body` for routes
   (Uint8Array), or `e.record` for event hooks. For routes, prefer
   `e.bindBody(new DynamicModel({...defaults}))` over manual `JSON.parse` —
   it handles Content-Type negotiation (JSON, form-urlencoded, multipart).

3. **Wrap handler body in `try { ... } catch (err) { ... }`.** Without it,
   exceptions surface as generic HTTP 500s and the real message is lost. Log
   `err.message` AND `err.stack` to stdout (`docker logs`).

4. **Read `$http.send` response bodies with the official helpers.** See below.

5. **For record CRUD, call `$app.findXxx` / `$app.save` / `$app.delete`
   directly.** Get env vars with `$os.getenv("NAME")` (returns `undefined`
   if missing — always `||` a default).

6. **Throw `BadRequestError` / `NotFoundError` / `UnauthorizedError` for
   expected 4xx.** PB serializes them as JSON with the right HTTP status.
   Reserve uncaught exceptions for actual 5xx bugs.

## $http.send — the critical pattern

`resp.body` is **always a `Uint8Array`** in this project. Concatenating it
with `+` triggers `Array.prototype.toString()` and produces a comma-separated
byte string like `"123,10,32,32,34,105,115,115,..."` — which then breaks
every downstream `JSON.parse`, `substring`, or `String.length` call.

```js
// CORRECT — three equivalent ways, pick the one that fits:
const resp = $http.send({ url, method: "GET", timeout: 30 });

// (a) Best when the upstream returns application/json:
const data = resp.json;
if (!data || typeof data !== "object") { ... }

// (b) Best when you need the raw string for logging / custom parsing:
const text = toString(resp.body);
const data = JSON.parse(text);

// (c) Bytes-only (file downloads):
const bytes = toBytes(resp.body);
```

```js
// WRONG — these all silently corrupt the response:
JSON.parse(resp.body)            // parses "123,10,..." as junk
resp.body.substring(0, 100)      // TypeError: Object has no member 'substring'
String(resp.body).length         // returns byte count, NOT char count
"prefix: " + resp.body           // produces the "123,10,..." log
```

## Other JSVM gotchas (PB 0.40.5)

- **Top-level `let`/`const` are NOT shared between handlers.** Each
  `routerAdd` callback runs in a fresh VM context. Declare constants **inside**
  the handler or they'll be `undefined` in production but work in single-thread
  tests. (This bit `google-signin.pb.js` in another project — won't bite us
  here yet, but keep it in mind.)
- **No `await` / no `Promise`.** `$http.send` is synchronous. The whole hook
  blocks the request thread, so set `timeout: 30` (or higher) and never chain
  sequential HTTP calls when you can parallelize.
- **`$tokens` was REMOVED in v0.23.** Use `record.newAuthToken()` /
  `record.newVerificationToken()` / `record.newFileToken()` /
  `record.newPasswordResetToken()` / `record.newEmailChangeToken(newEmail)`.
  Error if you use the old API: `$tokens is not defined`.
- **`$os.getenv("X")` returns `undefined` (not throws) if the var is missing.**
  Always provide a default with `||`.
- **`Record` is a class** — `new Record(collection)`, then `record.set("k", v)`,
  then `$app.save(record)`. Forgetting `save` silently drops the change.
- **Custom errors:** `throw new BadRequestError("msg", null)`,
  `throw new NotFoundError("msg", null)`,
  `throw new ForbiddenError("msg", null)`,
  `throw new UnauthorizedError("msg", null)`. PB serializes them as JSON with
  the right HTTP status. Use them for expected 4xx, not for "I don't know what
  happened" 5xx.
- **`console.log` goes to stdout, not the client.** Use it for debugging but
  don't ship sensitive data through it (it ends up in `docker logs`).
- **No hot-reload on Windows / Docker volume mounts.** PB on UNIX auto-restarts
  on `pb_hooks/*.pb.js` changes, but in a container the volume mount usually
  wins and you must restart the container.

## v0.23 Dao migration (don't write pre-0.23 code)

In v0.23 the `Dao` abstraction was **removed** — methods moved up one level
onto `$app` itself. **Code that worked in v0.22 throws
`TypeError: Object has no member 'dao'` at runtime in v0.23+**, but only when
that line is hit — there's no startup-time warning.

| Operation | v0.22 (old, don't use) | v0.23+ (use this) |
|---|---|---|
| Find collection | `$app.dao().findCollectionByNameOrId("x")` | `$app.findCollectionByNameOrId("x")` |
| Find record by id | `$app.dao().findRecordById("x", id)` | `$app.findRecordById("x", id)` |
| Find first by data | `$app.dao().findFirstRecordByData("x", "k", v)` | `$app.findFirstRecordByData("x", "k", v)` |
| Find first by filter | `$app.dao().findFirstRecordByFilter(col, ...)` | `$app.findFirstRecordByFilter("x", ...)` |
| Save record | `$app.dao().saveRecord(rec)` | `$app.save(rec)` |
| Save without validation | — | `$app.saveNoValidate(rec)` |
| Delete record | `$app.dao().deleteRecord(rec)` | `$app.delete(rec)` |
| Auth record by email | `$app.dao().findAuthRecordByEmail("users", e)` | `$app.findAuthRecordByEmail("users", e)` |
| Record query | `$app.dao().recordQuery("x")` | `$app.recordQuery("x")` |
| Generate auth token | `$tokens.recordAuthToken($app, rec)` | `record.newAuthToken()` |
| Generate verify token | `$tokens.recordVerifyToken($app, rec)` | `record.newVerificationToken()` |

## Reference: `00-api-proxy.pb.js` (this repo)

When adding a hook that calls the FastAPI service, the patterns in
`00-api-proxy.pb.js` are the right template:

- `const base = $os.getenv("TELEGRAM_API_URL") || "http://eh-tudo_telegram-account-webhook-telegram:80";`
  — read internal Docker DNS from env, with a sane fallback.
- `const reqInfo = e.requestInfo();` for headers, body, path.
- `reqInfo.headers.authorization` (lowercase) to read the `Authorization` header.
- `toString(reqInfo.body)` to convert the incoming body to string before
  passing to `$http.send({ body })`.
- `resp.json` first, fall back to `toString(resp.body)` for non-JSON upstreams.
- `return e.json(status, data)` or `e.string(status, str)` to send the response.
- `throw new Error("...")` (or specific `*Error` classes) to short-circuit on
  upstream failure.

## Deploy procedure (this project)

1. `git add pocketbase/pb_hooks/<name>.pb.js`
2. `git commit -m "feat(pb): <description>"` and `git push origin main`
3. Trigger rebuild via Easypanel:
   - Web UI: open service `telegram-account-webhook` → Deploy
   - Or via webhook: `curl -X POST http://82.112.244.9:3000/api/deploy/d08148ad7475ab169bc6b4baac629cc1c0e18c900b11d525`
   - Or via MCP easypanel-bleach: `deployAppService` on
     `eh-tudo/telegram-account-webhook`

Build + restart takes ~3-5 min. After deploy, hit `https://telegram-webhook.ehtudo.app/api/health`
or any `/api/*` endpoint to verify the hook is registered and the proxy works.

## Debugging a broken hook

1. **Check the hook is in the container.** SSH in (or `docker exec`) and
   `ls -la /app/pb_hooks/`. If your new `.pb.js` isn't there, the volume
   mount or COPY step missed it.
2. **Tail the logs filtered to your tag.** Every `console.log` in the hook
   should be prefixed with `[hook-name]` so you can grep:
   `docker logs -f <container> 2>&1 | grep '\[hook-name\]'`.
3. **Reproduce the error path on the client side.** Browser DevTools → Network
   shows the status code; PB's `errorBody()` (in the response) usually
   contains the hook's `BadRequestError` / `UnauthorizedError` message verbatim.
4. **Add granular `console.log` per stage** (request received → header read →
   body parsed → upstream call → response status → body kind → JSON parse →
   final response). One log per `// -------- N. --------` section. The missing
   log tells you which step blew up.
5. **Common errors:**
   - `Object has no member 'dao'` → wrote pre-v0.23 code.
   - `TypeError: Object has no member 'substring'` and the input came from
     `$http.send().body` → concatenating a `Uint8Array` (>=0.27).
   - `$tokens is not defined` → use `record.newAuthToken()` instead.
   - `BadRequestError` thrown but PB still returns 500 → check the message
     isn't an object; PB stringifies `message` and serializes the second arg
     as `data` in the JSON response.
