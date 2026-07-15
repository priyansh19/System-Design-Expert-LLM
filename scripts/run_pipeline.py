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

from sdx.config import GENERATED_DIR, base_config, gen_concurrency, gen_temperature, provider_config
from sdx.corpus import (
    corpus_index,
    load_corpus,
    load_grounding,
    read_jsonl,
    write_jsonl,
)
from sdx.llm import make_teacher, map_bounded
from sdx.schema import DPORecord, SFTRecord


# Round-robin offset advances across rounds (see main()) so a multi-round run actually
# visits every (domain, scale) grid cell instead of re-hitting the first `per-round` cells
# every time. Without the offset, per_round < len(grid) meant whole domains never appeared.


def _topic_sig(rec: SFTRecord) -> tuple[str, ...]:
    """Exact topic-set signature, used to cap how many scenarios share the same
    corpus-topic combination (a proxy for 'same architecture pattern, different domain
    dressing' near-duplicates that embedding dedup alone tends to miss)."""
    return tuple(sorted(t.lower() for t in rec.topics))


MAX_PER_TOPIC_SIG = 3


async def _gen_round(
    teacher, notes, grounding, index, temp, n, concurrency, offset: int = 0
) -> list[SFTRecord]:
    grid = [(d, s) for d in gs.DOMAINS for s in gs.SCALES]
    work = [grid[(offset + i) % len(grid)] for i in range(n)]

    async def scn_worker(pair):
        return await gs._one(teacher, index, pair[0], pair[1], temp)

    scn_res = await map_bounded(work, scn_worker, concurrency=concurrency, label="scenarios")
    scenarios = [s for s in scn_res if s is not None]

    async def ans_worker(scn):
        return await ga._one(teacher, scn, notes, grounding, temp)

    ans_res = await map_bounded(scenarios, ans_worker, concurrency=concurrency, label="answers")
    answers = [a for a in ans_res if a is not None]
    # structure + length gates (per-record; dedup + topic-diversity cap happen per round)
    return [r for r in answers if qf._passes_gates(r, 300, 1400)]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--per-round", type=int, default=20)
    ap.add_argument("--dpo", type=int, default=1200, help="max DPO pairs to build (0 to skip)")
    ap.add_argument("--sim-threshold", type=float, default=0.92)
    ap.add_argument("--sft-out", default=str(GENERATED_DIR / "sft.jsonl"))
    ap.add_argument("--dpo-out", default=str(GENERATED_DIR / "dpo.jsonl"))
    ap.add_argument(
        "--teacher-provider", default=None,
        help="override TEACHER_PROVIDER env for this run (e.g. 'cerebras'); lets multiple "
        "provider streams run concurrently against the same shared .env",
    )
    ap.add_argument(
        "--concurrency", type=int, default=None,
        help="override GEN_CONCURRENCY env for this run -- needed when two teacher streams "
        "share one .env but have different TPM-vs-concurrency tradeoffs (e.g. Groq's small "
        "6K TPM budget wants concurrency=1 to avoid 429 churn under padded reasoning-token "
        "requests, while a generous-TPM provider like Cerebras tolerates 2+)",
    )
    args = ap.parse_args()

    notes = load_corpus()
    grounding = load_grounding()
    index = corpus_index(notes)
    teacher = make_teacher(provider_config(args.teacher_provider))
    temp = gen_temperature()
    concurrency = args.concurrency if args.concurrency is not None else gen_concurrency()
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
        sig_counts: dict[tuple[str, ...], int] = {}
        for rec in pool:
            sig_counts[_topic_sig(rec)] = sig_counts.get(_topic_sig(rec), 0) + 1

        got = await _gen_round(
            teacher, notes, grounding, index, temp, args.per_round, concurrency,
            offset=(r - 1) * args.per_round,
        )
        kept = 0
        for rec in got:
            sig = _topic_sig(rec)
            if sig_counts.get(sig, 0) >= MAX_PER_TOPIC_SIG:
                continue  # topic combination already well-represented; drop for diversity
            sig_counts[sig] = sig_counts.get(sig, 0) + 1
            if rec.id in seen_ids:
                rec.id = uuid.uuid4().hex[:12]
            seen_ids.add(rec.id)
            pool.append(rec)
            kept += 1

        # Dedup every round (not just once at the end): keeps the on-disk checkpoint
        # clean so an interrupted run + resume never compounds near-duplicates.
        pool = qf._dedup(pool, args.sim_threshold)
        seen_ids = {rec.id for rec in pool}
        write_jsonl(sft_path, pool)
        print(
            f"[round {r}/{args.rounds}] +{kept}/{len(got)} kept "
            f"(topic-cap+dedup)  total={len(pool)}"
        )

    print(f"SFT done: {len(pool)} records -> {sft_path}")

    if args.dpo and pool:
        base = make_teacher(base_config())
        subset = pool[: args.dpo]

        async def dpo_worker(rec: SFTRecord) -> DPORecord:
            return await _rejected(base, rec)

        res = await map_bounded(subset, dpo_worker, concurrency=concurrency)
        pairs = [p for p in res if p is not None and p.chosen.strip() != p.rejected.strip()]
        n = write_jsonl(Path(args.dpo_out), pairs)
        print(f"DPO done: {n} pairs -> {args.dpo_out}")


if __name__ == "__main__":
    asyncio.run(main())
