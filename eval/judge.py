"""LLM-as-judge scoring: rate each generated answer 1-10 on 5 rubric dimensions.

The judge only ever sees {prompt, answer} -- never the `system` label -- so it cannot use
"which system produced this" as a scoring shortcut. Per the design spec's bias controls
(S5), the judge MUST be a different provider family than the teacher; enforced below unless
--allow-same-family is passed.

Usage:
    python eval/judge.py --answers eval/answers/teacher-grounded.jsonl
    python eval/judge.py --answers "eval/answers/*.jsonl"     # score every system in one pass
    python eval/judge.py --judge-provider nvidia --answers "eval/answers/*.jsonl"
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import asyncio
import glob
import os
from pathlib import Path

from sdx.config import gen_concurrency, provider_config
from sdx.corpus import read_jsonl, write_jsonl
from sdx.llm import Teacher, make_teacher, map_bounded

RUBRIC = ["correctness", "tradeoff_depth", "completeness", "feasibility", "clarity"]

# Providers served from the same local Ollama daemon share the same underlying model
# family (Qwen3-arch "ornith" persona, or its own future fine-tune) -- judging one with
# another from this set would violate the "judge family != teacher family" bias control.
_LOCAL_QWEN_FAMILY = {"ornith", "ollama", "finetune"}

_SYSTEM = (
    "You are a strict, senior staff-engineer panel judge for system-design answers. "
    "You score objectively and are not swayed by length, formatting, or confident tone alone."
)

_PROMPT_TMPL = """Rate the ANSWER to the REQUEST below on each dimension, 1 (poor) to 10 (excellent):

- correctness: are the technical claims and recommendations accurate, not hand-wavy or wrong?
- tradeoff_depth: does it weigh real alternatives with concrete pros/cons, not just assert one choice?
- completeness: does it cover requirements, architecture, data model, scaling, and failure modes?
- feasibility: could a real team actually build this as described (concrete tech, realistic numbers)?
- clarity: is it well-organized and easy for an engineer to act on?

# Request
{prompt}

# Answer
{answer}

Return STRICT JSON: {{"correctness": <int>, "tradeoff_depth": <int>, "completeness": <int>, \
"feasibility": <int>, "clarity": <int>, "notes": "<one sentence justification>"}}"""


def _same_family(provider_a: str, provider_b: str) -> bool:
    if provider_a in _LOCAL_QWEN_FAMILY and provider_b in _LOCAL_QWEN_FAMILY:
        return True
    return provider_a == provider_b


async def _score_one(judge: Teacher, row: dict) -> dict:
    msgs = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _PROMPT_TMPL.format(prompt=row["prompt"], answer=row["answer"])},
    ]
    data = await judge.chat_json(msgs, temperature=0.0, max_tokens=300)
    scores = {k: max(1, min(10, int(data[k]))) for k in RUBRIC}
    mean = sum(scores.values()) / len(RUBRIC)
    return {
        "id": row["id"],
        "system": row["system"],
        "scores": scores,
        "mean": round(mean, 2),
        "notes": data.get("notes", ""),
    }


async def _judge_file(path: Path, judge: Teacher, out_dir: Path) -> None:
    rows = list(read_jsonl(path))
    if not rows:
        print(f"skip {path}: empty")
        return

    async def worker(row: dict) -> dict:
        return await _score_one(judge, row)

    results = await map_bounded(rows, worker, concurrency=gen_concurrency())
    scored = [r for r in results if r is not None]
    out_path = out_dir / path.name
    n = write_jsonl(out_path, scored)
    avg = sum(r["mean"] for r in scored) / len(scored) if scored else 0.0
    print(f"{path.name}: judged {n}/{len(rows)}, mean={avg:.2f} -> {out_path}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", nargs="+", default=["eval/answers/*.jsonl"])
    ap.add_argument("--out-dir", default="eval/scores")
    ap.add_argument("--judge-provider", default=None, help="override JUDGE_PROVIDER env")
    ap.add_argument("--teacher-provider", default=None, help="override TEACHER_PROVIDER for the family check")
    ap.add_argument("--allow-same-family", action="store_true")
    args = ap.parse_args()

    judge_provider = (args.judge_provider or os.getenv("JUDGE_PROVIDER", "openai")).lower()
    teacher_provider = (args.teacher_provider or os.getenv("TEACHER_PROVIDER", "ornith")).lower()
    if not args.allow_same_family and _same_family(judge_provider, teacher_provider):
        raise SystemExit(
            f"Judge provider {judge_provider!r} is the same family as teacher {teacher_provider!r}. "
            "The eval design requires the judge to differ from the teacher family to avoid "
            "self-similarity score inflation. Set JUDGE_PROVIDER to deepseek/xai/openai/nvidia, "
            "or pass --allow-same-family to override."
        )

    judge = make_teacher(provider_config(judge_provider))
    out_dir = Path(args.out_dir)

    paths: list[Path] = []
    for pattern in args.answers:
        matched = glob.glob(pattern)
        if matched:
            paths.extend(Path(p) for p in matched)
        elif Path(pattern).exists():
            paths.append(Path(pattern))
    paths = sorted(set(paths))
    if not paths:
        raise SystemExit(f"No answer files matched {args.answers}")

    for path in paths:
        await _judge_file(path, judge, out_dir)


if __name__ == "__main__":
    asyncio.run(main())
