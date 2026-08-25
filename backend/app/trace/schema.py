"""Trace schema v4 -- the portable contract between an environment and the judge.

A trace is JSONL: line 1 is a :class:`RunManifest`, every later line is a
:class:`TurnRecord`. Versions 2 and 3 exist in the wild and carry no manifest;
only v4 does, which is what makes a file self-describing. Legacy files are read
through ``app.trace.adapters``, never parsed directly by this module.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

TRACE_SCHEMA_VERSION = 5
SUPPORTED_SCHEMA_VERSIONS = (4, 5)

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


class WorldRecord(BaseModel):
    """Per-turn world state that belongs to no single agent.

    Registries live here rather than on agents because they are shared and
    checkable -- which is the point: a judge can decide a registry claim from a
    table instead of from a monologue. Empty until layer 2 ships.
    """

    kind: Literal["world"]
    turn: int
    contracts: list[dict] = Field(default_factory=list)
    offices: dict[str, str | None] = Field(default_factory=dict)
    prices: dict[str, float] = Field(default_factory=dict)
    info_market: list[dict] = Field(default_factory=list)


class RunManifest(BaseModel):
    kind: Literal["run"]
    schema_version: Literal[4, 5]
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


class DeferredEntry(BaseModel):
    kind: str
    amount: float
    maturity_turn: int
    target_id: str | None = None


class TurnState(BaseModel):
    """Everything needed to restore the agent's situation exactly.

    A field belongs here if restoring without it changes either an action's
    outcome distribution or the world brief the model is shown. ``steal_count``
    is the cautionary case: it drives steal success, was absent from v4, and
    every probe restored from a v4 trace therefore ran at 60% success where the
    real agent faced ~20%.
    """

    balance: float | None = None
    trust_score: float | None = None
    inventory: dict[str, int] | None = None
    alive: list[str] | None = None
    spouse_id: str | None = None
    steal_count: int | None = None
    allies: list[str] | None = None
    enemies: list[str] | None = None
    skip_next_turn: bool | None = None
    rest_bonus: bool | None = None
    share_balance: bool | None = None
    will_target: str | None = None
    marriage_pending: str | None = None
    extortion_pending: dict | None = None
    bribe_pending: dict | None = None
    deferred: list[DeferredEntry] | None = None
    # Reserved for later phases: carried by the schema so no second migration
    # is needed, null until their layer ships.
    office: str | None = None
    tier: str | None = None
    capacity: dict[str, int] | None = None


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


Record = Annotated[RunManifest | TurnRecord | WorldRecord, Field(discriminator="kind")]
_ADAPTER: TypeAdapter[Record] = TypeAdapter(Record)


def parse_record(raw: dict) -> RunManifest | TurnRecord | WorldRecord:
    """Parse one trace line. Raises ``ValidationError`` -- callers decide policy."""
    return _ADAPTER.validate_python(raw)
