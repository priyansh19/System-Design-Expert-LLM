"""Aggregate judge scores into a per-dimension comparison table across systems.

Usage:
    python eval/report.py                        # eval/scores/*.jsonl -> eval/report.md + stdout
    python eval/report.py --scores eval/scores/teacher-grounded.jsonl eval/scores/base-bare.jsonl
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import glob
from collections import defaultdict
from pathlib import Path

from judge import RUBRIC

from sdx.corpus import read_jsonl


def _aggregate(paths: list[Path]) -> dict[str, dict[str, float]]:
    per_system: dict[str, list[dict]] = defaultdict(list)
    for path in paths:
        for row in read_jsonl(path):
            per_system[row["system"]].append(row)

    table: dict[str, dict[str, float]] = {}
    for system, rows in per_system.items():
        dims = {d: sum(r["scores"][d] for r in rows) / len(rows) for d in RUBRIC}
        dims["overall"] = sum(r["mean"] for r in rows) / len(rows)
        dims["n"] = float(len(rows))
        table[system] = dims
    return table


def _render_markdown(table: dict[str, dict[str, float]]) -> str:
    cols = RUBRIC + ["overall", "n"]
    header = "| system | " + " | ".join(cols) + " |"
    sep = "|---" * (len(cols) + 1) + "|"
    lines = [header, sep]
    for system in sorted(table, key=lambda s: -table[s]["overall"]):
        row = table[system]
        cells = [str(int(row[c])) if c == "n" else f"{row[c]:.2f}" for c in cols]
        lines.append(f"| {system} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _resolve_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matched = glob.glob(pattern)
        if matched:
            paths.extend(Path(p) for p in matched)
        elif Path(pattern).exists():
            paths.append(Path(pattern))
    return sorted(set(paths))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", nargs="+", default=["eval/scores/*.jsonl"])
    ap.add_argument("--out", default="eval/report.md")
    args = ap.parse_args()

    paths = _resolve_paths(args.scores)
    if not paths:
        raise SystemExit(f"No score files matched {args.scores}")

    table = _aggregate(paths)
    md = _render_markdown(table)
    Path(args.out).write_text(md + "\n", encoding="utf-8")
    print(md)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
