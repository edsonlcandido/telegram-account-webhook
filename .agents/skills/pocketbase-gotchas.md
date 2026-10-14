# PocketBase 0.40.x - JS Routing e Hooks

## ⚠️ ATENÇÃO - Leia antes de mexer

### NÃO invente sintaxe! Use a documentação oficial.

- **Routing**: https://pocketbase.io/docs/js-routing/
- **JS Overview**: https://pocketbase.io/docs/js-overview/

---

## O que aprendemos (trial & error)

### Histórico de erros

1. **Flag errada**: `--dirs` não existe → usar `--publicDir`
2. **Hook syntax**: `$apis.static()` é o certo (não `c.staticFile()`)
3. **Wildcard**: `{path?}` não existe → usar `{path...}` (3 pontos)
4. **Dockerfile npm workspaces**: precisa copiar TODOS os arquivos de config
5. **Versão antiga**: 0.22.x tem APIs diferentes do 0.40.x

---

## Versão Atual
- PocketBase 0.40.5 (linux_amd64)
- Verificar versão com: `./pocketbase --version`

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

---

## Migrations JS (PB 0.40+)

> **Skill dedicada:** `.agents/skills/pocketbase-migrations/SKILL.md` —
> cobre em profundidade as 2 regras, sintaxe de Field, timestamps
> BRT-as-UTC, procedimento de teste local e tabela de erros. Esta
> seção é um resumo / histórico do que foi aprendido; consulte a skill
> dedicada antes de mexer em `pb_migrations/`.

### Regra de ouro: NUNCA editar uma migration depois de commitada

O PB registra as migrations aplicadas em `pb_data/_migrations` (tabela SQLite).
Se você edita o conteúdo de uma migration existente, o PB **não reaplica** —
o registro antigo continua lá e o seu código novo nunca roda. Pior: se a
migration antiga falhou e o estado ficou parcial, a única forma de consertar
é criar uma **nova** migration defensiva que cobre o caso.

**Errado** (pior que parece — vira código morto):
```js
// 1791929716_*.js (errado)
// Editar o conteúdo deste arquivo não muda nada em produção — o PB já
// marcou como "tentada" e não vai reaplicar.
```

**Certo** (criar nova migration com timestamp maior):
```js
// 1791930807_fix_*.js  ← novo arquivo, timestamp > anterior
migrate((app) => {
  // Idempotente: checa o estado antes de mexer.
  if (!collection.fields.getByName("name")) {
    collection.fields.add(new Field({...}))
    app.save(collection)
  }
})
```

### Timestamps de migration

Use timestamp Linux **com timezone -3 (BRT-as-UTC)**. Exemplo: agora é
`2026-10-13 22:36 BRT` → epoch UTC = `1791941800` → timestamp BRT-as-UTC
= `1791941800 - 3*3600` = `1791931000`. Em PowerShell:

```powershell
[DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - 3*3600
```

Mais importante que o cálculo exato: o timestamp da migration tem que ser
**maior** que o da última. Sempre verifique o maior existente em
`pocketbase/pb_migrations/` antes de criar.

### Sintaxe de Field em PB 0.40+

Em PB 0.40+, as opções de field vão **direto no field** (não dentro de
`options: {}` como em PB <0.22). Errado vs certo:

```js
// ❌ ERRADO (PB 0.22): opções aninhadas em `options`
{ name: "filter_direction", type: "select", required: false,
  options: { maxSelect: 1, values: ["all", "incoming"] } }
// Erro em prod: "(values: cannot be blank.)"

// ✅ CERTO (PB 0.40+): opções diretas no field
{ name: "filter_direction", type: "select", required: false,
  values: ["all", "incoming", "outgoing"], maxSelect: 1 }
```

Por tipo:

| Tipo | Campos chave (no field, não em `options`) |
|---|---|
| `text` | `max`, `min`, `pattern`, `required` |
| `url` | `exceptDomains`, `onlyDomains`, `required` |
| `bool` | `required` |
| `select` | `values: string[]`, `maxSelect`, `required` |
| `relation` | `collectionId`, `cascadeDelete`, `minSelect`, `maxSelect`, `required` |

### Adicionar field em collection existente

**Errado** (objeto literal): `collection.fields.add({name, type, max})`
falha com `"could not convert [object Object] to core.Field"`.

**Certo** (classe `Field`):
```js
const col = app.findCollectionByNameOrId("telegram_sessions")
if (!col.fields.getByName("name")) {
  col.fields.add(new Field({ name: "name", type: "text", max: 60, required: false }))
  app.save(col)
}
```

Shorthand válido: `col.fields.add("name")` cria um `TextField` básico
(precisa editar as props depois se quiser `max`/`min`).

### Testar migrations ANTES de commit/deploy

O usuário fica com 502 Gateway no webapp se a migration quebrar em prod.
**Sempre** rodar localmente primeiro:

```bash
# 1) Baixar o binário (já tem script: scripts/pocketbase.js)
cd pocketbase
node ../scripts/pocketbase.js    # baixa + extrai via PowerShell Expand-Archive

# 2) Resetar pb_data pra estado limpo
mavis-trash pb_data
# (ou `rm -- pocketbase/pb_data` se o runtime permitir)

# 3) Rodar PB em foreground ou background (ele aplica as migrations no startup)
./pocketbase.exe serve --http=127.0.0.1:8090

# 4) Inspecionar o SQLite gerado em pb_data/data.db
sqlite3 pb_data/data.db "SELECT file FROM _migrations ORDER BY file"
sqlite3 pb_data/data.db "PRAGMA table_info(telegram_webhooks)"

# 5) Se algum erro no startup ("failed to apply migration..."), corrigir
#    e voltar pro passo 2. NÃO comitar até subir limpo.
```

Logs de erro comuns em migrations quebradas:
- `could not convert [object Object] to core.Field` → faltou `new Field({...})`
- `(collectionId: cannot be blank.)` → `collectionId` deve ser direto, não em `options`
- `(values: cannot be blank.)` → mesmo problema pra select
- `(min: cannot be blank.)` em migration que antes funcionava → checar se a migration anterior realmente rodou (pode estar rodando 2x)
