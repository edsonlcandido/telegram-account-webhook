# PocketBase + Vue 3 + TypeScript + Tailwind CSS Template

Template completo para projetos com PocketBase + Vue 3 + TypeScript + Tailwind CSS em arquitetura monorepo.

## 🚀 Características

- **Monorepo** com workspaces (Landing Page + Web App)
- **PocketBase** como backend (autenticação, database, API RESTful)
- **Vue 3** com Composition API e TypeScript
- **Tailwind CSS v4** para estilização moderna
- **Vue Router** com guards de autenticação
- **Pinia** para gerenciamento de estado
- **Vite** como build tool com proxy configurado
- **Heroicons** para ícones
- **Dockerfile** multi-stage para produção
- **Scripts automatizados** para desenvolvimento e deploy

## 📁 Estrutura do Projeto

```
pocketbase-vue-tailwind-template/
├── apps/
│   ├── landing/              # Landing page estática
│   │   ├── src/
│   │   │   ├── main.ts
│   │   │   └── style.css
│   │   ├── public/
│   │   ├── index.html
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── tailwind.config.js
│   │   └── tsconfig.json
│   │
│   └── web/                  # Web app com Vue
│       ├── src/
│       │   ├── router/       # Vue Router
│       │   ├── stores/       # Pinia stores
│       │   ├── services/     # Serviços (PocketBase client)
│       │   ├── views/        # Páginas/Views
│       │   ├── App.vue
│       │   ├── main.ts
│       │   └── style.css
│       ├── public/
│       ├── index.html
│       ├── package.json
│       ├── vite.config.ts
│       ├── tailwind.config.js
│       └── tsconfig.json
│
├── pocketbase/
│   ├── pb_hooks/             # Hooks do PocketBase
│   │   └── main.pb.js        # SPA routing
│   ├── pb_migrations/        # Migrations do banco
│   ├── pb_data/              # Dados do PocketBase (gitignored)
│   └── pb_public/            # Arquivos públicos servidos
│
├── scripts/
│   ├── pocketbase.js         # Script para baixar/rodar PocketBase
│   ├── copy-landing.js       # Copia build da landing
│   └── copy-app.js           # Copia build do app
│
├── Dockerfile                # Build multi-stage
├── .dockerignore
├── .gitignore
├── package.json              # Root package (workspaces)
└── README.md
```

## 🛠️ Pré-requisitos

- **Node.js** >= 20.19.0
- **npm** >= 10.x

## 📦 Instalação

1. Clone o repositório:
```bash
git clone https://github.com/edsonlcandido/pocketbase-vue-tailwind-template.git
cd pocketbase-vue-tailwind-template
```

2. Instale as dependências:
```bash
npm install
```

Isso instalará as dependências do root e de todos os workspaces (landing e web).

## 🚀 Desenvolvimento

### Configuração de Ambiente

O projeto usa variáveis de ambiente para configurar URLs. Cada app (landing e web) tem seus próprios arquivos:

```
apps/
├── landing/
│   ├── .env.example       # Modelo commitado (URLs localhost)
│   ├── .env.production    # Config de produção (URLs relativas)
│   └── .env.local         # Suas configs pessoais (gitignored)
│
└── web/
    ├── .env.example       # Modelo commitado (URLs localhost)
    ├── .env.production    # Config de produção (URLs relativas)
    └── .env.local         # Suas configs pessoais (gitignored)
```

| Arquivo | Uso | Git |
|---------|-----|-----|
| `.env.example`     | Modelo commitado com placeholders pra copiar | ✅ |
| `.env.production`  | Usado em `npm run build` (URLs relativas)     | ✅ |
| `.env.local`       | Sobrescreve tudo, pessoal, nunca vai pro git  | ❌ |

> 💡 **Convenção**: copie `.env.example` → `.env.local` e ajuste conforme o ambiente. O `.env.local` sempre vence sobre os outros arquivos.

#### Desenvolvimento Local (padrão)

Crie o `.env.local` em cada app com as URLs do localhost:

```bash
# apps/web/.env.local
cp apps/web/.env.example apps/web/.env.local
# Conteúdo (já vem pronto no .env.example):
#   VITE_POCKETBASE_URL=http://localhost:8090

# apps/landing/.env.local
cp apps/landing/.env.example apps/landing/.env.local
# Conteúdo (já vem pronto no .env.example):
#   VITE_POCKETBASE_URL=http://localhost:8090
#   VITE_WEBAPP_URL=http://localhost:5174
```

Depois é só rodar:

```bash
npm run dev
```

URLs locais:
- **PocketBase** → http://localhost:8090
- **Landing** → http://localhost:5173
- **Web App** → http://localhost:5174
- **PB Admin** → http://localhost:8090/_/

#### Desenvolvimento em Codespaces/GitPod

Para ambientes remotos, crie os arquivos `.env.local` em cada app:

```bash
# Landing Page
cat > apps/landing/.env.local << EOF
VITE_POCKETBASE_URL=https://sua-url-8090.app.github.dev/
VITE_WEBAPP_URL=https://sua-url-5174.app.github.dev/
EOF

# Web App
cat > apps/web/.env.local << EOF
VITE_POCKETBASE_URL=https://sua-url-8090.app.github.dev/
EOF
```

> ⚠️ Os arquivos `.env.local` são ignorados pelo git, então suas configurações locais não afetam outros desenvolvedores.

#### Desenvolvimento em VSCode Server (Easypanel / Tunnel / self-hosted)

Similar ao Codespaces, mas com o editor (`openvscode-server`, `code-server`) e os serviços rodando **no mesmo container/VM** atrás de um reverse proxy que expõe cada porta como subdomínio (Easypanel, Cloudflare Tunnel, Traefik, Caddy, Coolify). É o equivalente self-hosted do Codespaces — persistente, sem cobrança por hora, mas exige configurar 3 coisas manualmente.

**As 3 invariantes** (se qualquer uma falhar, o domínio externo retorna erro):

| # | O quê                          | Como garantir                                                                                  |
|---|--------------------------------|------------------------------------------------------------------------------------------------|
| 1 | Bind em `0.0.0.0` (não `127.0.0.1`) | `scripts/pocketbase.js` já passa `--http=0.0.0.0:8090`. Vite usa `vite.local.config.ts` (commitado) com `host: '0.0.0.0'` |
| 2 | `allowedHosts` no Vite         | `vite.local.config.ts` vem com `allowedHosts: true` (aceita qualquer host). Pra travar: `export VITE_ALLOWED_HOSTS="*.meudominio.com"` antes do `npm run dev` |
| 3 | URLs externas no `.env.local`  | Apontar pra `https://seu-dominio-8090.../` (com `/` no fim!) em `apps/web/.env.local` e `apps/landing/.env.local` |

**Setup no Easypanel** (exemplo concreto):

1. Suba um serviço `openvscode-server` (porta 8080) — anote o domínio gerado
2. Adicione 3 entradas no painel **apontando pro mesmo container**, cada uma em uma porta:

| Serviço        | Porta interna | Subdomínio gerado                              |
|----------------|---------------|------------------------------------------------|
| `openvscode`   | 8080          | `...-openvscode-node-8080.easypanel.host`      |
| `pocketbase`   | 8090          | `...-openvscode-node-8090.easypanel.host`      |
| `landing`      | 5173          | `...-openvscode-node-5173.easypanel.host`      |
| `web`          | 5174          | `...-openvscode-node-5174.easypanel.host`      |

3. No terminal do editor:
   ```bash
   cd /caminho/do/projeto
   npm install
   ```
4. Crie os `.env.local`:
   ```bash
   cat > apps/web/.env.local << EOF
   VITE_POCKETBASE_URL=https://...-openvscode-node-8090.nhiup2.easypanel.host/
   EOF

   cat > apps/landing/.env.local << EOF
   VITE_POCKETBASE_URL=https://...-openvscode-node-8090.nhiup2.easypanel.host/
   VITE_WEBAPP_URL=https://...-openvscode-node-5174.nhiup2.easypanel.host/
   EOF
   ```
5. Suba tudo:
   ```bash
   npm run dev
   ```
6. Acesse (em outra aba/janela):
   - Editor → `https://...-openvscode-node-8080.../`
   - Landing → `https://...-openvscode-node-5173.../`
   - Web → `https://...-openvscode-node-5174.../app/`
   - PB Admin → `https://...-openvscode-node-8090.../_/`

**Verificação rápida**:

```bash
# Deve mostrar 0.0.0.0 (NÃO 127.0.0.1):
ss -tln | grep -E "8090|5173|5174"

# Do seu navegador local (deve retornar 200):
curl -I https://...-openvscode-node-8090.../api/health
```

**Troubleshooting**:

| Sintoma                                              | Causa                                      | Fix                                                                       |
|------------------------------------------------------|--------------------------------------------|---------------------------------------------------------------------------|
| Domínio externo retorna `connection refused`         | PB/Vite bindado em `127.0.0.1`             | `ss -tln` deve mostrar `0.0.0.0`                                          |
| `Blocked request. This host (...) is not allowed.`  | Vite 5+ `allowedHosts` rejeitando         | Setar `VITE_ALLOWED_HOSTS` ou usar `vite.local.config.ts` (já é o default) |
| App carrega mas CTA/cliques dão 404                  | `.env.local` apontando pra `localhost`     | Conferir `VITE_POCKETBASE_URL` = URL externa com `/` no fim              |
| `502 Bad Gateway`                                    | Serviço interno caiu                       | `npm run dev` no terminal do editor                                      |
| `EADDRINUSE 8090`                                    | PB já estava rodando                       | `lsof -ti:8090 | xargs kill -9`                                          |

Mais detalhes, comparativo com Codespaces e dicas pra outras plataformas (Cloudflare Tunnel, ngrok, Coolify, Traefik) em `.opencode/skills/vscode-server-dev/SKILL.md`.

#### `VITE_ALLOWED_HOSTS` (variável custom do Vite)

`VITE_ALLOWED_HOSTS` **não é uma env do Vite** — é uma env custom definida em `apps/web/vite.local.config.ts` e `apps/landing/vite.local.config.ts`. Ela controla a opção `server.allowedHosts` do Vite, que (a partir do Vite 5) bloqueia requests com `Host:` header que não bate com `localhost` (proteção anti-DNS-rebinding).

```ts
// apps/web/vite.local.config.ts (resumo)
const allowedHosts: true | string[] = (() => {
  const raw = process.env.VITE_ALLOWED_HOSTS
  if (!raw) return true              // default: aceita qualquer host
  return raw.split(',').map(s => s.trim()).filter(Boolean)
})()

export default defineConfig((env) => ({
  ...baseConfig(env),
  server: { ...baseConfig(env).server, host: '0.0.0.0', allowedHosts },
}))
```

> ⚠️ Por que `process.env` e não `import.meta.env`? Porque o `vite.config.ts` é avaliado **antes** do Vite carregar `.env.local` — então `import.meta.env.VITE_*` ainda não existe nesse momento. `process.env` lê direto do Node, que já tem a env do shell.

**Como usar**:

```bash
# Default (já é o que `vite.local.config.ts` faz se você não setar nada):
# aceita qualquer Host — ideal pra Easypanel/Tunnel que mudam URL

# Travar por domínio (recomendado em prod):
export VITE_ALLOWED_HOSTS="*.meudominio.com,meudominio.com,localhost"
npm run dev

# Aceitar só 1 domínio específico:
export VITE_ALLOWED_HOSTS="app.exemplo.com"
```

Formato: CSV de hosts, com wildcard `*` opcional. Vazio cai no `true` (aceita tudo).

> 💡 Não precisa colocar no `.env.local` — `process.env` é populado pelo shell antes do Node iniciar. Use `export` ou prefixe o comando: `VITE_ALLOWED_HOSTS="*.x.com" npm run dev`.

### Modo Desenvolvimento Completo

Execute todos os serviços simultaneamente (PocketBase + Landing + Web App):

```bash
npm run dev
```

Isso iniciará:
- **PocketBase** em http://localhost:8090
- **Landing Page** em http://localhost:5173
- **Web App** em http://localhost:5174

### Modo Desenvolvimento Individual

Execute cada serviço separadamente:

```bash
# Apenas PocketBase
npm run dev:pb

# Apenas Landing Page
npm run dev:landing

# Apenas Web App
npm run dev:web
```

### Acessar a Aplicação

- **Landing Page**: http://localhost:5173
- **Web App**: http://localhost:5174
- **PocketBase Admin**: http://localhost:8090/_/

## 🏗️ Build para Produção

### Build Completo

```bash
npm run build
```

Isso fará:
1. Build da landing page
2. Copia a landing para `pocketbase/pb_public/`
3. Build do web app
4. Copia o web app para `pocketbase/pb_public/app/`

### Build Individual

```bash
# Build apenas da landing
npm run build:landing

# Build apenas do web app
npm run build:web

# Copiar landing para PocketBase
npm run copy:landing

# Copiar web app para PocketBase
npm run copy:app
```

### Preview da Produção

Após o build completo, você pode testar a aplicação em modo produção:

```bash
npm run preview
```

Acesse http://localhost:8090 para ver:
- **Landing Page**: http://localhost:8090/
- **Web App**: http://localhost:8090/app/
- **PocketBase Admin**: http://localhost:8090/_/

## 🐳 Docker

### Build da Imagem

```bash
docker build -t pocketbase-app .
```

### Executar o Container

```bash
docker run -p 8090:8090 -v $(pwd)/pb_data:/app/pb_data pocketbase-app
```

Acesse http://localhost:8090

### Docker Compose (Exemplo)

Crie um arquivo `docker-compose.yml`:

```yaml
version: '3.8'

services:
  pocketbase:
    build: .
    ports:
      - "8090:8090"
    volumes:
      - ./pb_data:/app/pb_data
    restart: unless-stopped
```

Execute:

```bash
docker-compose up -d
```

## 🔐 Autenticação

O template já vem configurado com:

- **Pinia Store** para gerenciamento de autenticação
- **Vue Router Guards** para proteção de rotas
- **PocketBase Client** configurado
- **Login/Register Views** com Tailwind CSS

### Criar Primeiro Usuário

1. Acesse http://localhost:8090/_/
2. Crie uma conta de administrador
3. Acesse "Collections" e crie uma collection "users" (se não existir)
4. Configure as permissões necessárias

Ou use o web app em http://localhost:5174/app/login

## 🎨 Tailwind CSS

O template usa **Tailwind CSS v4** em ambos os apps (landing e web).

### Configuração

Cada app tem sua própria configuração:
- `apps/landing/tailwind.config.js`
- `apps/web/tailwind.config.js`

### Importação

Em cada app, o Tailwind é importado no `style.css`:

```css
@import "tailwindcss";
```

## 🔄 Vue Router

O web app usa Vue Router com as seguintes rotas:

- `/` → Redireciona para `/dashboard`
- `/login` → Página de login/registro
- `/dashboard` → Dashboard (requer autenticação)

### Guards de Navegação

```typescript
// Rotas protegidas
meta: { requiresAuth: true }

// Rotas apenas para visitantes
meta: { requiresGuest: true }
```

## 📱 Pinia Stores

### Auth Store

Localizado em `apps/web/src/stores/auth.ts`:

```typescript
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// Propriedades
authStore.user          // Usuário atual
authStore.isLoggedIn    // Status de autenticação

// Métodos
await authStore.login(email, password)
await authStore.register(email, password, passwordConfirm)
authStore.logout()
```

## 🔌 PocketBase Client

O cliente está configurado em `apps/web/src/services/pocketbase.ts`:

```typescript
import pb from '@/services/pocketbase'

// Usar as APIs do PocketBase
const records = await pb.collection('posts').getList()
```

### Variáveis de Ambiente

- **Local** (`.env.local` — gitignored, sobrescreve tudo):
  ```
  VITE_POCKETBASE_URL=http://localhost:8090
  VITE_WEBAPP_URL=http://localhost:5174
  ```

- **Produção** (`.env.production` — usado no `npm run build`):
  ```
  VITE_POCKETBASE_URL=/
  VITE_WEBAPP_URL=/app
  ```

> 💡 Pra começar, copie o `.env.example` (commitado) pra `.env.local` e ajuste conforme seu ambiente (localhost, Codespaces, VSCode Server, etc).

## 📝 Scripts Disponíveis

### Root Level

```bash
npm run dev              # Executar tudo em dev
npm run dev:pb           # Apenas PocketBase
npm run dev:landing      # Apenas Landing
npm run dev:web          # Apenas Web App
npm run build            # Build completo
npm run build:landing    # Build da landing
npm run build:web        # Build do web app
npm run copy:landing     # Copiar landing para PocketBase
npm run copy:app         # Copiar app para PocketBase
npm run preview          # Preview em produção
```

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/NovaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona NovaFeature'`)
4. Push para a branch (`git push origin feature/NovaFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 🙏 Agradecimentos

- [PocketBase](https://pocketbase.io/) - Backend incrível
- [Vue.js](https://vuejs.org/) - Framework progressivo
- [Tailwind CSS](https://tailwindcss.com/) - Framework CSS utilitário
- [Vite](https://vitejs.dev/) - Build tool ultra-rápido
- [Heroicons](https://heroicons.com/) - Belos ícones SVG

## 📞 Suporte

Se você encontrar algum problema ou tiver sugestões, por favor:

1. Verifique as [Issues existentes](https://github.com/edsonlcandido/pocketbase-vue-tailwind-template/issues)
2. Crie uma nova issue se necessário

---

Feito com ❤️ usando PocketBase + Vue + Tailwind CSS
