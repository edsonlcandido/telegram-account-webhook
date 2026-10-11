# =============================================================================
# Build Multi-Stage
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - compila o frontend Vue
# -----------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Instala dependências do npm
COPY package*.json ./
RUN npm ci

# Copia código fonte
COPY apps/ ./apps/

# Build da landing page
RUN npm run build:landing --prefix apps/landing

# Build do web app
RUN npm run build:web --prefix apps/web

# -----------------------------------------------------------------------------
# Stage 2: Production - só PocketBase
# -----------------------------------------------------------------------------
FROM pocketbase/pocketbase:latest AS production

# Copia os arquivos estáticos gerados
COPY --from=builder /app/apps/landing/dist /pb_public
COPY --from=builder /app/apps/web/dist /pb_public/app

# Copia hooks do PocketBase
COPY pocketbase/pb_hooks /pb_hooks

# Porta
EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8090/api/health || exit 1

# Entrypoint padrão do PocketBase
ENTRYPOINT ["/pocketbase"]
CMD ["serve", "--http=0.0.0.0:8090"]
