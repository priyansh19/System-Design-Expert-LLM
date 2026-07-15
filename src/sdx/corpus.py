"""Seed-corpus loading and JSONL helpers."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel

from sdx.config import GENERATED_DIR, SEED_CORPUS_DIR


class CorpusNote(BaseModel):
    slug: str          # filename stem, e.g. "caching"
    title: str         # first H1 in the file
    text: str          # full markdown body


def _first_h1(md: str, fallback: str) -> str:
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return fallback


def load_corpus(directory: Path = SEED_CORPUS_DIR) -> list[CorpusNote]:
    """Load every .md note from the seed corpus directory."""
    notes: list[CorpusNote] = []
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith("_"):  # skip _TEMPLATE.md and other meta files
            continue
        text = path.read_text(encoding="utf-8")
        notes.append(CorpusNote(slug=path.stem, title=_first_h1(text, path.stem), text=text))
    if not notes:
        raise RuntimeError(f"No seed-corpus notes found in {directory}")
    return notes


def corpus_index(notes: list[CorpusNote]) -> str:
    """A compact 'slug: title' index for prompting the scenario generator."""
    return "\n".join(f"- {n.slug}: {n.title}" for n in notes)


def notes_by_slugs(notes: list[CorpusNote], slugs: Iterable[str]) -> list[CorpusNote]:
    want = {s.lower() for s in slugs}
    return [n for n in notes if n.slug.lower() in want]


# --- Grounding pool (real GitHub sources, via ingest_sources.py) ---

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "the a an and or of to for in on at is are be we our need want how should can with "
    "system design service data use using each while that this it as by from".split()
)


def _tok_list(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 2]


def load_grounding(path: Path | None = None) -> list[dict]:
    """Load the ingested grounding chunks; empty list if not yet built."""
    path = path or (GENERATED_DIR / "grounding.jsonl")
    if not path.exists():
        return []
    return list(read_jsonl(path))


class _BM25:
    """BM25 index over grounding chunks (no external deps).

    Term-at-a-time scoring over an inverted index: top() only touches documents that
    share at least one token with the query (via postings[term]), not every document in
    the pool. A naive per-document linear scan is O(n_docs) per query regardless of query
    specificity -- fine at a few thousand chunks, but a real bottleneck once the grounding
    pool reaches hundreds of thousands of rows (each scenario/answer call issues its own
    retrieval). This keeps query cost proportional to how common the query's terms are,
    not to corpus size, and only stores document lengths (not full token lists) per doc.
    """

    def __init__(self, pool: list[dict], k1: float = 1.5, b: float = 0.75):
        self.pool = pool
        self.k1, self.b = k1, b
        self.doc_lens: list[int] = []
        self.postings: dict[str, dict[int, int]] = {}
        df: dict[str, int] = {}
        for i, c in enumerate(pool):
            toks = _tok_list(c.get("heading", "") + " " + c.get("text", ""))
            self.doc_lens.append(len(toks))
            seen: set[str] = set()
            for t in toks:
                bucket = self.postings.setdefault(t, {})
                bucket[i] = bucket.get(i, 0) + 1
                seen.add(t)
            for t in seen:
                df[t] = df.get(t, 0) + 1
        n = max(1, len(self.doc_lens))
        self.avgdl = (sum(self.doc_lens) / n) or 1.0
        # idf with +1 smoothing so common terms contribute ~0, rare terms dominate.
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def top(self, query: str, k: int) -> list[dict]:
        q = _tok_list(query)
        if not q or not self.doc_lens:
            return []
        scores: dict[int, float] = {}
        for t in q:
            bucket = self.postings.get(t)
            if not bucket:
                continue
            idf = self.idf.get(t, 0.0)
            for i, f in bucket.items():
                dl = self.doc_lens[i] or 1
                s = idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
                scores[i] = scores.get(i, 0.0) + s
        top_idx = sorted(scores, key=lambda i: -scores[i])[:k]
        return [self.pool[i] for i in top_idx]


_bm25_cache: dict[int, _BM25] = {}


def retrieve_grounding(query: str, pool: list[dict], k: int = 3) -> list[dict]:
    """BM25 top-k retrieval of grounding chunks (index cached per pool identity)."""
    if not pool:
        return []
    key = id(pool)
    idx = _bm25_cache.get(key)
    if idx is None:
        idx = _BM25(pool)
        _bm25_cache[key] = idx
    return idx.top(query, k)


# --- JSONL io ---

def write_jsonl(path: Path, rows: Iterable[BaseModel | dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            payload = row.model_dump() if isinstance(row, BaseModel) else row
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)
