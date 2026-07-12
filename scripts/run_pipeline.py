"""End-to-end dataset builder: loop N rounds accumulating SFT, then build DPO.

Each round:
  scenarios (teacher) -> answers (teacher, corpus+grounding) -> structure/length gates
  -> accumulate into the master pool (append; deduped globally at the end).

Resumable: re-running loads the existing master sft.jsonl and adds more rounds.

Usage:
    python scripts/run_pipeline.py --rounds 10 --per-round 20 --dpo 1200
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import asyncio
import uuid
from pathlib import Path

import gen_answers as ga
import gen_scenarios as gs
import quality_filter as qf
from build_dpo import _rejected

from sdx.config import GENERATED_DIR, base_config, gen_concurrency, gen_temperature, teacher_config
from sdx.corpus import (
    corpus_index,
    load_corpus,
    load_grounding,
    read_jsonl,
    write_jsonl,
)
from sdx.llm import make_teacher, map_bounded
from sdx.schema import DPORecord, SFTRecord


async def _gen_round(teacher, notes, grounding, index, temp, n, concurrency) -> list[SFTRecord]:
    grid = [(d, s) for d in gs.DOMAINS for s in gs.SCALES]
    work = [grid[i % len(grid)] for i in range(n)]

    async def scn_worker(pair):
        return await gs._one(teacher, index, pair[0], pair[1], temp)

    scn_res = await map_bounded(work, scn_worker, concurrency=concurrency)
    scenarios = [s for s in scn_res if s is not None]

    async def ans_worker(scn):
        return await ga._one(teacher, scn, notes, grounding, temp)

    ans_res = await map_bounded(scenarios, ans_worker, concurrency=concurrency)
    answers = [a for a in ans_res if a is not None]
    # structure + length gates (per-record; global dedup happens once at the end)
    return [r for r in answers if qf._passes_gates(r, 300, 1400)]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--per-round", type=int, default=20)
    ap.add_argument("--dpo", type=int, default=1200, help="max DPO pairs to build (0 to skip)")
    ap.add_argument("--sim-threshold", type=float, default=0.92)
    ap.add_argument("--sft-out", default=str(GENERATED_DIR / "sft.jsonl"))
    ap.add_argument("--dpo-out", default=str(GENERATED_DIR / "dpo.jsonl"))
    args = ap.parse_args()

    notes = load_corpus()
    grounding = load_grounding()
    index = corpus_index(notes)
    teacher = make_teacher(teacher_config())
    temp = gen_temperature()
    concurrency = gen_concurrency()
    print(f"teacher={teacher.cfg.name}:{teacher.cfg.model} notes={len(notes)} grounding={len(grounding)}")

    sft_path = Path(args.sft_out)
    # resume: start from any existing master pool
    pool: list[SFTRecord] = []
    seen_ids: set[str] = set()
    if sft_path.exists():
        for row in read_jsonl(sft_path):
            rec = SFTRecord(**row)
            pool.append(rec)
            seen_ids.add(rec.id)
        print(f"resuming from {len(pool)} existing SFT records")

    for r in range(1, args.rounds + 1):
        got = await _gen_round(teacher, notes, grounding, index, temp, args.per_round, concurrency)
        # ensure unique ids across rounds
        for rec in got:
            if rec.id in seen_ids:
                rec.id = uuid.uuid4().hex[:12]
            seen_ids.add(rec.id)
            pool.append(rec)
        write_jsonl(sft_path, pool)  # checkpoint after every round
        print(f"[round {r}/{args.rounds}] +{len(got)} passed  total={len(pool)}")

    # global dedup once at the end
    deduped = qf._dedup(pool, args.sim_threshold)
    write_jsonl(sft_path, deduped)
    print(f"SFT done: {len(pool)} -> {len(deduped)} after dedup -> {sft_path}")

    if args.dpo and deduped:
        base = make_teacher(base_config())
        subset = deduped[: args.dpo]

        async def dpo_worker(rec: SFTRecord) -> DPORecord:
            return await _rejected(base, rec)

        res = await map_bounded(subset, dpo_worker, concurrency=concurrency)
        pairs = [p for p in res if p is not None and p.chosen.strip() != p.rejected.strip()]
        n = write_jsonl(Path(args.dpo_out), pairs)
        print(f"DPO done: {n} pairs -> {args.dpo_out}")


if __name__ == "__main__":
    asyncio.run(main())
