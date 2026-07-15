"""Ingest an Alpaca-style {instruction, input, output} JSONL dataset from a HuggingFace
dataset repo into the grounding pool, following the same idempotent-merge pattern as
ingest_papers.py: existing rows for this --source-tag are replaced on re-run, everything
else (papers, GitHub sources, other datasets) is preserved.

Usage:
    python scripts/ingest_hf_dataset.py --repo ajibawa-2023/Software-Architecture \
        --file Software_Architecture_Final.jsonl \
        --source-tag dataset:ajibawa-software-architecture
    python scripts/ingest_hf_dataset.py --repo <owner>/<name> --file <name>.jsonl \
        --source-tag dataset:<slug> --limit 500   # smoke-test a subset
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import json
import re
import urllib.request
from pathlib import Path

from ingest_papers import chunk  # reuse the existing word-bounded chunker

from sdx.config import DATA_DIR, GENERATED_DIR
from sdx.corpus import read_jsonl, write_jsonl

DATASETS_DIR = DATA_DIR / "sources" / "hf_datasets"

_UA = {"User-Agent": "Mozilla/5.0 (compatible; sdx-grounding/1.0)"}
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_WS = re.compile(r"[ \t\u00a0]+")
_NL = re.compile(r"\s*\n\s*")


def download(repo: str, file: str, dest: Path) -> Path:
    """Stream a raw dataset file to dest (cached; skip if already present and non-empty)."""
    if dest.exists() and dest.stat().st_size > 1024:
        return dest
    url = f"https://huggingface.co/datasets/{repo}/resolve/main/{file}"
    req = urllib.request.Request(url, headers=_UA)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as out:
        while chunk_bytes := r.read(1 << 20):
            out.write(chunk_bytes)
    tmp.rename(dest)
    return dest


def clean(text: str) -> str:
    text = "".join(ch for ch in text if not 0xD800 <= ord(ch) <= 0xDFFF)
    text = _CTRL.sub(" ", text)
    text = _NL.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="HF dataset repo id, e.g. ajibawa-2023/Software-Architecture")
    ap.add_argument("--file", required=True, help="jsonl filename within the repo")
    ap.add_argument("--source-tag", required=True, help="grounding 'source' value, e.g. dataset:ajibawa-software-architecture")
    ap.add_argument("--out", default=str(GENERATED_DIR / "grounding.jsonl"))
    ap.add_argument("--chunk-words", type=int, default=220)
    ap.add_argument("--overlap", type=int, default=30)
    ap.add_argument("--min-words", type=int, default=60)
    ap.add_argument("--limit", type=int, default=0, help="cap rows processed (0 = all); for smoke tests")
    args = ap.parse_args()

    out_path = Path(args.out)
    local_name = args.repo.replace("/", "__") + "__" + args.file
    raw_path = download(args.repo, args.file, DATASETS_DIR / local_name)
    print(f"downloaded/cached: {raw_path} ({raw_path.stat().st_size:,} bytes)")

    new_rows: list[dict] = []
    total_words = 0
    seen = 0
    skipped = 0
    with raw_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if args.limit and seen >= args.limit:
                break
            seen += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            instruction = clean(str(row.get("instruction", "")))
            extra_input = clean(str(row.get("input", "")))
            output = clean(str(row.get("output", "")))
            if not instruction or not output:
                skipped += 1
                continue
            heading = instruction if not extra_input else f"{instruction} -- {extra_input}"
            heading = heading[:300]
            pieces = chunk(output, args.chunk_words, args.overlap)
            for i, piece in enumerate(pieces):
                words = len(piece.split())
                if words < args.min_words:
                    continue
                piece_heading = heading if len(pieces) == 1 else f"{heading} [{i + 1}/{len(pieces)}]"
                new_rows.append(
                    {"source": args.source_tag, "heading": piece_heading, "text": piece, "words": words}
                )
                total_words += words
            if seen % 50000 == 0:
                print(f"  ...processed {seen:,} rows, {len(new_rows):,} chunks so far")

    existing = [r for r in read_jsonl(out_path) if r.get("source") != args.source_tag] if out_path.exists() else []
    merged = existing + new_rows
    write_jsonl(out_path, merged)

    print(
        f"\nWrote {len(new_rows):,} chunks ({total_words:,} words) from {seen:,} source rows "
        f"({skipped:,} skipped/empty).\n"
        f"Grounding pool now {len(merged):,} rows ({len(existing):,} other + {len(new_rows):,} "
        f"'{args.source_tag}') -> {out_path}"
    )


if __name__ == "__main__":
    main()
