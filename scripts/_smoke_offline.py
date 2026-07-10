"""Offline smoke test: imports, schema, and quality-gate logic (no network)."""

import _bootstrap  # noqa: F401

from sdx.schema import ANSWER_SECTIONS, SFTRecord, Scenario, DPORecord

# Import the private gate helpers from the filter script.
import importlib.util
import pathlib
spec = importlib.util.spec_from_file_location("qf", pathlib.Path(__file__).parent / "quality_filter.py")
qf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qf)

good = "\n".join(f"## {s}\nsome content here " * 1 for s in ANSWER_SECTIONS)
good_out = "\n".join(f"## {s}\n" + ("word " * 60) for s in ANSWER_SECTIONS)
rec_good = SFTRecord(id="1", instruction="Design a multi region inventory service with strong stock consistency", output=good_out, domain="ecommerce", scale="mid")
rec_bad_struct = SFTRecord(id="2", instruction="Design a multi region inventory service now please today", output="no headers here " * 100, domain="x", scale="y")
rec_bad_len = SFTRecord(id="3", instruction="Design a multi region inventory service with strong consistency", output=good_out[:50], domain="x", scale="y")

assert qf._structure_ok(good_out) is True, "structure_ok should pass ordered headers"
assert qf._structure_ok("## Data Model\n## Summary") is False, "out-of-order must fail"
assert qf._passes_gates(rec_good, 300, 1400) is True, "good record must pass"
assert qf._passes_gates(rec_bad_struct, 300, 1400) is False, "missing structure must fail"
assert qf._passes_gates(rec_bad_len, 300, 1400) is False, "too short must fail"

# heading-level robustness: ### must also be accepted
h3_out = "\n".join(f"### {s}\n" + ("word " * 60) for s in ANSWER_SECTIONS)
assert qf._structure_ok(h3_out) is True, "### headers must be accepted"
# missing one section must fail (e.g. the Data Model drop seen from the 3B teacher)
missing = "\n".join(f"## {s}\n" for s in ANSWER_SECTIONS if s != "Data Model")
assert qf._structure_ok(missing) is False, "missing a section must fail"

# schema round-trip
Scenario(id="a", domain="fintech", scale="mid-scale", prompt="p", topics=["caching"])
DPORecord(id="a", prompt="p", chosen="c", rejected="r")

print("OFFLINE SMOKE OK:", len(ANSWER_SECTIONS), "sections; gates + schema validated")
