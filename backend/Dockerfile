# =============================================================================
# Dockerfile para o Backend FastAPI + Telethon
# =============================================================================

FROM python:3.11-slim

LABEL maintainer="Edson <edson@ehtudo.app>"

WORKDIR /app

# -----------------------------------------------------------------------------
# Dependências do sistema (necessárias para telethon/cryptography)
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Instala dependências Python
# -----------------------------------------------------------------------------
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Copia código
# -----------------------------------------------------------------------------
COPY backend/ .

# Usuário não-root (segurança)
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

# -----------------------------------------------------------------------------
# Exposição e Health Check
# -----------------------------------------------------------------------------
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 1

# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
