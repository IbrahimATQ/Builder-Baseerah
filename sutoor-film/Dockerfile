# ARABIC POETRY FILM PRODUCTION MCP — container for Hugging Face Spaces (Docker SDK, free CPU basic)
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg chromium ca-certificates git fonts-dejavu-core build-essential \
    && rm -rf /var/lib/apt/lists/*

# Remotion's bundler (Rspack) needs Node >= 22.12; Debian bookworm ships 18.x, so copy the official build.
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && node --version

RUN useradd -m -u 1000 user
WORKDIR /app

COPY --chown=user mcp/requirements.txt mcp/requirements.txt
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r mcp/requirements.txt

COPY --chown=user remotion/package.json remotion/package-lock.json remotion/
RUN cd remotion && npm ci --no-audit --no-fund

COPY --chown=user . .

ENV HOME=/home/user \
    HF_HUB_DISABLE_XET=1 \
    REMOTION_BROWSER=/usr/bin/chromium \
    MCP_WORKSPACE=/tmp/workspace \
    PORT=7860 HOST=0.0.0.0 MCP_PATH=/mcp
USER user
EXPOSE 7860
CMD ["python", "mcp/server.py"]
