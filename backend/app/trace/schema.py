"""Trace schema v4 -- the portable contract between an environment and the judge.

A trace is JSONL: line 1 is a :class:`RunManifest`, every later line is a
:class:`TurnRecord`. Versions 2 and 3 exist in the wild and carry no manifest;
only v4 does, which is what makes a file self-describing. Legacy files are read
through ``app.trace.adapters``, never parsed directly by this module.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

TRACE_SCHEMA_VERSION = 4

StateFidelity = Literal["full", "partial"]


class EnvManifest(BaseModel):
    name: str
    version: str = ""
    seed: int = 0
    actions: int | None = None


class AgentManifest(BaseModel):
    agent_id: str
    model: str = ""
    provider: str = ""
    specialty: str = ""
    persona: str | None = None
    turns_alive: int
    eliminated_at_turn: int | None = None
    outcome: str = ""


class RunManifest(BaseModel):
    kind: Literal["run"]
    schema_version: Literal[4]
    run_id: str
    env: EnvManifest
    condition: str = "neutral"
    horizon: int
    state_fidelity: StateFidelity = "full"
    agents: list[AgentManifest]

    def lifespans(self) -> dict[str, int]:
        return {a.agent_id: a.turns_alive for a in self.agents}

    def models(self) -> dict[str, str]:
        return {a.agent_id: a.model for a in self.agents}


class TurnState(BaseModel):
    balance: float | None = None
    trust_score: float | None = None
    inventory: dict[str, int] | None = None
    alive: list[str] | None = None
    spouse_id: str | None = None


class Instrument(BaseModel):
    tool_call_ok: bool = True
    note: str = ""


class TurnRecord(BaseModel):
    kind: Literal["turn"]
    turn: int
    agent_id: str
    monologue: str = ""
    public_message: str = ""
    action: str
    arguments: dict = Field(default_factory=dict)
    outcome: str = ""
    state: TurnState = Field(default_factory=TurnState)
    instrument: Instrument = Field(default_factory=Instrument)


Record = Annotated[RunManifest | TurnRecord, Field(discriminator="kind")]
_ADAPTER: TypeAdapter[Record] = TypeAdapter(Record)


def parse_record(raw: dict) -> RunManifest | TurnRecord:
    """Parse one trace line. Raises ``ValidationError`` -- callers decide policy."""
    return _ADAPTER.validate_python(raw)
