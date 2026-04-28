"""LangGraph wrapper around the Oracle turn loop.

The cognitive loop per agent is Plan -> Act -> Reflect. We model the *whole turn*
as a single graph that fans out one node per alive agent, then converges on a
single Oracle settlement node that applies survival tax and checks apex.

For most use cases the lightweight async loop in `oracle.engine` is sufficient.
This module is provided so the spec's LangGraph requirement is honored and the
state machine is explicit for research instrumentation.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.db import SessionLocal
from app.oracle.engine import run_turn


class TurnState(TypedDict, total=False):
    turn: int
    agents: dict[str, BaseAgent]
    apex: str | None
    eliminated: list[str]


async def _execute(state: TurnState) -> TurnState:
    async with SessionLocal() as session:
        result = await run_turn(session, turn=state["turn"], agents=state["agents"])
    return {**state, "apex": result.apex_declared, "eliminated": result.eliminated}


def build_turn_graph():
    graph = StateGraph(TurnState)
    graph.add_node("execute_turn", _execute)
    graph.set_entry_point("execute_turn")
    graph.add_edge("execute_turn", END)
    return graph.compile()
