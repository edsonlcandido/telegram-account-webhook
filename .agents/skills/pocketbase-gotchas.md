# PocketBase 0.40.x - JS Routing e Hooks

## Versão Usada
- PocketBase 0.40.5 (linux_amd64)

## Documentação Oficial
- JS Overview: https://pocketbase.io/docs/js-overview/
- JS Routing: https://pocketbase.io/docs/js-routing/
- JS Event Hooks: https://pocketbase.io/docs/js-event-hooks/

---

## Rota Catch-All para SPA

### Sintaxe Correta: `{path...}` (três pontos)

O Go usa `{name...}` para capturar múltiplos segmentos.

```javascript
// ERRADO - não existe
routerAdd("GET", "/app/{path?}", ...)
routerAdd("GET", "/app/{path}", ...)

// CERTO
routerAdd("GET", "/app/{path...}", function(e) {
    // captura /app, /app/, /app/foo, /app/foo/bar
})
```

---

## Servir Arquivos Estáticos

### Usar `$apis.static()` - é assim que funciona!

```javascript
// Serve todo o diretório com fallback SPA
routerAdd("GET", "/{path...}", $apis.static("pb_public", false))
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", false))
```

**Parâmetros:**
- `dirPath`: caminho do diretório (relativo ao working dir)
- `spaFallback`: `false` = retorna 404 se não encontrar, `true` = retorna index.html (SPA mode)

---

## Hook Completo para Vue SPA

```javascript
/// <reference path="../pb_data/types.d.ts" />

// Landing page na raiz
routerAdd("GET", "/{path...}", $apis.static("pb_public", false))

// Web app em /app/*
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", false))
```

---

## Parâmetros de Rota

```javascript
// Obter valor do parâmetro
routerAdd("GET", "/users/{id}", function(e) {
    const id = e.request.pathValue("id")
    return e.json(200, { userId: id })
})

// Catch-all (múltiplos segmentos)
routerAdd("GET", "/static/{path...}", function(e) {
    const path = e.request.pathValue("path")
    // path = "css/style.css" para /static/css/style.css
})
```

---

## Helpers Disponíveis no contexto `e`

```javascript
// Respostas JSON
e.json(200, { data: "value" })
e.json(404, { error: "Not found" })

// Arquivos
e.fileFS($os.dirFS("/path"), "file.txt")

// static() helper
$apis.static("pb_public", false)
$apis.static("pb_public/app", true)
```

---

## Dockerfile - Versão como ARG

```dockerfile
ARG POCKETBASE_VERSION=0.40.5

RUN wget https://github.com/pocketbase/pocketbase/releases/download/v${POCKETBASE_VERSION}/pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && unzip pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && rm pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && chmod +x pocketbase

CMD ["./pocketbase", "serve", "--http=0.0.0.0:8090"]
```

---

## Erros Comuns

### ❌ `bad wildcard name "path?"`
- `{path?}` não existe
- Usar `{path}` para parâmetro único ou `{path...}` para catch-all

### ❌ `Object has no member 'static'`
- Versão muito antiga do PocketBase (0.22.x)
- Atualizar para 0.40.x

### ❌ Hook não carrega
- Verificar se arquivo está em `pb_hooks/main.pb.js`
- Verificar sintaxe JavaScript

---

## Testar Localmente

```bash
# Build
cd apps/landing && npm run build
cd apps/web && npm run build

# Baixar pocketbase
wget https://github.com/pocketbase/pocketbase/releases/download/v0.40.5/pocketbase_0.40.5_linux_amd64.zip
unzip pocketbase_0.40.5_linux_amd64.zip

# Criar estrutura
mkdir -p pb_hooks pb_public/app

# Copiar hooks e dist
cp pocketbase/pb_hooks/main.pb.js pb_hooks/
cp -r apps/landing/dist/* pb_public/
cp -r apps/web/dist/* pb_public/app/

# Rodar
./pocketbase serve
```
