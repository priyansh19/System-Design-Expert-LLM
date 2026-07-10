"""Generate structured, corpus-grounded answers for each scenario -> SFT candidates.

Usage:
    python scripts/gen_answers.py --in data/generated/scenarios.jsonl \
        --out data/generated/sft_raw.jsonl
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import asyncio
from pathlib import Path

from sdx.config import GENERATED_DIR, gen_concurrency, gen_temperature, teacher_config
from sdx.corpus import (
    load_corpus,
    load_grounding,
    notes_by_slugs,
    read_jsonl,
    retrieve_grounding,
    write_jsonl,
)
from sdx.llm import Teacher, map_bounded
from sdx.schema import ANSWER_SECTIONS, Scenario, SFTRecord

SYSTEM = (
    "You are a distinguished (staff+) software architect. You give concrete, opinionated, "
    "production-grade system design guidance. You make explicit technology recommendations "
    "and always weigh tradeoffs like a senior engineer in a design review."
)

SECTIONS_BLOCK = "\n".join(f"## {s}" for s in ANSWER_SECTIONS)

PROMPT_TMPL = """Answer the following architecture request as a staff engineer would in a \
design doc. Ground your reasoning in the reference notes provided; prefer their vocabulary \
and tradeoffs, but adapt to the specific requirement. Be concrete: name technologies, give \
rough capacity numbers, call out failure modes.

# Request
{prompt}

# Reference notes (authoritative background)
{refs}

# Required answer format
Use ALL of these level-2 (##) section headers, verbatim, in this exact order. Do not skip \
any section, do not add others, do not change the heading level:
{sections}

Write a thorough but focused answer (600-1100 words). No preamble, start at the first header."""


def _refs_for(scn: Scenario, notes, grounding: list[dict]) -> str:
    picked = notes_by_slugs(notes, scn.topics)
    if not picked:  # fall back to a small default set if topics didn't match
        picked = notes[:4]
    parts = [f"[curated:{n.slug}] {n.title}\n{n.text}" for n in picked]
    # Real authoritative excerpts from the GitHub grounding pool, retrieved by relevance.
    for g in retrieve_grounding(scn.prompt + " " + " ".join(scn.topics), grounding, k=3):
        parts.append(f"[source:{g['source']}] {g['heading']}\n{g['text']}")
    return "\n\n---\n\n".join(parts)


async def _one(teacher: Teacher, scn: Scenario, notes, grounding: list[dict], temp: float) -> SFTRecord:
    msgs = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": PROMPT_TMPL.format(
                prompt=scn.prompt, refs=_refs_for(scn, notes, grounding), sections=SECTIONS_BLOCK
            ),
        },
    ]
    answer = await teacher.chat(msgs, temperature=temp, max_tokens=3000)
    return SFTRecord(
        id=scn.id,
        instruction=scn.prompt,
        output=answer.strip(),
        domain=scn.domain,
        scale=scn.scale,
        topics=scn.topics,
    )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(GENERATED_DIR / "scenarios.jsonl"))
    ap.add_argument("--out", default=str(GENERATED_DIR / "sft_raw.jsonl"))
    args = ap.parse_args()

    notes = load_corpus()
    grounding = load_grounding()
    scenarios = [Scenario(**row) for row in read_jsonl(Path(args.inp))]
    teacher = Teacher(teacher_config())
    temp = gen_temperature()

    async def worker(scn: Scenario) -> SFTRecord:
        return await _one(teacher, scn, notes, grounding, temp)

    results = await map_bounded(scenarios, worker, concurrency=gen_concurrency())
    records = [r for r in results if r is not None]
    n = write_jsonl(Path(args.out), records)
    print(f"Wrote {n}/{len(scenarios)} answers -> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
