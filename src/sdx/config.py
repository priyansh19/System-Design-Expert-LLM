"""Environment + provider configuration.

Providers are OpenAI-compatible; each maps to a trio of env vars:
    <PROVIDER>_API_KEY, <PROVIDER>_BASE_URL, <PROVIDER>_MODEL

This mirrors the convention already used in the sibling Rag_Knowledge project.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)  # .env is the source of truth (wins over stale shell env vars)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
GENERATED_DIR = DATA_DIR / "generated"
SEED_CORPUS_DIR = DATA_DIR / "seed_corpus"


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str
    base_url: str
    model: str


def _require(var: str) -> str:
    val = os.getenv(var, "").strip()
    if not val or val.startswith(("sk-your", "xai-your")):
        raise RuntimeError(
            f"Missing/placeholder env var {var}. Copy .env.example to .env and fill it in."
        )
    return val


# base_url defaults per provider so only the API key is strictly required.
_DEFAULT_BASE_URL = {
    "deepseek": "https://api.deepseek.com",
    "xai": "https://api.x.ai/v1",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
    "claude": "cli",  # sentinel: claude CLI provider is not HTTP-based
}
_DEFAULT_MODEL = {
    "deepseek": "deepseek-chat",
    "xai": "grok-4-fast",
    "openai": "gpt-4o",
    "ollama": "qwen2.5:7b",
    "claude": "sonnet",  # CLI model alias; auth via the logged-in claude CLI
}
# Providers that need no real API key (local / CLI-authenticated).
_NO_KEY = {"ollama", "claude"}


def provider_config(provider: str | None = None) -> ProviderConfig:
    """Resolve a provider's config from env. Defaults to TEACHER_PROVIDER."""
    provider = (provider or os.getenv("TEACHER_PROVIDER", "deepseek")).lower()
    prefix = provider.upper()
    api_key = "ollama" if provider in _NO_KEY else _require(f"{prefix}_API_KEY")
    base_url = os.getenv(f"{prefix}_BASE_URL", "").strip() or _DEFAULT_BASE_URL.get(provider, "")
    model = os.getenv(f"{prefix}_MODEL", "").strip() or _DEFAULT_MODEL.get(provider, "")
    if not base_url or not model:
        raise RuntimeError(f"Unknown provider '{provider}'; set {prefix}_BASE_URL and {prefix}_MODEL.")
    return ProviderConfig(name=provider, api_key=api_key, base_url=base_url, model=model)


def teacher_config() -> ProviderConfig:
    return provider_config(os.getenv("TEACHER_PROVIDER", "deepseek"))


def judge_config() -> ProviderConfig:
    return provider_config(os.getenv("JUDGE_PROVIDER", "openai"))


def base_config() -> ProviderConfig:
    """The 'base'/weaker model used to produce DPO 'rejected' answers (default local Ollama)."""
    return provider_config(os.getenv("BASE_PROVIDER", "ollama"))


def gen_concurrency() -> int:
    return int(os.getenv("GEN_CONCURRENCY", "6"))


def gen_temperature() -> float:
    return float(os.getenv("GEN_TEMPERATURE", "0.7"))
