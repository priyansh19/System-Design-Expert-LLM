"""Data schemas for the synthetic pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Fixed answer structure the teacher must follow (also enforced at filter time).
ANSWER_SECTIONS = [
    "Requirements & Assumptions",
    "High-Level Architecture",
    "Component Choices & Tradeoffs",
    "Data Model",
    "Scaling & Failure Modes",
    "Bottlenecks & Next Steps",
]


class Scenario(BaseModel):
    """A realistic system-design requirement to be answered."""

    id: str
    domain: str          # e.g. "fintech", "social", "iot", "ecommerce"
    scale: str           # e.g. "startup", "mid", "hyperscale"
    prompt: str          # the requirement stated as a user would ask it
    topics: list[str] = Field(default_factory=list)  # seed-corpus topic slugs referenced


class SFTRecord(BaseModel):
    """One instruction -> answer training example."""

    id: str
    instruction: str
    output: str
    domain: str
    scale: str
    topics: list[str] = Field(default_factory=list)
    retrieved_refs: list[str] = Field(default_factory=list)  # grounding chunk ids used, for audit


class DPORecord(BaseModel):
    """One preference pair."""

    id: str
    prompt: str
    chosen: str
    rejected: str
