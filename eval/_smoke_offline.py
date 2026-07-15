"""Offline smoke test for eval/: rubric, bias-control guard, report aggregation
(no network calls -- LLM-as-judge scoring itself needs a live provider)."""

import _bootstrap  # noqa: F401

import tempfile
from pathlib import Path

import generate
import judge
import report
from gen_answers import SYSTEM as _GEN_ANSWERS_SYSTEM

from sdx.corpus import write_jsonl

# --- rubric shape ---
assert judge.RUBRIC == ["correctness", "tradeoff_depth", "completeness", "feasibility", "clarity"], (
    "rubric must match the 5 design-spec dimensions"
)

# --- bias control: judge family must differ from teacher family ---
assert judge._same_family("ornith", "ollama") is True, "local Ollama providers share one family"
assert judge._same_family("ornith", "finetune") is True, "our own fine-tune is still the local family"
assert judge._same_family("ornith", "openai") is False, "openai is a different family"
assert judge._same_family("ornith", "nvidia") is False, "nvidia (Llama judge model) is a different family"
assert judge._same_family("openai", "openai") is True, "identical provider is always same-family"

# --- inference-mode persona parity: bare mode must mirror the production system prompt ---
assert generate._BARE_SYSTEM == _GEN_ANSWERS_SYSTEM, (
    "bare-mode eval persona has drifted from gen_answers.py's production SYSTEM prompt"
)

# --- report aggregation + markdown rendering ---
with tempfile.TemporaryDirectory() as td:
    tdp = Path(td)
    rows_a = [
        {"id": "1", "system": "sys-a", "scores": {d: 8 for d in judge.RUBRIC}, "mean": 8.0, "notes": ""},
        {"id": "2", "system": "sys-a", "scores": {d: 6 for d in judge.RUBRIC}, "mean": 6.0, "notes": ""},
    ]
    rows_b = [
        {"id": "3", "system": "sys-b", "scores": {d: 4 for d in judge.RUBRIC}, "mean": 4.0, "notes": ""},
    ]
    write_jsonl(tdp / "sys-a.jsonl", rows_a)
    write_jsonl(tdp / "sys-b.jsonl", rows_b)

    paths = report._resolve_paths([str(tdp / "*.jsonl")])
    assert len(paths) == 2, "both score files must be discovered"

    table = report._aggregate(paths)
    assert table["sys-a"]["overall"] == 7.0, f"sys-a mean of [8,6] should be 7.0, got {table['sys-a']['overall']}"
    assert table["sys-a"]["n"] == 2.0
    assert table["sys-b"]["overall"] == 4.0
    assert table["sys-a"]["correctness"] == 7.0

    md = report._render_markdown(table)
    lines = md.splitlines()
    assert lines[0].startswith("| system |"), "header row missing"
    # higher-overall system must be ranked first
    assert "sys-a" in lines[2] and "sys-b" in lines[3], "systems must be sorted by descending overall score"

print("EVAL OFFLINE SMOKE OK: rubric, bias-control guard, persona parity, report aggregation validated")
