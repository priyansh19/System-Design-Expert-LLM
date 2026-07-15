"""Generate answers to the held-out eval set from any configured provider.

Two modes:
  grounded -- the EXACT production code path (gen_answers.py's _one): teacher + curated
              notes + BM25-retrieved grounding chunks. Use this to score whether the
              *data-collection pipeline itself* (post-fixes) produces good answers, before
              spending Kaggle GPU-hours training on its output.
  bare     -- just the raw prompt, no retrieval. Mirrors real inference: RAG is not wired
              in at inference time (v1 design, out-of-scope), so a trained model only ever
              sees the bare instruction. Use this for base/fine-tune/frontier comparisons.

Usage:
    # Does the current pipeline (grounding + recent fixes) produce good data?
    python eval/generate.py --system teacher-grounded --provider ornith --mode grounded

    # Ablation: same teacher, no grounding -- shows how much the corpus lifts quality.
    python eval/generate.py --system teacher-bare --provider ornith --mode bare

    # Sanity floor: tiny base model bare, should score clearly lower than both above.
    python eval/generate.py --system base-bare --provider ollama --mode bare

    # Once trained + merged + `ollama create`-d (see .env FINETUNE_MODEL):
    python eval/generate.py --system finetune --provider finetune --mode bare
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import asyncio
from pathlib import Path

from gen_answers import SYSTEM as _GROUNDED_SYSTEM
from gen_answers import _one as _grounded_one

from sdx.config import gen_concurrency, gen_temperature, provider_config
from sdx.corpus import load_corpus, load_grounding, read_jsonl, write_jsonl
from sdx.llm import Teacher, make_teacher, map_bounded
from sdx.schema import Scenario

# Same persona used for production SFT generation, kept identical in bare mode so scoring
# reflects what the deployed model actually sees (its system prompt / Modelfile persona),
# not an unrelated instruction.
_BARE_SYSTEM = _GROUNDED_SYSTEM


async def _bare_one(teacher: Teacher, scn: Scenario, temp: float) -> dict:
    msgs = [
        {"role": "system", "content": _BARE_SYSTEM},
        {"role": "user", "content": scn.prompt},
    ]
    answer = await teacher.chat(msgs, temperature=temp, max_tokens=3000)
    return {
        "id": scn.id,
        "prompt": scn.prompt,
        "domain": scn.domain,
        "scale": scn.scale,
        "answer": answer.strip(),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default="eval/prompts.jsonl")
    ap.add_argument("--system", required=True, help="run label, e.g. teacher-grounded")
    ap.add_argument(
        "--provider", required=True, help="provider config name: ornith/deepseek/xai/openai/ollama/finetune"
    )
    ap.add_argument("--mode", choices=["grounded", "bare"], default="bare")
    ap.add_argument("--out-dir", default="eval/answers")
    args = ap.parse_args()

    scenarios = [Scenario(**row) for row in read_jsonl(Path(args.prompts))]
    if not scenarios:
        raise SystemExit(f"{args.prompts} is empty; run eval/make_prompts.py first.")

    teacher = make_teacher(provider_config(args.provider))
    temp = gen_temperature()

    if args.mode == "grounded":
        notes = load_corpus()
        grounding = load_grounding()

        async def worker(scn: Scenario) -> dict:
            rec = await _grounded_one(teacher, scn, notes, grounding, temp)
            return {
                "id": rec.id,
                "prompt": rec.instruction,
                "domain": rec.domain,
                "scale": rec.scale,
                "answer": rec.output,
            }
    else:

        async def worker(scn: Scenario) -> dict:
            return await _bare_one(teacher, scn, temp)

    results = await map_bounded(scenarios, worker, concurrency=gen_concurrency())
    answers = [r for r in results if r is not None]
    for a in answers:
        a["system"] = args.system

    out_path = Path(args.out_dir) / f"{args.system}.jsonl"
    n = write_jsonl(out_path, answers)
    print(f"Wrote {n}/{len(scenarios)} answers for system={args.system!r} ({args.mode}) -> {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
