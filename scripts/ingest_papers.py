"""Ingest canonical + expanded system-design/AI-infra research papers into the grounding pool.

Downloads a curated set of foundational distributed-systems / architecture papers, plus a much
larger expanded set (data/sources/paper_list.json -- LLM serving, training infra, vector/RAG
infra, classic distributed-systems gaps, and AI-platform/MLOps papers) covering "best practices"
for reliable, scalable systems including modern AI infrastructure. Extracts and cleans PDF text,
splits each into word-bounded chunks, and *merges* them into data/generated/grounding.jsonl in
the same {source, heading, text, words} schema the pipeline already retrieves over.

Idempotent: existing rows whose source starts with "paper:" are replaced on re-run;
GitHub-sourced grounding rows are preserved. PDFs are cached under data/sources/papers/.
Downloads run concurrently (--workers, default 8); a failed/unreachable PDF is skipped and
logged, never aborting the run.

Usage:
    python scripts/ingest_papers.py                 # download + ingest curated + expanded list
    python scripts/ingest_papers.py --chunk-words 220 --overlap 30 --min-words 60
    python scripts/ingest_papers.py --workers 16 --limit 50   # smoke-test a subset
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import json
import re
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pypdf import PdfReader

from sdx.config import DATA_DIR, GENERATED_DIR
from sdx.corpus import read_jsonl, write_jsonl

PAPERS_DIR = DATA_DIR / "sources" / "papers"
PAPER_LIST_JSON = DATA_DIR / "sources" / "paper_list.json"

# (name, title, url) — every URL verified as a freely-downloadable PDF.
PAPERS: list[tuple[str, str, str]] = [
    # --- Replicated / distributed storage ---
    ("dynamo", "Dynamo: Amazon's Highly Available Key-value Store",
     "https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf"),
    ("gfs", "The Google File System",
     "https://static.googleusercontent.com/media/research.google.com/en//archive/gfs-sosp2003.pdf"),
    ("bigtable", "Bigtable: A Distributed Storage System for Structured Data",
     "https://static.googleusercontent.com/media/research.google.com/en//archive/bigtable-osdi06.pdf"),
    ("cassandra", "Cassandra: A Decentralized Structured Storage System",
     "https://www.cs.cornell.edu/projects/ladis2009/papers/lakshman-ladis2009.pdf"),
    ("haystack", "Finding a Needle in Haystack: Facebook's Photo Storage",
     "https://www.usenix.org/legacy/event/osdi10/tech/full_papers/Beaver.pdf"),
    ("spanner", "Spanner: Google's Globally-Distributed Database",
     "https://static.googleusercontent.com/media/research.google.com/en//archive/spanner-osdi2012.pdf"),
    ("megastore", "Megastore: Providing Scalable, Highly Available Storage for Interactive Services",
     "https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/36971.pdf"),
    ("f1", "F1: A Distributed SQL Database That Scales",
     "https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/41344.pdf"),
    ("aurora", "Amazon Aurora: Design Considerations for High Throughput Cloud-Native Relational Databases",
     "https://web.stanford.edu/class/cs245/readings/aurora.pdf"),
    # --- Consensus / coordination ---
    ("raft", "In Search of an Understandable Consensus Algorithm (Raft)",
     "https://raft.github.io/raft.pdf"),
    ("paxos-simple", "Paxos Made Simple",
     "https://lamport.azurewebsites.net/pubs/paxos-simple.pdf"),
    ("zookeeper", "ZooKeeper: Wait-free Coordination for Internet-scale Systems",
     "https://www.usenix.org/legacy/event/atc10/tech/full_papers/Hunt.pdf"),
    ("chubby", "The Chubby Lock Service for Loosely-Coupled Distributed Systems",
     "https://static.googleusercontent.com/media/research.google.com/en//archive/chubby-osdi06.pdf"),
    # --- Data processing / pipelines ---
    ("mapreduce", "MapReduce: Simplified Data Processing on Large Clusters",
     "https://static.googleusercontent.com/media/research.google.com/en//archive/mapreduce-osdi04.pdf"),
    ("percolator", "Large-scale Incremental Processing Using Distributed Transactions and Notifications (Percolator)",
     "https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/36726.pdf"),
    ("dataflow", "The Dataflow Model: Balancing Correctness, Latency, and Cost in Massive-Scale Data Processing",
     "https://www.vldb.org/pvldb/vol8/p1792-Akidau.pdf"),
    ("millwheel", "MillWheel: Fault-Tolerant Stream Processing at Internet Scale",
     "https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/41378.pdf"),
    ("kafka", "Kafka: a Distributed Messaging System for Log Processing",
     "http://notes.stephenholiday.com/Kafka.pdf"),
    # --- Caching / social graph ---
    ("memcache", "Scaling Memcache at Facebook",
     "https://www.usenix.org/system/files/conference/nsdi13/nsdi13-final170_update.pdf"),
    ("tao", "TAO: Facebook's Distributed Data Store for the Social Graph",
     "https://www.usenix.org/system/files/conference/atc13/atc13-bronson.pdf"),
    # --- Observability / scheduling ---
    ("dapper", "Dapper, a Large-Scale Distributed Systems Tracing Infrastructure",
     "https://static.googleusercontent.com/media/research.google.com/en//archive/papers/dapper-2010-1.pdf"),
    ("monarch", "Monarch: Google's Planet-Scale In-Memory Time Series Database",
     "https://www.vldb.org/pvldb/vol13/p3181-adams.pdf"),
    ("borg", "Large-scale Cluster Management at Google with Borg",
     "https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/43438.pdf"),
    # --- Foundational principles / algorithms ---
    ("time-clocks", "Time, Clocks, and the Ordering of Events in a Distributed System",
     "https://lamport.azurewebsites.net/pubs/time-clocks.pdf"),
    ("end-to-end", "End-to-End Arguments in System Design",
     "https://web.mit.edu/Saltzer/www/publications/endtoend/endtoend.pdf"),
    ("tail-at-scale", "The Tail at Scale",
     "https://www.barroso.org/publications/TheTailAtScale.pdf"),
    ("consistent-hashing", "Consistent Hashing and Random Trees",
     "https://www.cs.princeton.edu/courses/archive/fall09/cos518/papers/chash.pdf"),
    ("chord", "Chord: A Scalable Peer-to-peer Lookup Service for Internet Applications",
     "https://pdos.csail.mit.edu/papers/chord:sigcomm01/chord_sigcomm.pdf"),
    ("harvest-yield", "Harvest, Yield, and Scalable Tolerant Systems",
     "https://radlab.cs.berkeley.edu/people/fox/static/pubs/pdf/c18.pdf"),
]

# Lenient SSL context: a couple of academic hosts serve valid PDFs behind
# certificate chains the local trust store can't verify.
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_UA = {"User-Agent": "Mozilla/5.0 (compatible; sdx-grounding/1.0)"}

# References/bibliography tail markers — cut here to keep citations out of grounding.
_REF_MARKER = re.compile(r"\n\s*(references|bibliography|acknowledg(e)?ments)\s*\n", re.I)
_DEHYPHEN = re.compile(r"([A-Za-z])-\n([a-z])")
_WS = re.compile(r"[ \t\u00a0]+")
_NL = re.compile(r"\s*\n\s*")
_PAGE_NO = re.compile(r"^\s*\d+\s*$")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def download(name: str, url: str, dest: Path) -> Path:
    """Download a PDF to dest (cached; skip if already present and non-empty)."""
    if dest.exists() and dest.stat().st_size > 1024:
        return dest
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=60, context=_SSL_CTX) as r:
        data = r.read()
    if data[:5] != b"%PDF-":
        raise RuntimeError(f"{name}: not a PDF (got {data[:16]!r})")
    dest.write_bytes(data)
    return dest


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def clean(text: str) -> str:
    # pypdf occasionally decodes garbled font encodings into lone UTF-16 surrogate
    # codepoints (U+D800-DFFF); those are unpaired and cannot be UTF-8 encoded at all,
    # so they must be dropped before any downstream JSON write, not just replaced.
    text = "".join(ch for ch in text if not 0xD800 <= ord(ch) <= 0xDFFF)
    text = _CTRL.sub(" ", text)
    text = _DEHYPHEN.sub(r"\1\2", text)            # join hyphenated line breaks
    # drop obvious standalone page numbers
    text = "\n".join("" if _PAGE_NO.match(ln) else ln for ln in text.splitlines())
    text = _NL.sub(" ", text)                        # flatten intra-paragraph newlines
    text = _WS.sub(" ", text).strip()
    # cut the reference/bibliography tail if it appears past the halfway mark
    m = None
    for cand in _REF_MARKER.finditer(text):
        if cand.start() > len(text) * 0.5:
            m = cand
            break
    if m:
        text = text[: m.start()].strip()
    return text


def chunk(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = max(1, size - overlap)
    out: list[str] = []
    for i in range(0, len(words), step):
        piece = words[i : i + size]
        out.append(" ".join(piece))
        if i + size >= len(words):
            break
    return out


def _load_extended() -> list[tuple[str, str, str]]:
    """Load the expanded paper list (name, title, url) from data/sources/paper_list.json,
    if present. Generated by a research/re-ranking pass; see docs/superpowers/specs/."""
    if not PAPER_LIST_JSON.exists():
        return []
    rows = json.loads(PAPER_LIST_JSON.read_text(encoding="utf-8"))
    return [(r["name"], r["title"], r["url"]) for r in rows]


def _process_one(
    name: str, title: str, url: str, chunk_words: int, overlap: int, min_words: int
) -> tuple[str, list[dict], int, str | None]:
    """Download + extract + chunk one paper. Returns (name, rows, total_words, error)."""
    try:
        pdf = download(name, url, PAPERS_DIR / f"{name}.pdf")
        body = clean(extract_text(pdf))
    except Exception as e:  # noqa: BLE001 - report and continue
        return name, [], 0, f"{type(e).__name__}: {e}"
    source = f"paper:{name}"
    pieces = chunk(body, chunk_words, overlap)
    rows: list[dict] = []
    for i, piece in enumerate(pieces):
        words = len(piece.split())
        if words < min_words:
            continue
        heading = title if len(pieces) == 1 else f"{title} [{i + 1}/{len(pieces)}]"
        rows.append({"source": source, "heading": heading, "text": piece, "words": words})
    return name, rows, len(body.split()), None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(GENERATED_DIR / "grounding.jsonl"))
    ap.add_argument("--chunk-words", type=int, default=220)
    ap.add_argument("--overlap", type=int, default=30)
    ap.add_argument("--min-words", type=int, default=60)
    ap.add_argument("--workers", type=int, default=8, help="concurrent downloads")
    ap.add_argument("--limit", type=int, default=0, help="cap total papers processed (0 = all); for smoke tests")
    ap.add_argument("--skip-extended", action="store_true", help="ingest only the original curated PAPERS list")
    args = ap.parse_args()

    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out)

    all_papers = list(PAPERS)
    if not args.skip_extended:
        all_papers += _load_extended()
    if args.limit:
        all_papers = all_papers[: args.limit]

    new_rows: list[dict] = []
    total_words = 0
    skipped = 0
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_process_one, name, title, url, args.chunk_words, args.overlap, args.min_words): name
            for name, title, url in all_papers
        }
        for fut in as_completed(futures):
            name, rows, words, err = fut.result()
            done += 1
            if err:
                skipped += 1
                print(f"  [{done}/{len(all_papers)}] SKIP {name}: {err}")
                continue
            new_rows.extend(rows)
            total_words += words
            print(f"  [{done}/{len(all_papers)}] {name}: {len(rows)} chunks ({words:,} words)")

    # merge: preserve non-paper grounding, replace prior paper:* rows
    existing = [r for r in read_jsonl(out_path) if not str(r.get("source", "")).startswith("paper:")] \
        if out_path.exists() else []
    merged = existing + new_rows
    write_jsonl(out_path, merged)

    print(
        f"\nWrote {len(new_rows)} paper chunks ({total_words:,} words) from "
        f"{len(all_papers) - skipped}/{len(all_papers)} papers ({skipped} skipped).\n"
        f"Grounding pool now {len(merged)} rows ({len(existing)} non-paper + {len(new_rows)} paper) -> {out_path}"
    )


if __name__ == "__main__":
    main()
