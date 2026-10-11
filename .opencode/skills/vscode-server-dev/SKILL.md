---
name: vscode-server-dev
description: Workflow completo pra desenvolver dentro de um VSCode Server (openvscode-server, code-server, GitHub Codespaces, GitPod) com editor + PocketBase + Vite no mesmo container/VM, expostos via reverse proxy (Easypanel, Traefik, Caddy, Cloudflare Tunnel, ngrok). Cobre bind em 0.0.0.0, allowedHosts do Vite, .env.local por app, mapeamento de portas e troubleshooting. Use quando o usuário quiser trabalhar no projeto a partir de um ambiente remoto/cloud self-hosted sem usar Docker pra dev.
---

# VSCode Server / Cloud Dev Environment

Workflow pra desenvolver dentro de um **VSCode Server** quando o editor (`openvscode-server`, `code-server`) e os serviços (PocketBase + 2 Vites) estão rodando todos no mesmo container/máquina, atrás de um reverse proxy que expõe portas como subdomínios (Easypanel, Cloudflare Tunnel, Coolify, Traefik, ngrok etc).

É o equivalente "self-hosted" do GitHub Codespaces/GitPod — um pouco mais trabalhoso de configurar, mas persistente, sem cobrança por hora, e com URLs estáveis.

## Arquitetura típica

```
┌─────────────────────────────────────────────────────────────┐
│ Container / VM remoto                                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ openvscode-server  (UI em 8080 → exposta)             │  │
│  │ PocketBase          (8090 → exposta)                  │  │
│  │ Vite landing        (5173 → exposta)                  │  │
│  │ Vite web            (5174 → exposta)                  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
            │
            ▼  (reverse proxy: Easypanel, Traefik, Caddy, Cloudflare Tunnel, ngrok)
┌─────────────────────────────────────────────────────────────┐
│ meudominio.com/                                              │
│   editor  → https://...-openvscode-node-8080.../             │
│   pb      → https://...-openvscode-node-8090.../             │
│   landing → https://...-openvscode-node-5173.../             │
│   web     → https://...-openvscode-node-5174.../             │
└─────────────────────────────────────────────────────────────┘
```

## Quando usar

- Você tem um VPS/container rodando `openvscode-server` (ou similar) e quer que o PB + Vite rodem **junto**, não em Docker separado
- Você quer que cada porta gere um subdomínio público (Easypanel faz isso automaticamente)
- Você prefere editar arquivos ao vivo com HMR do Vite, sem rebuild do container a cada mudança
- Codespaces ephemeral não serve (precisa persistir `.env.local`, `pb_data`, etc entre sessões)

## Pré-requisitos no ambiente remoto

- Node.js **>= 20.19.0** (`node -v`)
- npm **>= 10.x** (`npm -v`)
- `unzip` no PATH (`apt install unzip` em Debian/Ubuntu)
- 4 portas livres: `8080` (editor), `8090` (PB), `5173` (landing), `5174` (web)

## Setup (uma vez por clone)

```bash
git clone https://github.com/edsonlcandico/pocketbase-vue-tailwind-template.git
cd pocketbase-vue-tailwind-template
npm install
```

Não precisa criar `.env` nenhum manualmente nesta etapa. O template já vem configurado pra bindar em `0.0.0.0`.

## As 3 coisas que precisam estar certas

Esse fluxo é "mais trabalhoso" que Codespaces porque você tem que garantir manualmente 3 invariantes. Se qualquer uma falhar, o domínio externo retorna erro (refused / 403 / 404).

### 1. Bind em `0.0.0.0` (não `127.0.0.1`)

Todos os serviços precisam escutar em **todas** as interfaces, não só loopback. O template já entrega isso:

| Serviço      | Onde está configurado                              | Default |
|--------------|----------------------------------------------------|---------|
| PocketBase   | `scripts/pocketbase.js` passa `--http=0.0.0.0:8090` | ✅ |
| Vite landing | `apps/landing/vite.local.config.ts`                | ✅      |
| Vite web     | `apps/web/vite.local.config.ts`                    | ✅      |

Se você subir o PB **manualmente** (fora do `npm run dev`), precisa lembrar do flag:

```bash
./pocketbase serve --http=0.0.0.0:8090
```

> ⚠️ **Erro #1 mais comum**: PB rodando com `--http=localhost:8090` (ou sem flag — default histórico é `127.0.0.1`). Proxy externo bate e recebe `connection refused` em segundos, mesmo com DNS/url corretos.

Como verificar:

```bash
ss -tln | grep -E "8090|5173|5174"
# esperado:
#   0.0.0.0:8090
#   0.0.0.0:5173
#   0.0.0.0:5174
# NÃO pode aparecer 127.0.0.1 em nenhuma
```

### 2. `allowedHosts` no Vite (Vite 5+)

Vite 5+ **bloqueia** requests cujo `Host:` header não bate com `localhost` (anti-DNS-rebinding). Aí o navegador abre o domínio externo e recebe:

```
Blocked request. This host (...) is not allowed.
```

O template já tem `apps/{web,landing}/vite.local.config.ts` com `allowedHosts: true` (aceita qualquer host). Pra travar por domínio, defina a env no shell antes do `npm run dev`:

```bash
export VITE_ALLOWED_HOSTS="*.meudominio.com,meudominio.com,localhost"
npm run dev
```

Formato: lista CSV. Suporta wildcard `*`. Vazio cai no `true`.

### 3. URLs externas no `.env.local` por app

O Vite faz proxy dinâmico baseado em `VITE_POCKETBASE_URL`. Se essa env apontar pra `http://localhost:8090`, o navegador vai pedir `localhost:8090` (que não existe do lado de fora do container).

Cada app tem seu **próprio** `.env.local` (gitignored). Crie os 2 arquivos com as URLs públicas:

```bash
# apps/web/.env.local
cat > apps/web/.env.local << EOF
VITE_POCKETBASE_URL=https://ehtudo-openvscode-node-8090.nhiup2.easypanel.host/
EOF

# apps/landing/.env.local
cat > apps/landing/.env.local << EOF
VITE_POCKETBASE_URL=https://ehtudo-openvscode-node-8090.nhiup2.easypanel.host/
VITE_WEBAPP_URL=https://ehtudo-openvscode-node-5174.nhiup2.easypanel.host/
EOF
```

> ⚠️ A barra `/` no final importa. `Vite proxy` e `pb` montam paths concatenando — sem `/` você recebe 404 em metade das rotas.
>
> ⚠️ **NÃO** coloque URL externa em `.env.development` — esse é commitado e outros devs usam `localhost`.

## Subir tudo

```bash
npm run dev
```

Isso sobe PB + landing + web em paralelo via `concurrently`. Cada serviço usa o `vite.local.config.ts` (que seta `host: '0.0.0.0'` + `allowedHosts`).

### Verificar de fora do container

Do seu navegador local ou do curl da sua máquina:

```bash
# PB health
curl -I https://ehtudo-openvscode-node-8090.nhiup2.easypanel.host/api/health
# esperado: HTTP/2 200

# Landing HTML
curl -I https://ehtudo-openvscode-node-5173.nhiup2.easypanel.host/
# esperado: HTTP/2 200 + content-type text/html

# Web index
curl -I https://ehtudo-openvscode-node-5174.nhiup2.easypanel.host/app/
# esperado: HTTP/2 200
```

Se algum retorna `502/504/connection refused`, voltar pra seção "As 3 coisas que precisam estar certas".

## Mapeamento de portas no Easypanel (exemplo concreto)

Easypanel resolve isso com **múltiplos serviços apontando pro mesmo container**, cada um em uma porta diferente:

| Serviço Easypanel   | Container Port | Domínio gerado                                       |
|---------------------|----------------|------------------------------------------------------|
| `openvscode-server` | 8080           | `...-openvscode-node-8080.easypanel.host`            |
| `pocketbase`        | 8090           | `...-openvscode-node-8090.easypanel.host`            |
| `landing`           | 5173           | `...-openvscode-node-5173.easypanel.host`            |
| `web`               | 5174           | `...-openvscode-node-5174.easypanel.host`            |

Todos os 4 serviços no Easypanel usam **o mesmo container** — só varia a porta exposta e o domínio gerado.

Pra outras plataformas:

| Plataforma          | Como mapear                                            |
|---------------------|--------------------------------------------------------|
| **Cloudflare Tunnel**| 1 entrada `cloudflared` apontando `8080,8090,5173,5174` |
| **Traefik**         | 4 routers + 4 services no mesmo docker network          |
| **Caddy**           | 4 subdomínios com `reverse_proxy localhost:PORTA`      |
| **ngrok**           | 4 túneis simultâneos (`ngrok http 8090` × 4)           |
| **GitPod**          | similar ao Codespaces — auto-forward, mas com `.env.local` |
| **Coolify**         | mesma lógica do Easypanel (apps no mesmo recurso)      |

## Workflow diário

```bash
# 1. Acessar o editor
# https://...-openvscode-node-8080.../

# 2. No terminal integrado do editor:
npm run dev

# 3. Abrir as URLs externas (em outra aba/janela):
#    - Landing → https://...-5173.../
#    - Web     → https://...-5174.../app/
#    - PB admin → https://...-8090.../_/

# 4. Editar código — HMR do Vite recarrega automaticamente

# 5. Quando quiser parar:
# Ctrl+C no terminal do npm run dev
```

## Diferenças vs GitHub Codespaces

| Aspecto               | GitHub Codespaces               | openvscode-server + Easypanel       |
|-----------------------|---------------------------------|--------------------------------------|
| URL do editor         | gerada auto (`*.github.dev`)    | você define o subdomínio             |
| Port forwarding       | automático, com popup           | você mapeia cada porta no painel     |
| `allowedHosts`        | já vem OK                       | precisa configurar manualmente       |
| Persistência          | ephemeral por padrão (30d max) | container persistente, sem limite    |
| Custo                 | por hora de uso                 | depende do host (VPS, Easypanel...)  |
| `.env.local`          | recriar a cada start            | cria 1×, persiste                    |
| `pb_data`             | ephemeral                       | volume persistente                   |
| Setup inicial         | 1 click                         | ~15min mapeando portas + DNS         |
| HMR do Vite           | funciona                        | funciona (mesma config)              |
| Terminal integrado    | sim                             | sim                                  |

## Scripts npm úteis

A raiz já tem `npm run dev` (sobe os 3 juntos) e `npm run dev:{pb,landing,web}` (individual). Pra abrir o PB em modo **produção** (servindo os builds):

```bash
npm run build         # gera dist em pb_public/
npm run preview       # sobe PB servindo a build
```

Não confundir `npm run dev` (Vite dev server com HMR) com `npm run preview` (PB servindo build estático).

## Troubleshooting

| Sintoma                                                 | Causa                                          | Fix                                                                 |
|---------------------------------------------------------|------------------------------------------------|----------------------------------------------------------------------|
| Domínio externo retorna `connection refused` / timeout  | PB ou Vite bindado em `127.0.0.1`              | Confirmar `ss -tln` mostra `0.0.0.0`. PB: `--http=0.0.0.0:8090`     |
| `Blocked request. This host (...) is not allowed.`      | `allowedHosts` do Vite não inclui o domínio    | Setar `VITE_ALLOWED_HOSTS` ou usar `vite.local.config.ts`           |
| Web/landing carrega mas ações dão 404                  | `VITE_POCKETBASE_URL` errado no `.env.local`   | Conferir URL completa, com `https://` e `/` no fim                  |
| Landing abre mas CTA "Entrar" quebra                    | `VITE_WEBAPP_URL` da landing errado            | Conferir `apps/landing/.env.local` aponta pro domínio do web        |
| `502 Bad Gateway` no proxy                              | Serviço interno não está rodando               | `npm run dev` no terminal do VSCode Server                          |
| HMR não funciona (mudanças não refletem)                | Vite não tem `--host` ou porta errada          | Garantir `vite.local.config.ts` com `host: '0.0.0.0'`                |
| CORS error no browser                                   | PB atrás de proxy sem `Host` correto           | Já tratado: `--http=0.0.0.0` + Vite proxy com `changeOrigin: true`  |
| `EADDRINUSE 8090` ao subir                             | PB já rodando                                  | `lsof -ti:8090 | xargs kill -9`                                     |
| PB reinicia mas esquece admin/superuser                 | `pb_data` não está persistente                 | Garantir volume mapeado pro path `/app/pb_data` (Docker) ou direto (sem Docker) |
| `vite-env.d.ts` reclama que `VITE_*` não existe         | `.env.local` não foi criado                    | Criar arquivo seguindo passo 3 acima                                |

## Quando **NÃO** usar esse fluxo

- Você quer isolar dev/prod rigorosamente → use Docker (skill `docker-pb-deploy`)
- Você só precisa editar 1 arquivo e sair → use GitHub Codespaces
- Você não tem acesso root/admin pra mapear portas → use Codespaces/GitPod (que fazem port-forward automático)

## Resumo

Pra esse fluxo funcionar, garanta os 3 invariantes:

1. **Bind**: PB (`--http=0.0.0.0:8090`) + Vite (`host: '0.0.0.0'` em `vite.local.config.ts`)
2. **Hosts**: `allowedHosts: true` no Vite (ou `VITE_ALLOWED_HOSTS` filtrando)
3. **URLs externas**: `.env.local` em cada app apontando pro domínio público, com `/` no fim

Se um dos 3 falhar, a stack toda parece quebrada — mas é só um dos três. Faça o checklist antes de sair caçando bug no código.