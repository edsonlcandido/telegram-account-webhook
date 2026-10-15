/// <reference path="../pb_data/types.d.ts" />

// Landing page na raiz (sem fallback SPA pq a landing é estática)
routerAdd("GET", "/{path...}", $apis.static("pb_public", false))

// Web app em /app/* com fallback SPA (index.html) pra sub-rotas do Vue Router
// tipo /app/dashboard. Sem isso, qualquer sub-rota retorna 404.
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", true))

// =============================================================================
// Webhook forwarding: quando o FastAPI insere em `telegram_messages`,
// este hook distribui pros webhooks ativos da sessão, aplicando os filtros.
// Tudo roda DENTRO do PB — sem auth, sem HTTP hop extra pro FastAPI, sem
// problemas de propagação de token.
//
// GOTCHA PB 0.40+ JSVM (relembrando pq eu já quebrei isso 3x):
// - Funções helper top-level NÃO são visíveis dentro de handlers. Tudo
//   precisa estar inline (declarado dentro do corpo do hook) senão dá
//   "ReferenceError: X is not defined" no runtime.
// - $http.send retorna `res.statusCode` (NÃO `res.status` — esse campo
//   não existe, é silenciosamente undefined).
// - Hooks *AfterSuccess rodam DEPOIS do save. Se o hook lançar, o record
//   fica persistido mas a response pro cliente vira erro. NÃO chamar
//   e.next() (no-op ou erro em AfterSuccess).
// - $http.send bloqueia (síncrono). Timeout cobre socket I/O; DNS ruim
//   pode adicionar overhead antes.
// A skill `.agents/skills/pocketbase-jsvm/SKILL.md` tem mais detalhes.
//
// DECISÃO ARQUITETURAL — rewrite de URL pública → hostname Docker interno:
// PB e n8n estão no mesmo Easypanel/projeto `eh-tudo`. O hostname público
// do n8n (ehtudo-n8n.pfdgdz.easypanel.host ou eh-tudo-n8n.aiyfgd.easypanel.host)
// resolve pra IPs diferentes, e em alguns casos (pfdgdz = 82.29.60.12, que NÃO
// é o nosso Easypanel) a conexão via Traefik trava indefinidamente. O caminho
// confiável é chamar pelo hostname interno Docker (http://n8n:5678) — mesma
// network, HTTP puro, ~1ms. O usuário continua vendo a URL pública na UI.
// Adicionar novos mapeamentos no INTERNAL_URL_MAP abaixo conforme criar
// novos serviços no mesmo Easypanel.
// =============================================================================

onRecordAfterCreateSuccess((e) => {
  // O record JÁ foi salvo quando esse hook dispara.

  // Mapeamento URL pública → hostname Docker interno. Inline (top-level
  // const não é visível pra dentro do handler no PB 0.40+).
  const INTERNAL_URL_MAP = {
    "https://ehtudo-n8n.pfdgdz.easypanel.host": "http://n8n:5678",
    "https://eh-tudo-n8n.aiyfgd.easypanel.host": "http://n8n:5678",
    "https://n8n.ehtudo.app": "http://n8n:5678",
  }

  const msg = e.record
  const sessionRel = msg.getString("session")

  // 1) Acha a sessão
  let session
  try {
    session = $app.findRecordById("telegram_sessions", sessionRel)
  } catch (err) {
    console.log("telegram_messages hook: sessão não encontrada:", String(err))
    return
  }

  // 2) Lista webhooks ativos da sessão
  let webhooks
  try {
    webhooks = $app.findRecordsByFilter(
      "telegram_webhooks",
      "session={:sid} && enabled=true",
      "",
      500,
      0,
      { sid: sessionRel },
    )
  } catch (err) {
    console.log("telegram_messages hook: erro listando webhooks:", String(err))
    return
  }

  if (!webhooks || webhooks.length === 0) {
    return
  }

  // 3) Distribui pros webhooks que passam no filtro
  let delivered = 0
  let firstError = null
  for (let i = 0; i < webhooks.length; i++) {
    const wh = webhooks[i]
    if (!wh) continue

    // matchesFilters (inline — não pode ser helper top-level)
    let pass = true
    try {
      const dir = wh.getString("filter_direction") || "all"
      if (dir !== "all" && dir !== msg.getString("direction")) pass = false

      if (pass) {
        const ct = wh.getString("filter_chat_type") || "all"
        if (ct !== "all" && ct !== msg.getString("chat_type")) pass = false
      }

      if (pass) {
        const op = wh.getString("filter_text_match_operator") || "none"
        if (op !== "none") {
          const val = (wh.getString("filter_text_match_value") || "").trim()
          if (val) {
            const text = (msg.getString("text") || "").toLowerCase()
            const needle = val.toLowerCase()
            if (op === "equals") pass = (text === needle)
            else if (op === "contains") pass = (text.indexOf(needle) !== -1)
          }
        }
      }
    } catch (fErr) {
      console.log("telegram_messages hook: filter error:", String(fErr))
      continue
    }
    if (!pass) continue

    // Reescreve URL pública → Docker interno (bypass Traefik)
    let targetUrl = wh.getString("url")
    for (const pub in INTERNAL_URL_MAP) {
      if (targetUrl.indexOf(pub) === 0) {
        targetUrl = INTERNAL_URL_MAP[pub] + targetUrl.substring(pub.length)
        break
      }
    }

    // buildPayload (inline — não pode ser helper top-level)
    // TODO(schema): se o seu workflow n8n espera um shape específico tipo
    // {objeto: {prop, nume, sub: {name}}}, ajustar este objeto. O schema
    // atual funciona como genérico — webhook nodes n8n costumam aceitar
    // JSON arbitrário se não tiver validação estrita de schema.
    const payload = JSON.stringify({
      event: "telegram.message",
      webhook_id: wh.id,
      webhook_name: wh.getString("name"),
      session: {
        pb_id: session.id,
        session_id: session.getString("session_id"),
        phone: session.getString("phone"),
        name: session.getString("name") || "",
      },
      message: {
        id: msg.id,
        chat_id: msg.getNumber("chat_id"),
        chat_type: msg.getString("chat_type"),
        chat_title: msg.getString("chat_title") || "",
        direction: msg.getString("direction"),
        sender_id: msg.getNumber("sender_id"),
        sender_name: msg.getString("sender_name") || "",
        text: msg.getString("text") || "",
        timestamp: msg.getString("created"),
      },
    })

    // POST pro webhook. $http.send é síncrono, timeout em segundos, throws
    // em erro. Se a URL interna (http://n8n:5678) bater certinho, retorna
    // em <100ms. Se timeout/dns/route falhar, throws em até 10s.
    try {
      const resp = $http.send({
        url: targetUrl,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        timeout: 10,
      })
      delivered++
      console.log(
        "telegram_messages hook: delivered msg=" + msg.id +
        " webhook=" + wh.id +
        " url=" + targetUrl +
        " status=" + resp.statusCode,
      )
    } catch (err) {
      if (!firstError) firstError = String(err).substring(0, 500)
      console.log(
        "telegram_messages hook: webhook FAILED msg=" + msg.id +
        " webhook=" + wh.id +
        " url=" + targetUrl +
        " err=" + String(err).substring(0, 200),
      )
    }
  }

  // 4) Log final. NÃO tentamos persistir delivered_count/delivery_error
  // porque $app.dao().saveRecord no AfterSuccess é descartado pela
  // transação (PB 0.40+).
  console.log(
    "telegram_messages hook: msg=" + msg.id +
    " session=" + sessionRel +
    " webhooks=" + webhooks.length +
    " delivered=" + delivered +
    (firstError ? " firstError=" + firstError : ""),
  )
}, "telegram_messages")