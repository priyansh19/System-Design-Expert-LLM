"""Generate diverse, realistic system-design scenarios grounded in the seed corpus.

Usage:
    python scripts/gen_scenarios.py --n 500 --out data/generated/scenarios.jsonl
"""

from __future__ import annotations

import _bootstrap  # noqa: F401  (sys.path shim)

import argparse
import asyncio
import uuid
from pathlib import Path

from sdx.config import GENERATED_DIR, gen_concurrency, gen_temperature, teacher_config
from sdx.corpus import corpus_index, load_corpus, write_jsonl
from sdx.llm import Teacher, make_teacher, map_bounded
from sdx.schema import Scenario

DOMAINS = [
    "fintech", "social", "ecommerce", "iot", "media-streaming", "healthcare",
    "logistics", "gaming", "ads", "developer-tools", "ride-sharing", "collaboration",
    "ai-infrastructure",
]
SCALES = ["startup", "mid-scale", "hyperscale"]

SYSTEM = (
    "You are a distinguished systems architect creating training scenarios. "
    "You produce realistic production requirements that a company would actually face."
)

PROMPT_TMPL = """Using the system-design knowledge topics below, invent ONE realistic \
architecture requirement for the domain "{domain}" at "{scale}" scale.

Topics available (slug: title):
{index}

Rules:
- The requirement must read like a real ask from a product/eng leader, with concrete \
numbers where natural (users, QPS, latency, data volume) appropriate to the scale.
- It must be answerable by reasoning about 3-6 of the topics above.
- Vary the framing; do NOT default to "design Twitter"-style clones.

Return STRICT JSON:
{{"prompt": "<the requirement, 2-4 sentences>", "topics": ["<slug>", ...]}}"""


async def _one(teacher: Teacher, index: str, domain: str, scale: str, temp: float) -> Scenario:
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": PROMPT_TMPL.format(domain=domain, scale=scale, index=index)},
    ]
    data = await teacher.chat_json(msgs, temperature=temp, max_tokens=800)
    return Scenario(
        id=uuid.uuid4().hex[:12],
        domain=domain,
        scale=scale,
        prompt=data["prompt"].strip(),
        topics=[t.strip().lower() for t in data.get("topics", [])],
    )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500, help="number of scenarios")
    ap.add_argument("--out", type=str, default=str(GENERATED_DIR / "scenarios.jsonl"))
    args = ap.parse_args()

    notes = load_corpus()
    index = corpus_index(notes)
    teacher = make_teacher(teacher_config())
    temp = gen_temperature()

    # Build a balanced grid of (domain, scale) work items cycling to n.
    grid = [(d, s) for d in DOMAINS for s in SCALES]
    work = [grid[i % len(grid)] for i in range(args.n)]

    async def worker(pair: tuple[str, str]) -> Scenario:
        return await _one(teacher, index, pair[0], pair[1], temp)

    results = await map_bounded(work, worker, concurrency=gen_concurrency())
    scenarios = [r for r in results if r is not None]
    n = write_jsonl(Path(args.out), scenarios)
    print(f"Wrote {n}/{args.n} scenarios -> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
