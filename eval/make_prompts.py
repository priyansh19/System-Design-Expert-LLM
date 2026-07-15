"""Build the held-out evaluation prompt set (must NOT overlap with training data).

Generates a (domain, scale) grid of scenarios with the exact same generator as
gen_scenarios.py, then drops anything that is a near-duplicate (embedding cosine
similarity) of an existing SFT training instruction -- so the set stays genuinely
held-out even if this is re-run after more data collection.

Usage:
    python eval/make_prompts.py --n 60 --out eval/prompts.jsonl
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import asyncio
from pathlib import Path

from gen_scenarios import DOMAINS, SCALES, _one
from quality_filter import _embed

from sdx.config import GENERATED_DIR, gen_concurrency, gen_temperature, teacher_config
from sdx.corpus import corpus_index, load_corpus, read_jsonl, write_jsonl
from sdx.llm import make_teacher, map_bounded
from sdx.schema import Scenario

# A held-out prompt must be more different than this from every training instruction.
# Slightly looser than quality_filter's 0.92 dedup threshold on purpose: we want it to
# also reject "close paraphrase, same architecture pattern" pairs, not just near-exact dupes.
_SIM_THRESHOLD = 0.90


def _training_instructions(sft_path: Path) -> list[str]:
    if not sft_path.exists():
        return []
    return [row["instruction"] for row in read_jsonl(sft_path)]


def _drop_trained_overlap(scenarios: list[Scenario], existing: list[str]) -> list[Scenario]:
    if not existing or not scenarios:
        return scenarios
    held_vecs = _embed([s.prompt for s in scenarios])
    train_vecs = _embed(existing)
    keep = [
        s
        for s, v in zip(scenarios, held_vecs)
        if max(float(v @ tv) for tv in train_vecs) < _SIM_THRESHOLD
    ]
    return keep


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="target held-out prompt count (spec: 50-80)")
    ap.add_argument("--out", default="eval/prompts.jsonl")
    ap.add_argument(
        "--sft", default=str(GENERATED_DIR / "sft.jsonl"), help="training set to hold out against"
    )
    args = ap.parse_args()

    notes = load_corpus()
    index = corpus_index(notes)
    teacher = make_teacher(teacher_config())
    temp = gen_temperature()

    # Oversample the grid so post-dedup we still land near --n.
    grid = [(d, s) for d in DOMAINS for s in SCALES]
    oversample = max(args.n, int(args.n * 1.3))
    work = [grid[i % len(grid)] for i in range(oversample)]

    async def worker(pair: tuple[str, str]) -> Scenario:
        return await _one(teacher, index, pair[0], pair[1], temp)

    results = await map_bounded(work, worker, concurrency=gen_concurrency())
    scenarios = [r for r in results if r is not None]

    existing = _training_instructions(Path(args.sft))
    survivors = _drop_trained_overlap(scenarios, existing)
    dropped = len(scenarios) - len(survivors)
    kept = survivors[: args.n]

    n = write_jsonl(Path(args.out), kept)
    print(
        f"Wrote {n}/{args.n} held-out prompts -> {args.out} "
        f"(generated {len(scenarios)}, dropped {dropped} as training-overlap, "
        f"checked against {len(existing)} SFT instructions)"
    )


if __name__ == "__main__":
    asyncio.run(main())
