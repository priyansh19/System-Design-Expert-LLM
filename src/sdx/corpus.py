"""Seed-corpus loading and JSONL helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel

from sdx.config import SEED_CORPUS_DIR


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
