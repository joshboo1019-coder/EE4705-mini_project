"""
vlm.py — STUDENT B OWNS THIS FILE. Bonus: scene description / visual QA.

ask(frame, question) sends one front-camera frame plus the user's question to
the vision-language model config.VLM_SERVICE, through the same
OpenAI-compatible clients as llm_parser, and returns a short answer that is
based only on the image.
"""

import base64
import io
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from core import config
from dialogue import llm_parser

# service name -> (provider, model id, extra request params). Chosen by
# comparing all of these on the same sim frames (eval/task3_eval.md, "Prompt v4 / look").
VLM_SERVICES = {
    "qwen3-vl-flash": ("qwen", "qwen3-vl-flash", {"temperature": 0}),
    "qwen-vl-plus": ("qwen", "qwen-vl-plus", {"temperature": 0}),
    "gemini-3.8-flash": ("gemini", "gemini-3.8-flash", {"reasoning_effort": "none"}),
    "gpt-5-nano": ("openai", "gpt-5-nano", {"reasoning_effort": "minimal"}),
}

SYSTEM_PROMPT = (
    "You are the eyes of a small quadruped robot dog. The image is the current view from its "
    "front camera. Answer the user's question using ONLY what is visible in this image. Answer "
    "in one or two short sentences. Mention colours when relevant. If the image doesn't show "
    "enough to answer, say you can't tell. Never guess about things outside the image.")

FRAMES_DIR = Path(__file__).resolve().parent.parent / "eval" / "results" / "vlm"


@dataclass
class VLMAnswer:
    answer: str
    model: str
    latency_s: float
    tokens_in: int
    tokens_out: int


def _png_data_url(frame: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(np.asarray(frame, dtype=np.uint8)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def save_frame(frame: np.ndarray, frames_dir: Path = FRAMES_DIR) -> Path:
    frames_dir.mkdir(parents=True, exist_ok=True)
    path = frames_dir / f"{datetime.now():%Y%m%d-%H%M%S-%f}.png"
    Image.fromarray(np.asarray(frame, dtype=np.uint8)).save(path)
    return path


def ask(frame: np.ndarray, question: str, service: str = None, client=None) -> VLMAnswer:
    """One VLM call. Raises on API errors; the executor catches them."""
    service = service or config.VLM_SERVICE
    provider, model, extra = VLM_SERVICES[service]
    client = client or llm_parser._get_client(provider)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": question},
            {"type": "image_url", "image_url": {"url": _png_data_url(frame)}}]},
    ]
    t0 = time.time()
    resp = client.chat.completions.create(model=model, messages=messages, **extra)
    latency = time.time() - t0
    answer = (resp.choices[0].message.content or "").strip()
    if not answer:
        raise ValueError("empty VLM answer")
    usage = getattr(resp, "usage", None)
    return VLMAnswer(answer=answer, model=model, latency_s=latency,
                     tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
                     tokens_out=getattr(usage, "completion_tokens", 0) or 0)
