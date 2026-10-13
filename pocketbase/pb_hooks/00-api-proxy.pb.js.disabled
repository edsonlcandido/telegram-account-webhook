/// <reference path="../pb_data/types.d.ts" />

// =============================================================================
// TESTE: rota isolada que nao chama $http.send nenhum. Se retornar "ok",
// o e.string funciona e o problema e especifico do fluxo de proxy.
// Se nao retornar "ok", o e.string do JSVM do PB 0.40.5 tem bug.
// =============================================================================
routerAdd("GET", "/api-telegram-test", (e) => {
    return e.string(200, "ok");
});

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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // Decodifica Uint8Array -> string usando o helper global toString do JSVM
    // (documentado na skill pocketbase-jsvm). O log anterior confirmou que
    // toString funciona, mas e.json(status, obj) nao estava enviando o body.
    // Workaround: sempre retornar o body como string, com Content-Type JSON
    // setado no header, e o frontend faz JSON.parse se precisar.
    let text = "";
    if (resp.body && resp.body.length > 0) {
        if (typeof toString === "function") {
            try { text = toString(resp.body); } catch (_) {}
        }
        if (!text) {
            for (let i = 0; i < resp.body.length; i++) {
                text += String.fromCharCode(resp.body[i] & 0xFF);
            }
        }
    }
    // Workaround para bug do JSVM do PB 0.40.5: depois de chamar $http.send,
    // o e.string nao consegue mais escrever o body (teste isolado sem $http.send
    // retorna "ok" corretamente). Zerar a referencia ao resp antes do e.string
    // tenta forcar o GC a liberar o buffer interno que conflita.
    const statusToReturn = resp.status;
    const finalBody = text;
    resp = null;
    return e.string(statusToReturn, finalBody);
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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // Decodifica Uint8Array -> string usando o helper global toString do JSVM
    // (documentado na skill pocketbase-jsvm). O log anterior confirmou que
    // toString funciona, mas e.json(status, obj) nao estava enviando o body.
    // Workaround: sempre retornar o body como string, com Content-Type JSON
    // setado no header, e o frontend faz JSON.parse se precisar.
    let text = "";
    if (resp.body && resp.body.length > 0) {
        if (typeof toString === "function") {
            try { text = toString(resp.body); } catch (_) {}
        }
        if (!text) {
            for (let i = 0; i < resp.body.length; i++) {
                text += String.fromCharCode(resp.body[i] & 0xFF);
            }
        }
    }
    // Workaround para bug do JSVM do PB 0.40.5: depois de chamar $http.send,
    // o e.string nao consegue mais escrever o body (teste isolado sem $http.send
    // retorna "ok" corretamente). Zerar a referencia ao resp antes do e.string
    // tenta forcar o GC a liberar o buffer interno que conflita.
    const statusToReturn = resp.status;
    const finalBody = text;
    resp = null;
    return e.string(statusToReturn, finalBody);
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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // Decodifica Uint8Array -> string usando o helper global toString do JSVM
    // (documentado na skill pocketbase-jsvm). O log anterior confirmou que
    // toString funciona, mas e.json(status, obj) nao estava enviando o body.
    // Workaround: sempre retornar o body como string, com Content-Type JSON
    // setado no header, e o frontend faz JSON.parse se precisar.
    let text = "";
    if (resp.body && resp.body.length > 0) {
        if (typeof toString === "function") {
            try { text = toString(resp.body); } catch (_) {}
        }
        if (!text) {
            for (let i = 0; i < resp.body.length; i++) {
                text += String.fromCharCode(resp.body[i] & 0xFF);
            }
        }
    }
    // Workaround para bug do JSVM do PB 0.40.5: depois de chamar $http.send,
    // o e.string nao consegue mais escrever o body (teste isolado sem $http.send
    // retorna "ok" corretamente). Zerar a referencia ao resp antes do e.string
    // tenta forcar o GC a liberar o buffer interno que conflita.
    const statusToReturn = resp.status;
    const finalBody = text;
    resp = null;
    return e.string(statusToReturn, finalBody);
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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // Decodifica Uint8Array -> string usando o helper global toString do JSVM
    // (documentado na skill pocketbase-jsvm). O log anterior confirmou que
    // toString funciona, mas e.json(status, obj) nao estava enviando o body.
    // Workaround: sempre retornar o body como string, com Content-Type JSON
    // setado no header, e o frontend faz JSON.parse se precisar.
    let text = "";
    if (resp.body && resp.body.length > 0) {
        if (typeof toString === "function") {
            try { text = toString(resp.body); } catch (_) {}
        }
        if (!text) {
            for (let i = 0; i < resp.body.length; i++) {
                text += String.fromCharCode(resp.body[i] & 0xFF);
            }
        }
    }
    // Workaround para bug do JSVM do PB 0.40.5: depois de chamar $http.send,
    // o e.string nao consegue mais escrever o body (teste isolado sem $http.send
    // retorna "ok" corretamente). Zerar a referencia ao resp antes do e.string
    // tenta forcar o GC a liberar o buffer interno que conflita.
    const statusToReturn = resp.status;
    const finalBody = text;
    resp = null;
    return e.string(statusToReturn, finalBody);
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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // Decodifica Uint8Array -> string usando o helper global toString do JSVM
    // (documentado na skill pocketbase-jsvm). O log anterior confirmou que
    // toString funciona, mas e.json(status, obj) nao estava enviando o body.
    // Workaround: sempre retornar o body como string, com Content-Type JSON
    // setado no header, e o frontend faz JSON.parse se precisar.
    let text = "";
    if (resp.body && resp.body.length > 0) {
        if (typeof toString === "function") {
            try { text = toString(resp.body); } catch (_) {}
        }
        if (!text) {
            for (let i = 0; i < resp.body.length; i++) {
                text += String.fromCharCode(resp.body[i] & 0xFF);
            }
        }
    }
    // Workaround para bug do JSVM do PB 0.40.5: depois de chamar $http.send,
    // o e.string nao consegue mais escrever o body (teste isolado sem $http.send
    // retorna "ok" corretamente). Zerar a referencia ao resp antes do e.string
    // tenta forcar o GC a liberar o buffer interno que conflita.
    const statusToReturn = resp.status;
    const finalBody = text;
    resp = null;
    return e.string(statusToReturn, finalBody);
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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // Decodifica Uint8Array -> string usando o helper global toString do JSVM
    // (documentado na skill pocketbase-jsvm). O log anterior confirmou que
    // toString funciona, mas e.json(status, obj) nao estava enviando o body.
    // Workaround: sempre retornar o body como string, com Content-Type JSON
    // setado no header, e o frontend faz JSON.parse se precisar.
    let text = "";
    if (resp.body && resp.body.length > 0) {
        if (typeof toString === "function") {
            try { text = toString(resp.body); } catch (_) {}
        }
        if (!text) {
            for (let i = 0; i < resp.body.length; i++) {
                text += String.fromCharCode(resp.body[i] & 0xFF);
            }
        }
    }
    // Workaround para bug do JSVM do PB 0.40.5: depois de chamar $http.send,
    // o e.string nao consegue mais escrever o body (teste isolado sem $http.send
    // retorna "ok" corretamente). Zerar a referencia ao resp antes do e.string
    // tenta forcar o GC a liberar o buffer interno que conflita.
    const statusToReturn = resp.status;
    const finalBody = text;
    resp = null;
    return e.string(statusToReturn, finalBody);
});
