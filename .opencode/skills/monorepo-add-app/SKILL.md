---
name: monorepo-add-app
description: Adicionar um novo workspace (ex: `apps/admin`, `apps/blog`, `apps/mobile`) ao monorepo do template, configurando Vite, env, script raiz e wiring com Vite proxy / PocketBase build pipeline. Use quando o usuário quiser um terceiro app no monorepo ou migrar um app Vue standalone pra cá.
---

# Monorepo — Adicionar novo workspace

`workspaces: ["apps/*"]` no `package.json` raiz puxa automaticamente qualquer pasta em `apps/`. Então **basta criar `apps/<nome>/`** com seu próprio `package.json`. Mas o template tem scripts acoplados ao processo de build — precisa plugar no fluxo.

## Passo a passo (exemplo: `apps/admin`)

### 1. Criar estrutura

```bash
mkdir -p apps/admin/src/views apps/admin/src/stores apps/admin/src/services apps/admin/src/router
```

### 2. `apps/admin/package.json` mínimo

```json
{
  "name": "admin",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@heroicons/vue": "^2.2.0",
    "pinia": "^2.3.1",
    "pocketbase": "^0.26.7",
    "vue": "^3.5.13",
    "vue-router": "^4.5.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4.0.1",
    "@vitejs/plugin-vue": "^5.2.1",
    "tailwindcss": "^4.0.1",
    "typescript": "~5.9.3",
    "vite": "^6.0.3",
    "vue-tsc": "^2.2.0"
  }
}
```

### 3. `apps/admin/vite.config.ts`

```ts
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'url'
import { dirname } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, 'VITE_')
  const pbUrl = env.VITE_POCKETBASE_URL || 'http://localhost:8090'

  return {
    plugins: [vue()],
    base: '/admin/',          // ⭐ prefixo próprio
    server: {
      port: 5175,             // porta única
      proxy: {
        '/api': { target: pbUrl, changeOrigin: true },
        '/_':   { target: pbUrl, changeOrigin: true },
      },
    },
  }
})
```

### 4. `apps/admin/index.html`

```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Admin</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

### 5. `apps/admin/src/main.ts`

```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'

createApp(App).use(createPinia()).use(router).mount('#app')
```

### 6. `apps/admin/src/style.css`

```css
@import "tailwindcss";
```

### 7. `apps/admin/tsconfig.json`

```json
{
  "extends": "../../tsconfig.json",
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

### 8. `apps/admin/tsconfig.node.json`

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

## Plugar no fluxo de dev (root)

Edite `package.json` raiz:

```json
{
  "scripts": {
    "dev:admin": "cd apps/admin && npm run dev -- --port 5175",
    "dev": "concurrently -k -n PB,LANDING,WEB,ADMIN -c blue,green,magenta,yellow \"npm:dev:pb\" \"npm:dev:landing\" \"npm:dev:web\" \"npm:dev:admin\""
  }
}
```

## Plugar no build de produção

### Adicionar copy script

`scripts/copy-admin.js`:

```js
#!/usr/bin/env node
import { copyFileSync, mkdirSync, existsSync, readdirSync, statSync, rmSync } from 'fs'
import { join } from 'path'
import { fileURLToPath } from 'url'
import { dirname } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const rootDir = join(__dirname, '..')
const sourceDir = join(rootDir, 'apps', 'admin', 'dist')
const targetDir = join(rootDir, 'pocketbase', 'pb_public', 'admin')

function copyRecursive(src, dest) {
  if (!existsSync(src)) {
    console.error(`❌ Diretório ${src} não existe. Rode npm run build:admin antes.`)
    process.exit(1)
  }
  const stats = statSync(src)
  if (stats.isDirectory()) {
    if (!existsSync(dest)) mkdirSync(dest, { recursive: true })
    for (const f of readdirSync(src)) copyRecursive(join(src, f), join(dest, f))
  } else copyFileSync(src, dest)
}

if (existsSync(targetDir)) rmSync(targetDir, { recursive: true, force: true })
copyRecursive(sourceDir, targetDir)
console.log('✅ Admin copiado para pocketbase/pb_public/admin/')
```

### Hook no PB

Edite `pocketbase/pb_hooks/main.pb.js` (ou crie `pb_hooks/admin.pb.js`):

```js
// adicionar ao pb_hooks/main.pb.js
routerAdd("GET", "/admin/{path...}", $apis.static("pb_public/admin", true))
```

### Scripts raiz

```json
{
  "scripts": {
    "build:admin": "cd apps/admin && npm run build",
    "copy:admin": "node scripts/copy-admin.js",
    "build": "npm run build:landing && npm run copy:landing && npm run build:web && npm run copy:app && npm run build:admin && npm run copy:admin"
  }
}
```

### Dockerfile

```dockerfile
# adicionar stage entre web-builder e final
FROM node:20-alpine AS admin-builder
WORKDIR /app
COPY package*.json ./
COPY apps/admin/package*.json ./apps/admin/
RUN npm install --workspaces=false || npm install
COPY apps/admin ./apps/admin
RUN cd apps/admin && npm install && npm run build

# stage final (alpine/pocketbase)
RUN mkdir -p pb_public/admin
COPY --from=admin-builder /app/apps/admin/dist ./pb_public/admin
```

> Atualizar também o `pb_hooks` no COPY do stage final.

## Variável de ambiente

`apps/admin/.env.development`:

```bash
VITE_POCKETBASE_URL=http://localhost:8090
```

Em produção: `VITE_POCKETBASE_URL=/` (relativo — o PB serve os arquivos e a API).

## Atualizar `.dockerignore`

Já ignora `apps/*/dist`, mas para builds incrementais:

```
# garantir que build novo é refeito, mas cache dependências:
apps/admin/package*.json  # não precisa copiar código, COPY no stage cuida
```

## Checklist final

- [ ] `apps/<nome>/` com `package.json`, `vite.config.ts`, `index.html`, `tsconfig.json`
- [ ] Caminho base único (`base: '/<nome>/'` no Vite)
- [ ] Porta única em dev (5175, 5176…)
- [ ] `.env.development` + `.env.example`
- [ ] `dev:<nome>` e adicionado em `dev` no root
- [ ] `build:<nome>` + `copy:<nome>` no root
- [ ] Hook PB pra servir o path com `indexFallback=true`
- [ ] Stage do Dockerfile adicionado
- [ ] Rodar `npm install` no root pra puxar as deps do workspace
