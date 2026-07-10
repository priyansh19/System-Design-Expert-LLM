"""Async, provider-agnostic chat client with retry + bounded concurrency.

Any OpenAI-compatible endpoint works (DeepSeek, xAI/Grok, OpenAI). Used as the
teacher for synthetic generation and as the judge for evaluation.
"""

from __future__ import annotations

import asyncio
import json
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
