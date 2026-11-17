"""Gradio front end for the ARABIC POETRY FILM PRODUCTION MCP.

Publishes the same tool functions as mcp/server.py, through Gradio's built-in MCP server
(Streamable HTTP at /gradio_api/mcp/). This is the form a FREE Hugging Face account can host:
free accounts may run up to 2 Gradio Spaces on ZeroGPU hardware, while Docker/CPU Spaces need PRO.

GPU-capable steps (voice separation, Whisper) are wrapped with @spaces.GPU so they borrow a
ZeroGPU slice per call (free daily quota is small: minutes, not hours). Everything else runs on
the Space's CPU. Long steps should be started with start_job and polled with job_status, because
claude.ai connectors stop waiting after about 240 s per tool call.
"""
from __future__ import annotations

import functools
import os
import sys

import gradio as gr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "mcp"))
import tools  # noqa: E402

try:  # present on Hugging Face Spaces; absent locally
    import spaces

    gpu = spaces.GPU(duration=120)
except ImportError:  # pragma: no cover - local / CPU-only
    def gpu(fn):
        return fn

GPU_TOOLS = {"separate_voice", "transcribe_arabic"}


def _expose(fn):
    target = gpu(fn) if fn.__name__ in GPU_TOOLS else fn

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return target(*args, **kwargs)
        except tools.ToolError as e:
            raise gr.Error(str(e)) from e

    return wrapper


with gr.Blocks(title="Arabic Poetry Film Production MCP") as demo:
    gr.Markdown(
        "# ARABIC POETRY FILM PRODUCTION MCP\n"
        "Add this Space's `/gradio_api/mcp/` URL as a custom connector in claude.ai. "
        "Media you import stays in this Space; nothing is sent to third-party AI services."
    )
    for _fn in tools.TOOLS:
        gr.api(_expose(_fn), api_name=_fn.__name__)

if __name__ == "__main__":
    demo.launch(mcp_server=True, server_name=os.environ.get("HOST", "0.0.0.0"), server_port=int(os.environ.get("PORT", 7860)))
