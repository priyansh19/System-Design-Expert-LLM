"""Build DPO preference pairs.

chosen   = the filtered teacher answer (from sft.jsonl)
rejected = the base/weaker model's answer to the same prompt (default: local Ollama)

Usage:
    python scripts/build_dpo.py --in data/generated/sft.jsonl \
        --out data/generated/dpo.jsonl --n 1200
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import asyncio
from pathlib import Path

from sdx.config import GENERATED_DIR, base_config, gen_concurrency
from sdx.corpus import read_jsonl, write_jsonl
from sdx.llm import Teacher, make_teacher, map_bounded
from sdx.schema import ANSWER_SECTIONS, DPORecord, SFTRecord

_SECTIONS_BLOCK = "\n".join(f"## {s}" for s in ANSWER_SECTIONS)

# Hard negative, not an easy one: the rejected answer must use the SAME header
# structure and a similar length target as the teacher (chosen) answer, so DPO can't
# win the preference just by learning "produce headers / write more words". The
# degradation is confined to reasoning depth and grounding: a junior-engineer persona,
# no retrieved corpus/paper context, explicitly told to stay surface-level.
BASE_SYSTEM = (
    "You are a competent but junior backend engineer, not a distributed-systems "
    "specialist. Answer the request with reasonable effort but keep your reasoning "
    "surface-level: prefer generic advice over deep tradeoff analysis, and don't dig "
    "into failure modes, capacity numbers, or alternative technology choices unless the "
    "question forces it."
)

_HARD_PROMPT_TMPL = """Answer the following architecture request.

# Request
{prompt}

# Required answer format
Use ALL of these level-2 (##) section headers, verbatim, in this exact order. Do not skip \
any section, do not add others, do not change the heading level:
{sections}

Write a focused answer (500-1000 words)."""


async def _rejected(base: Teacher, rec: SFTRecord) -> DPORecord:
    msgs = [
        {"role": "system", "content": BASE_SYSTEM},
        {
            "role": "user",
            "content": _HARD_PROMPT_TMPL.format(prompt=rec.instruction, sections=_SECTIONS_BLOCK),
        },
    ]
    rejected = await base.chat(msgs, temperature=0.7, max_tokens=1500)
    return DPORecord(id=rec.id, prompt=rec.instruction, chosen=rec.output, rejected=rejected.strip())


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(GENERATED_DIR / "sft.jsonl"))
    ap.add_argument("--out", default=str(GENERATED_DIR / "dpo.jsonl"))
    ap.add_argument("--n", type=int, default=1200, help="max pairs to build")
    args = ap.parse_args()

    records = [SFTRecord(**row) for row in read_jsonl(Path(args.inp))][: args.n]
    base = make_teacher(base_config())

    async def worker(rec: SFTRecord) -> DPORecord:
        return await _rejected(base, rec)

    results = await map_bounded(records, worker, concurrency=gen_concurrency())
    pairs = [r for r in results if r is not None and r.chosen.strip() != r.rejected.strip()]
    n = write_jsonl(Path(args.out), pairs)
    print(f"Wrote {n} DPO pairs -> {args.out} (from {len(records)} SFT records)")


if __name__ == "__main__":
    asyncio.run(main())
