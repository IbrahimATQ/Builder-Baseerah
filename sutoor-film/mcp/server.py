#!/usr/bin/env python3
"""ARABIC POETRY FILM PRODUCTION MCP — one connector for the whole pipeline.

Tool logic lives in tools.py (also published through Gradio by ../space/app.py). This file
registers those functions with the official MCP Python SDK and runs a transport.

Security model (implemented in tools.py)
  * No arbitrary shell or ffmpeg filter strings: every tool builds argument lists itself.
  * Asset names are validated and resolved inside WORKSPACE (no traversal, no symlinks).
  * ffmpeg/ffprobe read inputs with -protocol_whitelist file,pipe (no fetches from crafted media).
  * Footage downloads only from allowlisted licensed-media CDNs; imports only over HTTPS to
    public IPs (SSRF guard) with a size cap. No media is sent to third-party AI services.
  * Long tools run as background jobs (start_job / job_status) to respect connector time limits.

Run:  python server.py            streamable HTTP on $HOST:$PORT$MCP_PATH (default 0.0.0.0:7860/mcp)
      python server.py --stdio    stdio, for Claude Code via the repo's .mcp.json
"""
from __future__ import annotations

import functools
import os
import sys

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as MCPToolError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tools  # noqa: E402

server = MCPServer(
    name="arabic-poetry-film-production",
    title="ARABIC POETRY FILM PRODUCTION MCP",
    version="1.1.0",
    instructions=(
        "Produce cinematic films from Arabic poetry recitations. Typical order: import_media -> "
        "inspect_media -> extract_audio -> separate_voice -> transcribe_arabic -> sync_subtitles -> "
        "search_footage -> download_licensed_media -> edit_video -> mix_audio -> create_composition -> "
        "render_film -> inspect_output. Run long steps through start_job and poll job_status. "
        "Subtitle only what is recited; never gate pauses."
    ),
)


def _expose(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except tools.ToolError as e:
            raise MCPToolError(str(e)) from e

    return wrapper


for _fn in tools.TOOLS:
    server.tool()(_expose(_fn))

if __name__ == "__main__" and "--stdio" in sys.argv:
    server.run("stdio")
elif __name__ == "__main__":
    server.run(
        "streamable-http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 7860)),
        streamable_http_path=os.environ.get("MCP_PATH", "/mcp"),
    )
