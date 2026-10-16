"""llama-server with a multimodal model, run by rpggen on a port of its own (T17.34).

The owner's Image Studio ships a llama.cpp build with vision support and Qwen3.5 9B; its vision
projector (an ``mmproj`` GGUF of the same model) is added by the owner, never downloaded here.
rpggen starts the server on ``port`` (8190 by default, so it never meets Image Studio's prompt
writer on 8189), asks through its OpenAI-style chat endpoint with the picture attached, and stops
it when done so the GPU is free again. Pictures never leave the machine: the server listens on
127.0.0.1 only.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

log = logging.getLogger(__name__)

READY_TIMEOUT_S = 360.0  # loading 9B on a busy GPU can take minutes
ASK_TIMEOUT_S = 300.0
COMFY_WAIT_S = 600.0  # how long to wait for ComfyUI to finish its queue before asking anyway
UPSCALE_TO = 512  # small pixel art is enlarged by whole steps to about this size


@dataclass(frozen=True)
class LlamaConfig:
    server: Path  # llama-server.exe
    model: Path  # the language model GGUF
    projector: Path  # its mmproj GGUF
    port: int = 8190
    comfy_url: str = "http://127.0.0.1:8188"  # the GPU's other user, waited for; "" not to

    def missing(self) -> list[str]:
        """What is not on disk (empty when the server can be started)."""
        return [str(p) for p in (self.server, self.model, self.projector) if not p.is_file()]


def picture_png(path: Path) -> bytes:
    """The picture as a PNG on white, small pixel art enlarged by whole steps (a 16 px sprite is
    a few pixels to a vision model otherwise)."""
    with Image.open(path) as opened:
        img = opened.convert("RGBA")
    scale = max(1, UPSCALE_TO // max(1, max(img.size)))
    if scale > 1:
        img = img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", img.size, (255, 255, 255, 255))
    canvas.alpha_composite(img)
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def _get_json(url: str, timeout: float) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def comfy_busy(comfy_url: str) -> bool:
    """True while ComfyUI runs or queues a job (it shares the GPU); False when it is idle or
    not running."""
    if not comfy_url:
        return False
    try:
        queue = _get_json(f"{comfy_url}/queue", 5)
    except (OSError, ValueError, urllib.error.URLError):
        return False
    return bool(queue.get("queue_running") or queue.get("queue_pending"))


class LlamaServer:
    """A running llama-server; use as a context manager. ``ask`` answers one picture."""

    def __init__(self, config: LlamaConfig, log_file: Path) -> None:
        self.config = config
        self.log_file = log_file
        self._proc: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> LlamaServer:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.config.port}"

    def start(self) -> None:
        missing = self.config.missing()
        if missing:
            raise FileNotFoundError("vision step: not found: " + ", ".join(missing))
        waited = 0.0
        while comfy_busy(self.config.comfy_url) and waited < COMFY_WAIT_S:
            time.sleep(5)
            waited += 5
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(self.config.server),
            "-m", str(self.config.model),
            "--mmproj", str(self.config.projector),
            "--host", "127.0.0.1",
            "--port", str(self.config.port),
            "-ngl", "99",
            "-c", "4096",
        ]  # fmt: skip
        with self.log_file.open("wb") as out:
            self._proc = subprocess.Popen(
                cmd, stdout=out, stderr=subprocess.STDOUT, cwd=str(self.config.server.parent)
            )
        deadline = time.monotonic() + READY_TIMEOUT_S
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError(f"vision step: llama-server exited ({self._proc.returncode})")
            try:
                if _get_json(f"{self.url}/health", 5).get("status") == "ok":
                    return
            except (OSError, ValueError, urllib.error.URLError):
                pass
            time.sleep(2)
        self.stop()
        raise TimeoutError("vision step: llama-server did not become ready")

    def stop(self) -> None:
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None

    def ask(self, png: bytes, question: str, max_tokens: int = 60) -> str:
        """The model's answer about one picture (thinking off, temperature 0)."""
        d = base64.b64encode(png).decode("ascii")
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{d}"}},
                        {"type": "text", "text": question},
                    ],
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        req = urllib.request.Request(
            f"{self.url}/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=ASK_TIMEOUT_S) as resp:
            message = json.loads(resp.read())["choices"][0]["message"]
        return str(message.get("content") or "").strip()
