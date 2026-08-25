"""The cache is what makes 'reproducible' falsifiable rather than aspirational."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.base import AgentDecision, BaseAgent
from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.models.agent import Agent
from app.replay.cache import (
    CacheMiss,
    EnvVersionMismatch,
    ResponseCache,
    decision_key,
)
from app.replay.cached_agent import CachedAgent

ENV = "darwin-1.0"


class Recording(BaseAgent):
    """Stands in for a live model; counts how often it was actually asked."""

    def __init__(self, agent_id="a0", action="work"):
        self.agent_id = agent_id
        self.model = "stub/model"
        self._action = action
        self.calls = 0

    async def decide(self, state, agent) -> AgentDecision:
        self.calls += 1
        return AgentDecision(action=self._action, arguments={"n": self.calls},
                             monologue="live")


def _agent(agent_id="a0") -> Agent:
    return Agent(session_id="s", agent_id=agent_id, display_name=agent_id.upper(),
                 provider="stub", model="stub/model", personality="x", sprite="blue",
                 balance=10.0, alive=True, allies=[], enemies=[], inventory={})


def _state(turn=1, balance=10.0) -> dict:
    return {
        "turn": turn,
        "_condition": "neutral",
        "agents": [
            {"agent_id": "a0", "display_name": "A0", "balance": balance, "alive": True,
             "spouse": None, "allies": [], "enemies": [], "skip_next_turn": False,
             "trust_score": 50.0, "steal_count": 0, "share_balance": True,
             "inventory": {}, "specialty": "ore", "rest_bonus": False,
             "will_target": None, "extortion_pending": None, "bribe_pending": None},
        ],
    }


def _kwargs(**over):
    base = dict(env_version=ENV, model="m", prompt_version="v3", system_prompt="sys",
                user_prompt="usr", tool_names=["work"], temperature=0.0)
    base.update(over)
    return base


def test_key_is_stable_across_processes():
    """hash() is randomised per process; a replay key must not be."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    code = (
        "from app.replay.cache import decision_key;"
        "print(decision_key(env_version='e', model='m', prompt_version='v3',"
        " system_prompt='s', user_prompt='u', tool_names=['work'], temperature=0.0))"
    )
    root = str(Path(__file__).resolve().parents[1])
    seen = set()
    for seed in (0, 1, 2):
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                              text=True, cwd=root,
                              env=dict(os.environ, PYTHONHASHSEED=str(seed)))
        assert proc.returncode == 0, proc.stderr
        seen.add(proc.stdout.strip())
    assert len(seen) == 1


def test_a_different_world_yields_a_different_key():
    """The prompts encode world state, which is what makes the key correct."""
    assert decision_key(**_kwargs()) != decision_key(**_kwargs(user_prompt="different"))


def test_env_version_is_part_of_the_key():
    assert decision_key(**_kwargs()) != decision_key(**_kwargs(env_version="darwin-2.0"))


def test_put_then_get_round_trips(tmp_path):
    cache = ResponseCache(tmp_path, env_version=ENV)
    key = decision_key(**_kwargs())
    cache.put(key, {"action": "work", "arguments": {}})
    assert cache.get(key)["action"] == "work"
    assert cache.stats().hits == 1


def test_missing_key_returns_none_and_counts(tmp_path):
    cache = ResponseCache(tmp_path, env_version=ENV)
    assert cache.get("deadbeef") is None
    assert cache.stats().misses == 1


def test_env_version_mismatch_raises_rather_than_serving(tmp_path):
    """Serving a stale entry would silently mix two environments in one run."""
    recorded = ResponseCache(tmp_path, env_version="darwin-1.0")
    key = decision_key(**_kwargs())
    recorded.put(key, {"action": "work", "arguments": {}})

    replaying = ResponseCache(tmp_path, env_version="darwin-2.0")
    with pytest.raises(EnvVersionMismatch):
        replaying.get(key)


async def test_permissive_records_then_strict_replays(tmp_path):
    cache = ResponseCache(tmp_path, env_version=ENV)
    live = Recording()
    agent, state = _agent(), _state()

    recorder = CachedAgent("a0", cache=cache, inner=live, mode="permissive",
                           prompt_version="v3")
    first = await recorder.decide(state, agent)
    assert live.calls == 1

    replayer = CachedAgent("a0", cache=ResponseCache(tmp_path, env_version=ENV),
                           inner=None, mode="strict", model="stub/model",
                           prompt_version="v3")
    second = await replayer.decide(state, agent)

    assert live.calls == 1, "strict replay must not reach the live agent"
    assert (second.action, second.arguments, second.monologue) == (
        first.action, first.arguments, first.monologue
    )


async def test_strict_mode_raises_on_a_miss(tmp_path):
    """A miss must fail loudly, or a reproduction quietly becomes a fresh run."""
    replayer = CachedAgent("a0", cache=ResponseCache(tmp_path, env_version=ENV),
                           inner=Recording(), mode="strict", model="stub/model",
                           prompt_version="v3")
    with pytest.raises(CacheMiss):
        await replayer.decide(_state(), _agent())


async def test_a_changed_world_misses_rather_than_serving_the_wrong_turn(tmp_path):
    cache = ResponseCache(tmp_path, env_version=ENV)
    recorder = CachedAgent("a0", cache=cache, inner=Recording(), mode="permissive",
                           prompt_version="v3")
    await recorder.decide(_state(turn=1, balance=10.0), _agent())

    strict = CachedAgent("a0", cache=ResponseCache(tmp_path, env_version=ENV),
                         inner=None, mode="strict", model="stub/model",
                         prompt_version="v3")
    with pytest.raises(CacheMiss):
        await strict.decide(_state(turn=1, balance=99.0), _agent())


async def test_free_actions_survive_the_round_trip(tmp_path):
    class WithFree(BaseAgent):
        def __init__(self):
            self.agent_id = "a0"
            self.model = "stub/model"

        async def decide(self, state, agent):
            return AgentDecision(action="work", arguments={}, monologue="m",
                                 free_action="vouch", free_arguments={"target": "a1"})

    cache = ResponseCache(tmp_path, env_version=ENV)
    await CachedAgent("a0", cache=cache, inner=WithFree(), mode="permissive",
                      prompt_version="v3").decide(_state(), _agent())

    replayed = await CachedAgent(
        "a0", cache=ResponseCache(tmp_path, env_version=ENV), inner=None,
        mode="strict", model="stub/model", prompt_version="v3",
    ).decide(_state(), _agent())

    assert replayed.free_action == "vouch"
    assert replayed.free_arguments == {"target": "a1"}


async def test_a_full_run_replays_identically(tmp_path):
    """The claim in miniature: same engine, recorded decisions, same trace."""
    from app.agents.factory import build_agents
    from app.oracle.engine import run_turn, seed_roster
    from app.trace.adapters.darwin_db import export_session

    roster = [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(3)
    ]

    async def _run(session_id, agents_factory):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            await seed_roster(session, session_id, roster, seed=5)
            agents = agents_factory()
            for turn in range(1, 7):
                await run_turn(session, session_id=session_id, turn=turn,
                               agents=agents, seed=5)
            _, records, _ = await export_session(session, session_id, seed=5)
        await engine.dispose()
        return [(r.turn, r.agent_id, r.action, r.outcome) for r in records]

    cache = ResponseCache(tmp_path, env_version=ENV)
    live = build_agents(roster=roster)
    recorded = await _run("rec", lambda: {
        aid: CachedAgent(aid, cache=cache, inner=inner, mode="permissive",
                         model="stub/model", prompt_version="v3")
        for aid, inner in live.items()
    })

    replay_cache = ResponseCache(tmp_path, env_version=ENV)
    replayed = await _run("rep", lambda: {
        aid: CachedAgent(aid, cache=replay_cache, inner=None, mode="strict",
                         model="stub/model", prompt_version="v3")
        for aid in live
    })

    assert recorded == replayed
    assert replay_cache.stats().misses == 0
