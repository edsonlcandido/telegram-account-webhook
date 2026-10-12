# PocketBase 0.40.x - JS Routing e Hooks

## ⚠️ ATENÇÃO - Leia antes de mexer

### NÃO invente sintaxe! Use a documentação oficial.

- **Routing**: https://pocketbase.io/docs/js-routing/
- **JS Overview**: https://pocketbase.io/docs/js-overview/

---

## Versão Usada
- PocketBase 0.40.5 (linux_amd64)

## Rota Catch-All para SPA

### Sintaxe Correta: `{path...}` (TRÊS pontos)

O Go usa `{name...}` para capturar múltiplos segmentos.

```javascript
// ERRADO - não existe
routerAdd("GET", "/app/{path?}", ...)  // ❌ bad wildcard name
routerAdd("GET", "/app/{path}", ...)   // ❌ só captura 1 segmento

// CERTO
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", false))
```

| Sintaxe | Significado |
|---------|-------------|
| `{path}` | Parâmetro único |
| `{path...}` | Catch-all (múltiplos segmentos) - **3 pontos** |
| `{path?}` | **NÃO EXISTE** |

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
- `spaFallback`: `false` = 404 se não encontrar, `true` = retorna index.html (SPA mode)

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

## Dockerfile - Versão como ARG

```dockerfile
ARG POCKETBASE_VERSION=0.40.5

RUN wget https://github.com/pocketbase/pocketbase/releases/download/v${POCKETBASE_VERSION}/pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && unzip pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && rm pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && chmod +x pocketbase

CMD ["./pocketbase", "serve", "--http=0.0.0.0:8090"]
```

**⚠️ NÃO usar imagem DockerHub** - não existe `pocketbase/pocketbase`

---

## Erros Comuns

### ❌ `bad wildcard name "path?"`
- Causa: `{path?}` não existe no PocketBase/Go
- Solução: usar `{path}` para parâmetro único ou `{path...}` para catch-all

### ❌ `Object has no member 'static'`
- Causa: Versão muito antiga do PocketBase (< 0.30)
- Solução: Atualizar para 0.40.x

### ❌ `tsc` não encontrado no Docker build
- Causa: não copiou os arquivos de config do projeto
- Solução: copiar TODOS os arquivos necessários

---

## Dockerfile npm workspaces - Arquivos Necessários

O Dockerfile DEVE copiar todos os arquivos de config, não só package.json:

```dockerfile
# ✅ CERTO - copia tudo
COPY apps/landing/package*.json ./apps/landing/
COPY apps/landing/tsconfig.json ./apps/landing/
COPY apps/landing/vite.config.ts ./apps/landing/
COPY apps/landing/postcss.config.js ./apps/landing/
COPY apps/landing/tailwind.config.js ./apps/landing/
COPY apps/landing/src ./apps/landing/src/
COPY apps/landing/index.html ./apps/landing/
COPY apps/landing/public ./apps/landing/public/
```

```dockerfile
# ❌ ERRADO - só package.json não funciona
COPY package*.json ./
COPY apps/landing/package*.json ./apps/landing/
```

---

## Vue App - URL do PocketBase em Produção

Em produção, o Vue app é servido pelo PocketBase na **mesma origem**. Usar URL relativa ou `window.location.origin`.

```typescript
// services/pocketbase.ts
function getPocketBaseUrl(): string {
  // Em produção (mesma origem), usar origin atual
  if (import.meta.env.PROD) {
    return window.location.origin
  }
  // Em dev, usar localhost
  return 'http://localhost:8090'
}

const pb = new PocketBase(getPocketBaseUrl())
```

`.env.production`:
```env
VITE_POCKETBASE_URL=/
```

---

## Variáveis de Ambiente - Comunicação Interna Docker

O PocketBase (serviço Application) precisa saber a URL do Telegram API para fazer chamadas internas:

```env
# Serviço Application (PocketBase)
TELEGRAM_API_URL=http://telegram-api:8000
```

O backend Telegram API (FastAPI) precisa saber a URL do PocketBase:

```env
# Serviço Telegram API
POCKETBASE_URL=http://pocketbase:8090
```

**Rede Docker interna:**
- Application → `http://telegram-api:8000`
- Telegram API → `http://pocketbase:8090`

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
