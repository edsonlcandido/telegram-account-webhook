/// <reference path="../pb_data/types.d.ts" />

// =============================================================================
// Proxy reverso: encaminha /api-telegram/* do frontend (mesma origem) para o
// servico Telegram API (FastAPI).
// =============================================================================
// ATENCAO: cada handler e 100% self-contained. Nenhum `const`/`let`/`function`
// declarado no top-level do arquivo, porque o JSVM do PB executa cada callback
// de routerAdd em um VM context separado do pool - qualquer referencia a
// declaracao do top-level (mesmo `const`) da `ReferenceError: not defined` em
// producao. Cada handler le a env, monta o URL e faz o $http.send sozinho.
// =============================================================================

routerAdd("POST", "/api-telegram/send-code", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const url = base.replace(/\/+$/, "") + "/api/send-code";
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    const body = reqInfo.body && (reqInfo.body.length || 0) > 0 ? toString(reqInfo.body) : null;
    let resp;
    try {
        resp = $http.send({ url: url, method: "POST", body: body, header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("POST", "/api-telegram/verify-code", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const url = base.replace(/\/+$/, "") + "/api/verify-code";
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    const body = reqInfo.body && (reqInfo.body.length || 0) > 0 ? toString(reqInfo.body) : null;
    let resp;
    try {
        resp = $http.send({ url: url, method: "POST", body: body, header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("POST", "/api-telegram/set-webhook", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const url = base.replace(/\/+$/, "") + "/api/set-webhook";
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    const body = reqInfo.body && (reqInfo.body.length || 0) > 0 ? toString(reqInfo.body) : null;
    let resp;
    try {
        resp = $http.send({ url: url, method: "POST", body: body, header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("GET", "/api-telegram/sessions", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const url = base.replace(/\/+$/, "") + "/api/sessions";
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    let resp;
    try {
        resp = $http.send({ url: url, method: "GET", header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("DELETE", "/api-telegram/session/{sessionId}", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const parts = e.requestInfo().path.split("/").filter(Boolean);
    const sessionId = parts[parts.length - 1] || "";
    const url = base.replace(/\/+$/, "") + "/api/session/" + sessionId;
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    let resp;
    try {
        resp = $http.send({ url: url, method: "DELETE", header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("POST", "/api-telegram/test-webhook", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const url = base.replace(/\/+$/, "") + "/api/test-webhook";
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    const body = reqInfo.body && (reqInfo.body.length || 0) > 0 ? toString(reqInfo.body) : null;
    let resp;
    try {
        resp = $http.send({ url: url, method: "POST", body: body, header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});
