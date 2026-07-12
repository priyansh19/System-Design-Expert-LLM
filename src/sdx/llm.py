"""Async, provider-agnostic chat client with retry + bounded concurrency.

Any OpenAI-compatible endpoint works (DeepSeek, xAI/Grok, OpenAI). Used as the
teacher for synthetic generation and as the judge for evaluation.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, TypeVar

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential

from sdx.config import ProviderConfig

T = TypeVar("T")
R = TypeVar("R")


class Teacher:
    """Thin wrapper over an OpenAI-compatible async client."""

    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
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
        kwargs: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await self.client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content
        if not content:
            raise ValueError("Empty completion from provider")
        return content

    async def chat_json(self, messages: list[dict[str, str]], **kw: Any) -> Any:
        raw = await self.chat(messages, json_mode=True, **kw)
        return json.loads(raw)


def _extract_json(raw: str) -> Any:
    """Parse JSON from CLI text output, tolerating markdown fences / prose."""
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


class CLITeacher:
    """Teacher backed by the local `claude` CLI (Claude Code print mode).

    Same async surface as Teacher. Auth/model come from the CLI's own login;
    temperature/max_tokens are not exposed by the CLI and are ignored.
    """

    def __init__(self, cfg: ProviderConfig, *, timeout: float = 300.0):
        self.cfg = cfg
        self.timeout = timeout
        self._exe = shutil.which("claude") or "claude"

    @staticmethod
    def _split(messages: list[dict[str, str]]) -> tuple[str, str]:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        user = "\n\n".join(m["content"] for m in messages if m["role"] != "system")
        return system, user

    @retry(wait=wait_random_exponential(min=2, max=60), stop=stop_after_attempt(4), reraise=True)
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        system, user = self._split(messages)
        args = [self._exe, "-p", "--output-format", "text"]
        if self.cfg.model and self.cfg.model != "cli":
            args += ["--model", self.cfg.model]
        if system:
            args += ["--system-prompt", system]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(user.encode("utf-8")), timeout=self.timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError(f"claude cli timed out after {self.timeout}s")
        if proc.returncode != 0:
            msg = err.decode("utf-8", "replace")[:300]
            raise RuntimeError(f"claude cli rc={proc.returncode}: {msg}")
        text = out.decode("utf-8", "replace").strip()
        if not text:
            raise ValueError("Empty completion from claude cli")
        return text

    async def chat_json(self, messages: list[dict[str, str]], **kw: Any) -> Any:
        raw = await self.chat(messages, json_mode=True, **kw)
        return _extract_json(raw)


def make_teacher(cfg: ProviderConfig) -> "Teacher | CLITeacher":
    """Return the right backend for a provider (CLI for `claude`, HTTP otherwise)."""
    if cfg.name == "claude":
        return CLITeacher(cfg)
    return Teacher(cfg)


async def map_bounded(
    items: Sequence[T],
    worker: Callable[[T], Awaitable[R]],
    *,
    concurrency: int,
    on_error: str = "skip",  # "skip" -> None in output; "raise" -> propagate
) -> list[R | None]:
    """Run `worker` over `items` with a bounded semaphore, preserving order."""
    sem = asyncio.Semaphore(concurrency)
    results: list[R | None] = [None] * len(items)

    async def run(idx: int, item: T) -> None:
        async with sem:
            try:
                results[idx] = await worker(item)
            except Exception:
                if on_error == "raise":
                    raise
                results[idx] = None

    await asyncio.gather(*(run(i, it) for i, it in enumerate(items)))
    return results
