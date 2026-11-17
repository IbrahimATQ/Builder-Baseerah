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


def ensure_node22() -> None:
    """Gradio Spaces run Debian (Node 18); Remotion's bundler needs Node >= 22.12. Fetch the latest
    official Node 22 build, verify it against nodejs.org's SHASUMS256.txt, and install the Remotion
    project's dependencies. Runs once in the background so the MCP endpoint is available at once."""
    import hashlib
    import subprocess
    import tarfile
    import threading
    import urllib.request

    def work() -> None:
        home = os.path.expanduser("~/.node22")
        bin_dir = os.path.join(home, "bin")
        if not os.path.exists(os.path.join(bin_dir, "node")):
            base = "https://nodejs.org/dist/latest-v22.x/"
            sums = urllib.request.urlopen(base + "SHASUMS256.txt", timeout=60).read().decode()
            line = next(l for l in sums.splitlines() if l.endswith("-linux-x64.tar.xz"))
            digest, name = line.split()
            blob = urllib.request.urlopen(base + name, timeout=300).read()
            if hashlib.sha256(blob).hexdigest() != digest:
                raise RuntimeError("Node download failed checksum verification")
            tmp = os.path.join("/tmp", name)
            open(tmp, "wb").write(blob)
            with tarfile.open(tmp) as tf:
                tf.extractall("/tmp/node22", filter="data")
            os.rename(os.path.join("/tmp/node22", name[: -len(".tar.xz")]), home)
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]
        os.environ.setdefault("REMOTION_BROWSER", "/usr/bin/chromium")
        remotion = os.path.join(ROOT, "remotion")
        if not os.path.isdir(os.path.join(remotion, "node_modules")):
            subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=remotion, check=True)

    threading.Thread(target=work, daemon=True).start()


if os.environ.get("SPACE_ID"):  # only on Hugging Face Spaces
    ensure_node22()


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
