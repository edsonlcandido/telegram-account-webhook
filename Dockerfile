# Estágio 1: Build da Landing Page
FROM node:20-alpine AS landing-builder

WORKDIR /app

# Copiar apenas arquivos de dependências primeiro (cache layer)
COPY package*.json ./
COPY apps/landing/package*.json ./apps/landing/

# Instalar dependências (usando npm install pois package-lock.json pode não existir)
RUN npm install --workspaces=false || npm install

# Copiar código fonte da landing
COPY apps/landing ./apps/landing

# Build da landing page
RUN cd apps/landing && npm install && npm run build

# Estágio 2: Build do Web App
FROM node:20-alpine AS web-builder

WORKDIR /app

# Copiar apenas arquivos de dependências primeiro (cache layer)
COPY package*.json ./
COPY apps/web/package*.json ./apps/web/

# Instalar dependências
RUN npm install --workspaces=false || npm install

# Copiar código fonte do web app
COPY apps/web ./apps/web

# Build do web app
RUN cd apps/web && npm install && npm run build

# Estágio 3: Imagem final com PocketBase
FROM alpine:latest

# Instalar dependências
RUN apk add --no-cache \
    ca-certificates \
    wget \
    unzip

# Criar diretório de trabalho
WORKDIR /app

# Baixar e instalar PocketBase
ARG POCKETBASE_VERSION=0.40.5
RUN wget https://github.com/pocketbase/pocketbase/releases/download/v${POCKETBASE_VERSION}/pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && unzip pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && rm pocketbase_${POCKETBASE_VERSION}_linux_amd64.zip \
    && chmod +x pocketbase

# Criar estrutura de diretórios do PocketBase
RUN mkdir -p pb_hooks pb_migrations pb_data pb_public/app

# Copiar hooks e configurações
COPY pocketbase/pb_hooks ./pb_hooks

# Copiar builds das aplicações
COPY --from=landing-builder /app/apps/landing/dist ./pb_public
COPY --from=web-builder /app/apps/web/dist ./pb_public/app

# Expor porta
EXPOSE 8090

# Volume para dados persistentes
VOLUME /app/pb_data

# Comando de execução
CMD ["./pocketbase", "serve", "--http=0.0.0.0:8090"]
