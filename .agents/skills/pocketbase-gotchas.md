# PocketBase Gotchas - Telegram Webhook Hub

## Versão Usada
- PocketBase 0.22.18 (linux_amd64)

## Problemas Conhecidos

### 1. Flag --dirs NÃO existe
**ERRADO:**
```dockerfile
CMD ["serve", "--http=0.0.0.0:8090", "--dirs=/app/public"]
```

**CERTO:**
```dockerfile
CMD ["serve", "--http=0.0.0.0:8090", "--publicDir=/app/public"]
```

A flag correta para definir o diretório de arquivos públicos é `--publicDir`.

---

### 2. $apis.static() NÃO existe
**ERRADO (gera "Object has no member 'static'"):**
```javascript
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", true))
```

**CERTO (usar c.staticFile):**
```javascript
routerAdd("GET", "/app/{path?}", function(c) {
    c.staticFile("pb_public/app/index.html")
})
```

Alternativa com index fallback manual:
```javascript
routerAdd("GET", "/app/{path?}", function(c) {
    try {
        return c.staticFile("pb_public/app/" + c.pathParam("path"))
    } catch (e) {
        return c.staticFile("pb_public/app/index.html")
    }
})
```

---

### 3. Imagem DockerHub NÃO existe
**ERRADO:**
```dockerfile
FROM pocketbase/pocketbase:latest
```

**CERTO (baixar do GitHub releases):**
```dockerfile
RUN apk add --no-cache curl unzip && \
    curl -L -o pocketbase.zip https://github.com/pocketbase/pocketbase/releases/download/v0.22.18/pocketbase_0.22.18_linux_amd64.zip && \
    unzip pocketbase.zip && \
    rm pocketbase.zip && \
    chmod +x pocketbase
```

---

### 4. Referência de Tipos
Se hooks derem erro de tipos, adicionar no início do arquivo:
```javascript
/// <reference path="../pb_data/types.d.ts" />
```

---

## Comandos Úteis

### Verificar versão
```bash
./pocketbase --version
```

### Help
```bash
./pocketbase serve --help
```

### Testar localmente
```bash
./pocketbase serve --http=127.0.0.1:8090 --publicDir=./public
```
