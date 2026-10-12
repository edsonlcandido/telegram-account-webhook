/// <reference path="../pb_data/types.d.ts" />

// =============================================================================
// Proxy reverso: encaminha as chamadas /api-telegram/* do frontend (mesma
// origem) para o servico Telegram API (FastAPI) via DNS interno do Docker.
// =============================================================================
//
// Por que esse prefixo e nao /api/*:
//   O namespace /api/ e nativo do PocketBase (/api/collections, /api/health,
//   /api/records, /api/files, /api/batch, /api/logs, /api/imports, /api/cron,
//   /api/email-templates, /api/backups, /api/realtime, /api/settings, etc).
//   Usar /api/* num routerAdd do JSVM mistura o namespace e cria risco de
//   colisao com rotas nativas adicionadas em versoes futuras do PB. O
//   prefixo /api-telegram/* isola 100% esse hook do resto.
//
// Por que isso existe:
//   O frontend Vue chama /api-telegram/send-code, /api-telegram/sessions
//   etc. via URL relativa (mesma origem = este PB). O PB nao implementa
//   essas rotas, e nao ha middleware HTTP na frente pra repassar. Entao o
//   hook abaixo intercepta cada /api-telegram/* e faz $http.send pro FastAPI
//   usando TELEGRAM_API_URL (variavel de ambiente do servico PB no Easypanel).
//
// O frontend envia o JWT do PocketBase no header `Authorization: Bearer <jwt>`;
// este hook apenas repassa o header adiante. O FastAPI valida o token via
// dependency `verify_pb_auth` (consulta /auth-refresh no proprio PB).
//
// Sem Promise / sem await: $http.send e sincrono. Cada handler bloqueia a
// thread de request do PB, mas como o FastAPI responde rapido (telethon e
// async, mas a chamada HTTP externa e curta), o custo e desprezivel.
// =============================================================================

// Resolucao do upstream uma unica vez por handler (top-level let/const NAO
// sao compartilhados entre handlers no JSVM, conforme nota da skill
// pocketbase-jsvm - declarar dentro do helper).
function getUpstreamBase() {
    let base = $os.getenv("TELEGRAM_API_URL");
    if (!base) {
        // Fallback de emergencia caso a env nao esteja configurada no servico.
        // No Easypanel o DNS interno segue o padrao <project>_<service>.
        base = "http://eh-tudo_telegram-account-webhook-telegram:80";
    }
    return base.replace(/\/+$/, "");
}

function proxyToFastApi(e, method, upstreamPath) {
    const base = getUpstreamBase();
    const url = base + upstreamPath;

    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };

    // Repassa o Authorization (header em lowercase no PB >= 0.23).
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }

    // Repassa o body cru (somente em metodos que carregam body).
    let body = null;
    if (method !== "GET" && method !== "DELETE") {
        if (reqInfo.body && (reqInfo.body.length || 0) > 0) {
            body = toString(reqInfo.body);
        }
    }

    let resp;
    try {
        resp = $http.send({
            url: url,
            method: method,
            body: body,
            header: headers,
            timeout: 60,
        });
    } catch (err) {
        console.log(`[api-proxy] upstream ${method} ${upstreamPath} falhou: ${err.message}`);
        throw new Error("Servico Telegram API indisponivel");
    }

    let data;
    if (resp.status >= 200 && resp.status < 300) {
        try {
            data = resp.json;
        } catch (_) {
            data = toString(resp.body);
        }
    } else {
        // Repassa o body de erro como veio (FastAPI retorna {detail: "..."}).
        try {
            data = resp.json;
        } catch (_) {
            data = { detail: toString(resp.body) };
        }
    }

    if (typeof data === "string") {
        return e.string(resp.status, data);
    }
    return e.json(resp.status, data);
}

// -----------------------------------------------------------------------------
// Rotas - prefixo /api-telegram/* para isolar do namespace nativo /api/* do PB
// -----------------------------------------------------------------------------

routerAdd("POST", "/api-telegram/send-code", (e) => {
    return proxyToFastApi(e, "POST", "/api/send-code");
});

routerAdd("POST", "/api-telegram/verify-code", (e) => {
    return proxyToFastApi(e, "POST", "/api/verify-code");
});

routerAdd("POST", "/api-telegram/set-webhook", (e) => {
    return proxyToFastApi(e, "POST", "/api/set-webhook");
});

routerAdd("GET", "/api-telegram/sessions", (e) => {
    return proxyToFastApi(e, "GET", "/api/sessions");
});

routerAdd("DELETE", "/api-telegram/session/{sessionId}", (e) => {
    // Extrai o sessionId do path requisitado (PB nao expoe params nomeados
    // de forma simples nas rotas custom; caminho mais robusto e split).
    const parts = e.requestInfo().path.split("/").filter(Boolean);
    const sessionId = parts[parts.length - 1] || "";
    return proxyToFastApi(e, "DELETE", `/api/session/${sessionId}`);
});

routerAdd("POST", "/api-telegram/test-webhook", (e) => {
    return proxyToFastApi(e, "POST", "/api/test-webhook");
});
