"""Experiment spec: the grid of cells a sweep runs.

JSON rather than YAML -- the repo has no yaml dependency and already uses JSON
for rosters. One cell is one ``(condition, seed)`` pair.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Agent.session_id and every scoped table are VARCHAR(32). A derived id that
# overflows would fail at insert time partway into a sweep, so it is checked
# before the first cell runs.
MAX_SESSION_ID = 32

Condition = Literal["neutral", "honesty", "deception"]


class SeedRange(BaseModel):
    start: int = 1
    count: int = Field(ge=1)

    def values(self) -> list[int]:
        return list(range(self.start, self.start + self.count))


class Budget(BaseModel):
    max_usd: float | None = None
    max_calls: int | None = None


class Cell(BaseModel):
    condition: str
    seed: int
    session_id: str
    natural_id: str
    trace_name: str


class ExperimentSpec(BaseModel):
    experiment: str = Field(min_length=1, max_length=64)
    roster: str
    conditions: list[Condition] = Field(min_length=1)
    seeds: SeedRange | list[int]
    turns: int = Field(ge=1)
    out: str
    concurrency: int = Field(default=2, ge=1)
    # Directory for recorded model decisions. Set it for any run you intend to
    # replay or publish: a decision not recorded during the run is unrecoverable.
    cache: str | None = None
    budget: Budget = Field(default_factory=Budget)

    @field_validator("seeds")
    @classmethod
    def _non_empty_seeds(cls, v: SeedRange | list[int]) -> SeedRange | list[int]:
        if isinstance(v, list) and not v:
            raise ValueError("seeds must not be empty")
        return v

    @model_validator(mode="after")
    def _ids_fit_the_column(self) -> ExperimentSpec:
        cells = self.cells()
        for cell in cells:
            if len(cell.session_id) > MAX_SESSION_ID:
                raise ValueError(
                    f"derived session_id {cell.session_id!r} exceeds {MAX_SESSION_ID} chars"
                )
        ids = {c.session_id for c in cells}
        if len(ids) != len(cells):
            raise ValueError("derived session ids collide; rename the experiment")
        return self

    def seed_values(self) -> list[int]:
        return self.seeds.values() if isinstance(self.seeds, SeedRange) else list(self.seeds)

    def cells(self) -> list[Cell]:
        out: list[Cell] = []
        for condition in self.conditions:
            for seed in self.seed_values():
                out.append(
                    Cell(
                        condition=condition,
                        seed=seed,
                        session_id=_derive_session_id(self.experiment, condition, seed),
                        natural_id=f"{self.experiment}:{condition}:{seed}",
                        trace_name=f"{condition}-s{seed}",
                    )
                )
        return out


def _derive_session_id(experiment: str, condition: str, seed: int) -> str:
    """Short, unique, and inside VARCHAR(32).

    Prefer a readable id; fall back to a hash of the natural id when the
    readable form would overflow, so a long experiment name degrades to
    something opaque rather than to a runtime failure. The hash covers the
    condition too, or two conditions of the same long-named experiment would
    collide on the same seed.
    """
    short = f"{experiment[:12]}:{condition[:3]}:{seed}"
    if len(short) <= MAX_SESSION_ID:
        return short
    natural = f"{experiment}:{condition}:{seed}"
    digest = hashlib.sha1(natural.encode("utf-8")).hexdigest()[:12]
    return f"x{digest}:{seed}"[:MAX_SESSION_ID]


def load_spec(path: Path) -> ExperimentSpec:
    return ExperimentSpec.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
