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
    """Minimal BM25 index over grounding chunks (no external deps)."""

    def __init__(self, pool: list[dict], k1: float = 1.5, b: float = 0.75):
        self.pool = pool
        self.k1, self.b = k1, b
        self.docs = [_tok_list(c.get("heading", "") + " " + c.get("text", "")) for c in pool]
        self.freqs = [{} for _ in self.docs]
        df: dict[str, int] = {}
        for i, toks in enumerate(self.docs):
            for t in toks:
                self.freqs[i][t] = self.freqs[i].get(t, 0) + 1
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        n = max(1, len(self.docs))
        self.avgdl = sum(len(d) for d in self.docs) / n
        # idf with +1 smoothing so common terms contribute ~0, rare terms dominate.
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def top(self, query: str, k: int) -> list[dict]:
        q = _tok_list(query)
        if not q or not self.docs:
            return []
        scored: list[tuple[float, int]] = []
        for i, freq in enumerate(self.freqs):
            dl = len(self.docs[i]) or 1
            s = 0.0
            for t in q:
                f = freq.get(t)
                if not f:
                    continue
                idf = self.idf.get(t, 0.0)
                s += idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            if s > 0:
                scored.append((s, i))
        scored.sort(key=lambda x: -x[0])
        return [self.pool[i] for _, i in scored[:k]]


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
