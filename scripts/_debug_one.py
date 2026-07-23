"""One-shot debug: generate a single scenario + answer and show why gates pass/fail."""

import _bootstrap  # noqa: F401

import asyncio
import sys

import gen_answers as ga
import gen_scenarios as gs
import quality_filter as qf

from sdx.config import provider_config, gen_temperature
from sdx.corpus import corpus_index, load_corpus, load_grounding
from sdx.llm import make_teacher
from sdx.schema import ANSWER_SECTIONS


async def main() -> None:
    notes = load_corpus()
    grounding = load_grounding()
    index = corpus_index(notes)
    # optional argv[1] = provider override (e.g. "mesh"); .env override=True means shell
    # env vars can't select the provider, mirroring run_pipeline's --teacher-provider flag
    provider = sys.argv[1] if len(sys.argv) > 1 else None
    teacher = make_teacher(provider_config(provider))
    print("provider:", teacher.cfg.name, teacher.cfg.model)
    temp = gen_temperature()

    scn = await gs._one(teacher, index, "fintech", "mid-scale", temp)
    print("SCENARIO OK:", scn.prompt[:160], "| topics:", scn.topics)

    rec = await ga._one(teacher, scn, notes, grounding, temp)
    words = len(rec.output.split())
    print("ANSWER words:", words, "(gate: 300-1400)")
    missing = [s for s in ANSWER_SECTIONS if f"## {s}" not in rec.output]
    print("missing section headers:", missing or "none")
    print("passes gates:", qf._passes_gates(rec, 300, 1400))
    print("---- first 500 chars ----")
    print(rec.output[:500])
    print("---- last 300 chars ----")
    print(rec.output[-300:])


if __name__ == "__main__":
    asyncio.run(main())
