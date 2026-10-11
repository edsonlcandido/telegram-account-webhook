---
name: docker-pb-deploy
description: Build, run e deploy do template via Docker / docker-compose. Cobre o Dockerfile multi-stage (landing-builder → web-builder → alpine/pocketbase), `pb_data` como volume persistente, e fluxo de produção PocketBase servindo Vue buildado. Use quando o usuário quiser publicar a app, criar CI/CD, ou subir localmente em container.
---

# Docker — Build & Deploy

O template já vem com **Dockerfile multi-stage** + `docker-compose.yaml`. Resultado: 1 imagem única servindo Landing + Web App + PocketBase na porta 8090.

## Pipeline de build

```
landing-builder (node:20-alpine)
   └─ npm install + vite build → apps/landing/dist
   ↓
web-builder (node:20-alpine)
   └─ npm install + vue-tsc + vite build → apps/web/dist
   ↓
alpine:latest + pocketbase 0.36.2
   └─ copia dist pra pb_public/, hooks em pb_hooks/
   └─ CMD ["./pocketbase", "serve", "--http=0.0.0.0:8090"]
```

## Comando único (recomendado)

```bash
docker build -t stack:latest .

# build + subir:
docker compose up -d

# logs:
docker compose logs -f pocketbase

# parar:
docker compose down
```

Acessos:
- Admin PB → http://localhost:8090/_/
- Landing → http://localhost:8090/
- Web App → http://localhost:8090/app/

## O que o Dockerfile faz (passo a passo)

1. **Stage 1 `landing-builder`** — instala deps do root + landing, gera `apps/landing/dist`
2. **Stage 2 `web-builder`** — instala deps do root + web, gera `apps/web/dist`
3. **Stage 3 `pocketbase`** — imagem final `alpine:latest`:
   - Instala `ca-certificates wget unzip`
   - Baixa PocketBase **v0.36.2** (fixa via `ARG POCKETBASE_VERSION`)
   - Cria `pb_hooks pb_migrations pb_data pb_public/app`
   - Copia hooks (`pb_hooks/`) e builds (`pb_public/` + `pb_public/app/`)
   - Expõe **8090**
   - Volume `/app/pb_data` (persistência)

> ⚠️ `pb_data` **não** é embedded — vem de volume. Primeiro start precisa criar admin via `/_/`.

## Customizar versão do PocketBase

```bash
docker build --build-arg POCKETBASE_VERSION=0.40.0 -t stack:v0.40.0 .
```

Edite também `scripts/pocketbase.js` (constante `version`) para paridade em dev.

## docker-compose.yaml atual

```yaml
services:
  pocketbase:
    image: stack:latest
    container_name: pocketbase
    ports:
      - "8090:8090"
    volumes:
      - pb_data:/app/pb_data
    restart: unless-stopped

volumes:
  pb_data:
```

## Adicionar CI/CD no GitHub Actions

`.github/workflows/deploy.yml`:

```yaml
name: build-and-push
on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t ghcr.io/${{ github.repository }}:latest .
      - name: Push
        run: |
          echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
          docker push ghcr.io/${{ github.repository }}:latest
```

## Deploy com Caddy/Traefik (exemplo)

PocketBase em `:8090` já serve frontends via `pb_public/`. Pra HTTPS + domínio:

```caddyfile
# Caddyfile
app.exemplo.com {
  reverse_proxy localhost:8090
}
```

## Problemas comuns

| Sintoma | Causa | Fix |
|---|---|---|
| Build do `web` falha com erro de tipo | Tipos do PB não disponíveis | Rodar `npm run dev:pb` local antes pra `pb_data/types.d.ts` existir |
| PB não inicia (permission denied) | `pocketbase` sem permissão no Linux | Dockerfile já seta `chmod +x` — não remover |
| `pb_data` resetou após deploy | Compose sem volume | Verificar `volumes:` em `docker-compose.yaml` |
| Admin `/_/` abre mas collections sumiram | Volume apontando pra outro path | Conferir `volumes: - pb_data:/app/pb_data` |
| Landing 404 em `/` | Hook `main.pb.js` não incluído | Hook está em `pocketbase/pb_hooks/` — `pb_hooks/` é copiado no build |
| Web app rotas SPA não funcionam | Hook `indexFallback` desligado | Conferir `pocketbase/pb_hooks/main.pb.js`: `$apis.static("pb_public/app", true)` (o `true` é essencial) |

## Boas práticas

- Versionar imagem: `stack:v0.1.0` em vez de `latest` em produção
- Bindar `pb_migrations/` como volume adicional se quiser atualizar schema sem rebuild:

```yaml
volumes:
  - pb_data:/app/pb_data
  - ./pocketbase/pb_migrations:/app/pb_migrations:ro
```

- Backup: `docker run --rm -v stack_pb_data:/data -v $PWD:/backup alpine tar czf /backup/pb_data.tar.gz /data`
- Em prod, sempre `--http=0.0.0.0:8090` (já está no Dockerfile). Sem isso, só atende `localhost`.
- Healthcheck opcional:

```yaml
services:
  pocketbase:
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:8090/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

## Migração de dados entre ambientes

```bash
# export
docker compose exec pocketbase tar czf /tmp/dump.tar.gz pb_data
docker cp $(docker compose ps -q pocketbase):/tmp/dump.tar.gz .

# import (com stack parado)
docker compose down
docker run --rm -v stack_pb_data:/target -v $PWD:/src alpine tar xzf /src/dump.tar.gz -C /target
docker compose up -d
```
