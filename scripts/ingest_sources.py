"""Ingest trusted GitHub system-design sources into a grounding pool.

Splits authoritative markdown into heading-scoped chunks, cleans noise, and
writes data/generated/grounding.jsonl: {source, heading, text, words}.

Usage:
    python scripts/ingest_sources.py --out data/generated/grounding.jsonl --min-words 40
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import re
from pathlib import Path

from sdx.config import DATA_DIR, GENERATED_DIR
from sdx.corpus import write_jsonl

SOURCES_DIR = DATA_DIR / "sources"

# Curated high-text-value files (English only; skip i18n copies and link lists).
SOURCE_FILES = [
    ("system-design-primer", "system-design-primer/README.md"),
    ("karanpratapsingh/system-design", "system-design/README.md"),
    ("bytebytego/system-design-101", "system-design-101/README.md"),
]

_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_HTML = re.compile(r"<[^>]+>")
_BADGE = re.compile(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")  # keep link text, drop url
_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")


def _clean(text: str) -> str:
    text = _BADGE.sub("", text)
    text = _IMG.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _HTML.sub("", text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    # drop table-of-contents-ish and empty-heavy noise
    out: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append("")
            continue
        if s.startswith(("* [", "- [", "|")) and len(s) < 4:
            continue
        out.append(ln)
    # collapse 3+ blank lines
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _chunk_by_heading(md: str) -> list[tuple[str, str]]:
    """Split into (heading, body) at ## / ### boundaries."""
    chunks: list[tuple[str, str]] = []
    cur_head = "Overview"
    cur_body: list[str] = []
    for ln in md.splitlines():
        m = _HEADING.match(ln)
        if m and len(m.group(1)) in (2, 3):
            if cur_body:
                chunks.append((cur_head, "\n".join(cur_body).strip()))
            cur_head = m.group(2).strip()
            cur_body = []
        else:
            cur_body.append(ln)
    if cur_body:
        chunks.append((cur_head, "\n".join(cur_body).strip()))
    return chunks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(GENERATED_DIR / "grounding.jsonl"))
    ap.add_argument("--min-words", type=int, default=40)
    args = ap.parse_args()

    rows: list[dict] = []
    for source, rel in SOURCE_FILES:
        path = SOURCES_DIR / rel
        if not path.exists():
            print(f"WARN missing {path}; run the git clone step first.")
            continue
        cleaned = _clean(path.read_text(encoding="utf-8", errors="ignore"))
        for heading, body in _chunk_by_heading(cleaned):
            body = _clean(body)
            words = len(body.split())
            if words < args.min_words:
                continue
            rows.append({"source": source, "heading": heading, "text": body, "words": words})

    n = write_jsonl(Path(args.out), rows)
    total_words = sum(r["words"] for r in rows)
    print(f"Wrote {n} grounding chunks ({total_words:,} words) -> {args.out}")
    by_src: dict[str, int] = {}
    for r in rows:
        by_src[r["source"]] = by_src.get(r["source"], 0) + 1
    for s, c in by_src.items():
        print(f"  {s}: {c} chunks")


if __name__ == "__main__":
    main()
