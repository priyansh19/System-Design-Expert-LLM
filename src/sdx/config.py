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
    "ornith": "http://localhost:11434/v1",  # local, same Ollama daemon as "ollama"
    "finetune": "http://localhost:11434/v1",  # our own model once `ollama create`-d post-training
    # NVIDIA API Catalog (build.nvidia.com) trial keys are JUDGE-ONLY here, never teacher/base:
    # the trial ToS grants "limited trial ... internal testing and evaluation purposes, not
    # production" and bars redistributing Generated Content beyond that (Sections 1.2/1.4/4.2).
    # Training the shipped fine-tune on it would reopen the exact ToS risk already fixed by
    # dropping the Claude CLI teacher. Scoring our own answers for a local report never trains
    # or redistributes anything, so it fits the trial grant cleanly.
    "nvidia": "https://integrate.api.nvidia.com/v1",
    # Groq: TEACHER-safe (unlike nvidia/openai-consumer-tiers) -- read Groq's actual Services
    # Agreement Sec 4.2/8.1: customer owns Inputs/Outputs, Groq itself may not train on them,
    # and the only customer-side non-compete (Sec 6.3e) bars building a rival inference
    # *platform*, not downstream fine-tuning. Free tier: no card, 30 RPM/6K TPM/1K RPD.
    "groq": "https://api.groq.com/openai/v1",
    # Cerebras: TEACHER-safe -- ToS explicitly states inputs/outputs are governed by the
    # Third-Party Model Terms and "does not grant Cerebras the right to use Service Content
    # for the purpose of training or fine-tuning models"; independently verified no retention.
    # Free tier: no card, 1M TPD / model (gpt-oss-120b, zai-glm-4.7, gemma-4-31b), 5 RPM,
    # 30K TPM, token-bucket refill (smooth, not a hard daily reset). Run alongside Groq as a
    # second teacher stream, not a replacement -- doubles effective daily generation budget.
    "cerebras": "https://api.cerebras.ai/v1",
    # mesh-llm (github.com/Mesh-LLM/mesh-llm): local/private-mesh OpenAI-compatible endpoint
    # pooling this laptop + the mac mini. TEACHER-safe for the same reason as ornith -- the
    # served weights are Apache-2.0 Qwen GGUFs running on our own hardware, no vendor ToS on
    # outputs. Separate provider name (NOT "ollama"/"ornith") on purpose: llm.py routes those
    # to Ollama's *native* /api/chat for think:false, which mesh-llm does not implement --
    # mesh speaks OpenAI-compat only, so thinking is suppressed via Qwen3's /no_think soft
    # switch + <think> stripping in the mesh branch of Teacher.chat instead.
    "mesh": "http://localhost:9337/v1",
    # Same mesh endpoint, second logical provider so BASE_PROVIDER can pin the deliberately
    # weak DPO-'rejected' model while TEACHER_PROVIDER=mesh serves the big one concurrently.
    "meshsmall": "http://localhost:9337/v1",
}
_DEFAULT_MODEL = {
    "deepseek": "deepseek-chat",
    "xai": "grok-4-fast",
    "openai": "gpt-4o",
    "ollama": "qwen2.5:0.5b",  # fast+weak: only needs to be worse for DPO 'rejected' answers
    "ornith": "ornith-nothink:9b",  # local teacher; staff-architect persona baked into the Modelfile
    "finetune": "system-design-expert",  # tag used by deploy/ once the merged GGUF is `ollama create`-d
    # Llama family, not Qwen -- keeps judge family != ornith's Qwen3 base per the bias control.
    "nvidia": "meta/llama-3.3-70b-instruct",
    # Qwen3-32B, Apache-2.0 (no Llama-license naming/attribution encumbrance on the shipped
    # model), same architecture family as ornith but far bigger/faster (~400 tok/s on Groq's
    # LPUs vs ~8 tok/s local CPU). Supports response_format=json_object (chat_json path).
    "groq": "qwen/qwen3-32b",
    # gemma-4-31b: Google Gemma 4, 31B, ~1850 tok/s on Cerebras hardware. Supports
    # response_format=json_object. NOTE (accepted tradeoff, not the Apache-2.0-clean default):
    # Gemma's Terms of Use define any model trained via distillation on Gemma outputs as a
    # "Model Derivative" bound by Gemma's Terms/Prohibited Use Policy -- unlike gpt-oss-120b
    # (Apache 2.0, zero downstream encumbrance) or groq's qwen3-32b above, the model shipped
    # from this stream's data inherits that obligation. Chosen deliberately anyway; see
    # docs/superpowers/specs/ risk log for the explicit call.
    "cerebras": "gemma-4-31b",
    # Model ids as exposed by mesh-llm's /v1/models for the catalog GGUFs we downloaded.
    "mesh": "Qwen3-8B-Q4_K_M",
    "meshsmall": "Qwen2.5-0.5B-Instruct-Q4_K_M",
}
# Providers that need no real API key (local / Ollama-served / mesh-served).
_NO_KEY = {"ollama", "ornith", "finetune", "mesh", "meshsmall"}


def provider_config(provider: str | None = None) -> ProviderConfig:
    """Resolve a provider's config from env. Defaults to TEACHER_PROVIDER."""
    provider = (provider or os.getenv("TEACHER_PROVIDER", "ornith")).lower()
    prefix = provider.upper()
    api_key = "ollama" if provider in _NO_KEY else _require(f"{prefix}_API_KEY")
    base_url = os.getenv(f"{prefix}_BASE_URL", "").strip() or _DEFAULT_BASE_URL.get(provider, "")
    model = os.getenv(f"{prefix}_MODEL", "").strip() or _DEFAULT_MODEL.get(provider, "")
    if not base_url or not model:
        raise RuntimeError(f"Unknown provider '{provider}'; set {prefix}_BASE_URL and {prefix}_MODEL.")
    return ProviderConfig(name=provider, api_key=api_key, base_url=base_url, model=model)


def teacher_config() -> ProviderConfig:
    return provider_config(os.getenv("TEACHER_PROVIDER", "ornith"))


def judge_config() -> ProviderConfig:
    return provider_config(os.getenv("JUDGE_PROVIDER", "openai"))


def base_config() -> ProviderConfig:
    """The 'base'/weaker model used to produce DPO 'rejected' answers (default local Ollama)."""
    return provider_config(os.getenv("BASE_PROVIDER", "ollama"))


def gen_concurrency() -> int:
    return int(os.getenv("GEN_CONCURRENCY", "6"))


def gen_temperature() -> float:
    return float(os.getenv("GEN_TEMPERATURE", "0.7"))
