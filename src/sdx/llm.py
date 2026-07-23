"""Async, provider-agnostic chat client with retry + bounded concurrency.

Any OpenAI-compatible endpoint works (DeepSeek, xAI/Grok, OpenAI, local Ollama). Used as
the teacher for synthetic generation, the base for DPO negatives, and the judge for eval.
"""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, TypeVar

import httpx
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential

from sdx.config import ProviderConfig

T = TypeVar("T")
R = TypeVar("R")


def _extract_json(raw: str) -> Any:
    """Parse JSON, tolerating markdown fences (some local models wrap `format: json`
    output in ```json ... ``` regardless of the JSON-grammar constraint) or stray prose."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(raw[start : end + 1])


class Teacher:
    """Thin wrapper over an OpenAI-compatible async client.

    Local Ollama-served "thinking" models (Qwen3-arch, e.g. ornith-nothink:9b) ignore
    `think`/`extra_body` passed through the OpenAI-compat `/v1/chat/completions` route on
    Ollama 0.31.1 — verified empirically: the hidden reasoning trace still runs, burning
    the whole `max_tokens` budget and often returning empty `content`. Ollama's *native*
    `/api/chat` endpoint honors top-level `think: false` correctly and skips the reasoning
    trace entirely (~15x faster for short completions). So Ollama-family providers bypass
    the OpenAI SDK and hit `/api/chat` directly; every other provider is unaffected.
    """

    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self._is_ollama = "11434" in cfg.base_url or cfg.name in {"ollama", "ornith", "finetune"}
        # mesh-llm private-mesh endpoint: OpenAI-compatible llama.cpp under the hood. Qwen3
        # GGUFs served there emit a <think> preamble by default (same failure mode as Groq's
        # hosted Qwen3); no reasoning_format knob exists, so the mesh branch in chat() uses
        # Qwen3's documented /no_think soft switch plus response-side <think> stripping.
        self._is_mesh = cfg.name.startswith("mesh")
        if self._is_ollama:
            root = cfg.base_url.rsplit("/v1", 1)[0] or cfg.base_url
            # 900s, not 300s: a 3000-token answer at ~10 tok/s (slow CPU node) takes ~300s,
            # which sat exactly on the old timeout -- every long answer timed out and the
            # tenacity retries burned ~30min before giving up. Faster nodes are unaffected.
            self._http = httpx.AsyncClient(base_url=root, timeout=900.0)
        else:
            # Local mesh inference on CPU can be slow per request; the OpenAI SDK default
            # timeout (600s) is kept, but retries stay bounded by tenacity above.
            self.client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    @retry(wait=wait_random_exponential(min=2, max=60), stop=stop_after_attempt(6), reraise=True)
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        if self._is_ollama:
            return await self._chat_ollama_native(messages, temperature, max_tokens, json_mode)
        if self._is_mesh:
            # Qwen3 /no_think soft switch: appended to the system message (or injected as
            # one) it disables the thinking trace for the turn. Belt-and-braces: the
            # response is still <think>-stripped below because the soft switch leaves an
            # empty <think></think> pair on some llama.cpp template versions.
            messages = [dict(m) for m in messages]
            for m in messages:
                if m["role"] == "system":
                    m["content"] = m["content"].rstrip() + " /no_think"
                    break
            else:
                messages.insert(0, {"role": "system", "content": "/no_think"})
        kwargs: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            if self._is_mesh:
                # mesh-llm's skippy runtime 400s on response_format ("structured output ...
                # not yet implemented"). Prompt-driven JSON + _extract_json instead: nudge
                # the model and let the tolerant parser strip fences/prose.
                messages = [dict(m) for m in messages]
                messages[-1]["content"] += "\n\nReturn ONLY the JSON object. No markdown fences, no commentary."
                kwargs["messages"] = messages
            else:
                kwargs["response_format"] = {"type": "json_object"}
        if self.cfg.name == "groq":
            # Qwen3 (and other reasoning models) on Groq emit a <think>...</think> preamble
            # by default, which would pollute SFT/DPO training text and breaks Groq's own
            # JSON-mode validation (the raw completion must itself be valid JSON). "hidden"
            # strips reasoning from the response entirely, matching the "think": False the
            # local ollama path already forces. Reasoning tokens still count against
            # max_tokens even when hidden, so pad the budget -- otherwise a small
            # max_tokens (e.g. judge/scenario JSON calls) gets consumed entirely by
            # invisible thinking, leaving nothing (or a truncated answer) as content.
            kwargs["extra_body"] = {"reasoning_format": "hidden"}
            kwargs["max_tokens"] = max_tokens + 2000
        elif self.cfg.name == "cerebras" and self.cfg.model == "gpt-oss-120b":
            # gpt-oss-120b is a reasoning model; same failure mode as Groq's Qwen3 --
            # reasoning tokens count against max_tokens even though the default format
            # already separates them into their own field, so a small max_tokens budget
            # (e.g. scenario/judge JSON calls) can be fully consumed by reasoning before any
            # content is emitted, yielding an empty completion. "hidden" drops reasoning
            # entirely for defense in depth. reasoning_effort=medium (model default) is kept
            # deliberately, not turned down to "low" -- system-design tradeoff answers need
            # real reasoning depth, not fast/shallow completions; padding is sized up
            # accordingly since medium spends more reasoning tokens than low.
            kwargs["extra_body"] = {"reasoning_format": "hidden", "reasoning_effort": "medium"}
            kwargs["max_tokens"] = max_tokens + 4000
        elif self.cfg.name == "cerebras" and self.cfg.model == "gemma-4-31b":
            # Gemma 4 31B has reasoning DISABLED by default (unlike gpt-oss/GLM) and does NOT
            # support "hidden"/"raw"/"clear_thinking"/"preserve_thinking" reasoning_format
            # values -- passing one would error, so this branch omits reasoning_format
            # entirely and relies on the (parsed-style) default to keep reasoning out of the
            # content field. reasoning_effort=medium explicitly enables reasoning ("none" is
            # the default/disabled) for the same real-reasoning-depth reason as gpt-oss above.
            # Reasoning tokens still count against max_tokens once enabled, so pad the budget.
            kwargs["extra_body"] = {"reasoning_effort": "medium"}
            kwargs["max_tokens"] = max_tokens + 4000
        if self._is_mesh:
            # Reasoning tokens count against max_tokens if the soft switch is ignored;
            # pad like the Groq branch so content never comes back truncated/empty.
            kwargs["max_tokens"] = max_tokens + 2000
        resp = await self.client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content
        if self._is_mesh and content:
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        if not content:
            raise ValueError("Empty completion from provider")
        return content

    async def _chat_ollama_native(
        self, messages: list[dict[str, str]], temperature: float, max_tokens: int, json_mode: bool
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "think": False,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        resp = await self._http.post("/api/chat", json=payload)
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "")
        if not content:
            raise ValueError("Empty completion from provider")
        return content

    async def chat_json(self, messages: list[dict[str, str]], **kw: Any) -> Any:
        raw = await self.chat(messages, json_mode=True, **kw)
        return _extract_json(raw)


def make_teacher(cfg: ProviderConfig) -> Teacher:
    return Teacher(cfg)


async def map_bounded(
    items: Sequence[T],
    worker: Callable[[T], Awaitable[R]],
    *,
    concurrency: int,
    on_error: str = "skip",  # "skip" -> None in output; "raise" -> propagate
    label: str = "",
) -> list[R | None]:
    """Run `worker` over `items` with a bounded semaphore, preserving order.

    On "skip", failures are silent to the caller (None in the output list) but NOT
    silent to stdout: a one-line summary + first error is printed so a batch that goes
    entirely to zero (e.g. a rate-limit/quota wall) is diagnosable from the log alone
    instead of looking identical to "nothing matched the gates".
    """
    sem = asyncio.Semaphore(concurrency)
    results: list[R | None] = [None] * len(items)
    errors: list[str] = []

    async def run(idx: int, item: T) -> None:
        async with sem:
            try:
                results[idx] = await worker(item)
            except Exception as exc:
                if on_error == "raise":
                    raise
                results[idx] = None
                errors.append(f"{type(exc).__name__}: {exc}")

    await asyncio.gather(*(run(i, it) for i, it in enumerate(items)))
    if errors:
        tag = f" {label}" if label else ""
        print(f"[map_bounded{tag}] {len(errors)}/{len(items)} failed; first: {errors[0][:300]}")
    return results
