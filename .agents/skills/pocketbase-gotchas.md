# PocketBase Gotchas - Telegram Webhook Hub

## Versão Usada
- PocketBase 0.40.5 (linux_amd64)

## Dockerfile Correto

Usar `ARG POCKETBASE_VERSION` para controlar a versão:

```dockerfile
ARG POCKETBASE_VERSION=0.40.5

RUN wget https://github.com/pocketbase/pocketbase/releases/download/v${POCKETBASE_VERSION}/pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && unzip pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && rm pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && chmod +x pocketbase
```

### NÃO usar imagem DockerHub
```dockerfile
# ERRADO - imagem não existe
FROM pocketbase/pocketbase:latest
```

---

## Problemas Conhecidos (versão 0.22.x vs 0.40.x)

### $apis.static() - depende da versão
**Versão 0.22.x (não existe):**
```javascript
// ERRO: Object has no member 'static'
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", true))
```

**Versão 0.40.x:**
```javascript
// Certo
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", true))
```

**Alternativa segura (funciona em todas):**
```javascript
routerAdd("GET", "/app/{path?}", function(c) {
    try {
        return c.staticFile("pb_public/app/" + (c.pathParam("path") || ""))
    } catch (e) {
        return c.staticFile("pb_public/app/index.html")
    }
})
```

---

## SPA Routing Hook (pb_hooks/main.pb.js)

```javascript
/// <reference path="../pb_data/types.d.ts" />

/**
 * SPA Routing - Serve Vue app em /app/*
 * Compatível com PocketBase 0.40.x
 */

routerAdd("GET", "/app/{path?}", function(c) {
    const path = c.pathParam("path")
    if (!path || path === "") {
        return c.staticFile("pb_public/app/index.html")
    }
    try {
        return c.staticFile("pb_public/app/" + path)
    } catch (e) {
        return c.staticFile("pb_public/app/index.html")
    }
})
```

---

## Comandos Úteis

### Verificar versão
```bash
./pocketbase --version
```

### Help completo
```bash
./pocketbase serve --help
```

### Testar localmente
```bash
./pocketbase serve --http=127.0.0.1:8090
```

### Buildar e testar
```bash
# Build do frontend
cd apps/landing && npm run build
cd apps/web && npm run build

# Rodar pocketbase localmente
./pocketbase serve
```

---

## Estrutura de Pastas PocketBase

```
pocketbase/
├── pocketbase          # executável
├── pb_hooks/          # hooks JS
│   └── main.pb.js
├── pb_migrations/     # migrations
├── pb_data/           # dados (SQLite + uploads)
└── pb_public/         # arquivos estáticos (SPA)
    ├── index.html     # landing page
    └── app/           # web app
        └── index.html # Vue SPA
```

---

## Referências

- [Documentação oficial](https://pocketbase.io/docs/)
- [GitHub Releases](https://github.com/pocketbase/pocketbase/releases)
- [Sponsors API](https://pocketbase.io/docs/js-overview/)
