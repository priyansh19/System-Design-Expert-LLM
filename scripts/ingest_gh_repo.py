"""Ingest every markdown file from a GitHub repo into the grounding pool, heading-scoped
and cleaned the same way ingest_sources.py handles its curated SOURCE_FILES -- but fetched
live via the GitHub API/raw URLs instead of requiring a local clone, and idempotently merged
the same way ingest_papers.py / ingest_hf_dataset.py handle their own --source-tag rows.

Usage:
    python scripts/ingest_gh_repo.py --repo design-gurus/grokking-system-design \
        --source-tag github:grokking-system-design
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import urllib.request
from pathlib import Path

from ingest_sources import _chunk_by_heading, _clean  # reuse heading-chunker + noise cleaner

from sdx.config import GENERATED_DIR
from sdx.corpus import read_jsonl, write_jsonl

_UA = {"User-Agent": "Mozilla/5.0 (compatible; sdx-grounding/1.0)"}
_DEFAULT_EXCLUDE = ("_template", "CONTRIBUTING", ".github/")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def list_markdown_files(repo: str, branch: str, exclude: tuple[str, ...]) -> list[str]:
    import json

    tree = json.loads(_get(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"))
    paths = [
        n["path"]
        for n in tree["tree"]
        if n["type"] == "blob"
        and n["path"].endswith(".md")
        and not any(x in n["path"] for x in exclude)
    ]
    return paths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name, e.g. design-gurus/grokking-system-design")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--source-tag", required=True, help="grounding 'source' value, e.g. github:grokking-system-design")
    ap.add_argument("--out", default=str(GENERATED_DIR / "grounding.jsonl"))
    ap.add_argument("--min-words", type=int, default=30)
    ap.add_argument("--exclude", nargs="*", default=list(_DEFAULT_EXCLUDE))
    args = ap.parse_args()

    files = list_markdown_files(args.repo, args.branch, tuple(args.exclude))
    print(f"found {len(files)} markdown files in {args.repo}@{args.branch}")

    rows: list[dict] = []
    failed: list[str] = []
    for path in files:
        raw_url = f"https://raw.githubusercontent.com/{args.repo}/{args.branch}/{path}"
        try:
            md = _get(raw_url).decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001 - report and continue, never abort the run
            failed.append(f"{path}: {type(e).__name__}: {e}")
            continue
        cleaned = _clean(md)
        for heading, body in _chunk_by_heading(cleaned):
            body = _clean(body)
            words = len(body.split())
            if words < args.min_words:
                continue
            rows.append(
                {"source": args.source_tag, "heading": f"{path} -- {heading}", "text": body, "words": words}
            )

    out_path = Path(args.out)
    existing = [r for r in read_jsonl(out_path) if r.get("source") != args.source_tag] if out_path.exists() else []
    merged = existing + rows
    write_jsonl(out_path, merged)

    total_words = sum(r["words"] for r in rows)
    print(
        f"\nWrote {len(rows)} chunks ({total_words:,} words) from {len(files) - len(failed)}/{len(files)} files "
        f"({len(failed)} failed).\n"
        f"Grounding pool now {len(merged):,} rows ({len(existing):,} other + {len(rows)} '{args.source_tag}') "
        f"-> {out_path}"
    )
    for f in failed:
        print(f"  FAILED {f}")


if __name__ == "__main__":
    main()
