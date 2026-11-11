# Etapa 1: compila a página React.
FROM node:24.22.2-alpine3.24 AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# Grava em /app/src/nl_calculator/static (outDir do vite.config.ts).
RUN npm run build

# Etapa 2: roda a API, que também serve a página. Sem Node.
FROM python:3.14.10-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Sem .python-version: o uv usa o Python 3.14 da imagem em vez de tentar baixar a 3.14.8.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src/ src/
COPY --from=web /app/src/nl_calculator/static src/nl_calculator/static
RUN uv sync --locked --no-dev --no-editable

USER nobody
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]
CMD ["/app/.venv/bin/uvicorn", "nl_calculator.api:app", "--host", "0.0.0.0", "--port", "8000"]
