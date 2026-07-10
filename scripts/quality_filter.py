"""Filter raw SFT candidates: structure + length gates, then embedding dedup.

Usage:
    python scripts/quality_filter.py --in data/generated/sft_raw.jsonl \
        --out data/generated/sft.jsonl --min-words 300 --max-words 1400 --sim-threshold 0.92
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import re
from pathlib import Path

import numpy as np

from sdx.config import GENERATED_DIR
from sdx.corpus import read_jsonl, write_jsonl
from sdx.schema import ANSWER_SECTIONS, SFTRecord

# Match a section header at 2-4 hash levels (teachers vary between ## and ###).
_HEADER_RE = {
    s: re.compile(rf"^#{{2,4}}\s+{re.escape(s)}\s*$", re.MULTILINE) for s in ANSWER_SECTIONS
}


def _structure_ok(output: str) -> bool:
    """All required section headers present, in order (any heading depth ##-####)."""
    pos = -1
    for section in ANSWER_SECTIONS:
        m = _HEADER_RE[section].search(output, pos + 1)
        if not m or m.start() <= pos:
            return False
        pos = m.start()
    return True


def _passes_gates(rec: SFTRecord, min_words: int, max_words: int) -> bool:
    words = len(rec.output.split())
    if words < min_words or words > max_words:
        return False
    if not _structure_ok(rec.output):
        return False
    if len(rec.instruction.split()) < 8:  # too-thin prompt
        return False
    return True


def _embed(texts: list[str]) -> np.ndarray:
    from fastembed import TextEmbedding  # lazy: heavy import

    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    vecs = np.array(list(model.embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


def _dedup(records: list[SFTRecord], threshold: float) -> list[SFTRecord]:
    """Greedy near-duplicate removal on cosine similarity of the instruction+answer."""
    if len(records) < 2:
        return records
    vecs = _embed([f"{r.instruction}\n{r.output}" for r in records])
    keep: list[int] = []
    kept_vecs: list[np.ndarray] = []
    for i, v in enumerate(vecs):
        if kept_vecs and max(float(v @ kv) for kv in kept_vecs) >= threshold:
            continue
        keep.append(i)
        kept_vecs.append(v)
    return [records[i] for i in keep]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(GENERATED_DIR / "sft_raw.jsonl"))
    ap.add_argument("--out", default=str(GENERATED_DIR / "sft.jsonl"))
    ap.add_argument("--min-words", type=int, default=300)
    ap.add_argument("--max-words", type=int, default=1400)
    ap.add_argument("--sim-threshold", type=float, default=0.92)
    ap.add_argument("--no-dedup", action="store_true")
    args = ap.parse_args()

    raw = [SFTRecord(**row) for row in read_jsonl(Path(args.inp))]
    gated = [r for r in raw if _passes_gates(r, args.min_words, args.max_words)]
    deduped = gated if args.no_dedup else _dedup(gated, args.sim_threshold)

    n = write_jsonl(Path(args.out), deduped)
    print(
        f"in={len(raw)} passed_gates={len(gated)} after_dedup={n} -> {args.out}\n"
        f"(dropped {len(raw) - len(gated)} on gates, {len(gated) - n} as duplicates)"
    )


if __name__ == "__main__":
    main()
