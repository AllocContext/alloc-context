# Self-host evaluation stack. Built locally — not published to a registry.
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md glama.json server.json ./
COPY alloccontext ./alloccontext
COPY config ./config
COPY schemas ./schemas
COPY docker/config.yaml ./docker/config.yaml

RUN pip install --no-cache-dir -e ".[hosted]"

ENV ALLOC_CONTEXT_CONFIG=/app/docker/config.yaml \
    ALLOC_CONTEXT_DB=/data/alloccontext.db \
    ALLOC_CONTEXT_MCP_HOST=0.0.0.0 \
    ALLOC_CONTEXT_MCP_PORT=8000 \
    ALLOC_CONTEXT_SELF_HOST_HTTP=1

EXPOSE 8000
VOLUME /data

ENTRYPOINT ["alloc-context"]
CMD ["mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
