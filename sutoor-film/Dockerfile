# ARABIC POETRY FILM PRODUCTION MCP — container for Hugging Face Spaces (Docker SDK, free CPU basic)
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg chromium nodejs npm ca-certificates git fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

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
