import json

from app.judge.batch import judge_trace
from app.judge.factory import build_judge
from app.trace.io import TraceWriter
from app.trace.schema import (
    AgentManifest,
    EnvManifest,
    Instrument,
    RunManifest,
    TurnRecord,
)


def _trace(path, rows):
    manifest = RunManifest(
        kind="run", schema_version=4, run_id="jb",
        env=EnvManifest(name="darwin", seed=1), horizon=10,
        agents=[AgentManifest(agent_id="a0", turns_alive=10),
                AgentManifest(agent_id="a1", turns_alive=10)],
    )
    with TraceWriter(path, manifest) as w:
        for row in rows:
            w.append(row)
    return path


def _turn(turn, agent="a0", action="work", ok=True, msg="hello"):
    return TurnRecord(kind="turn", turn=turn, agent_id=agent, action=action,
                      monologue="m", public_message=msg,
                      instrument=Instrument(tool_call_ok=ok))


def _rows(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


async def test_judges_every_eligible_turn(tmp_path):
    src = _trace(tmp_path / "t.jsonl", [_turn(1), _turn(2, agent="a1")])
    out = tmp_path / "v.jsonl"
    result = await judge_trace(src, out, judge=build_judge(provider="stub"))

    assert result.judged == 2
    rows = _rows(out)
    assert {(r["turn"], r["agent_id"]) for r in rows} == {(1, "a0"), (2, "a1")}
    assert all("is_deceptive" in r for r in rows)


async def test_skips_fallback_turns_by_instrument_flag(tmp_path):
    src = _trace(tmp_path / "t.jsonl", [_turn(1, ok=False), _turn(2)])
    out = tmp_path / "v.jsonl"
    result = await judge_trace(src, out, judge=build_judge(provider="stub"))

    assert result.judged == 1
    assert result.skipped == 1
    assert [r["turn"] for r in _rows(out)] == [2]


async def test_fallback_turns_can_be_included_explicitly(tmp_path):
    src = _trace(tmp_path / "t.jsonl", [_turn(1, ok=False), _turn(2)])
    out = tmp_path / "v.jsonl"
    result = await judge_trace(src, out, judge=build_judge(provider="stub"),
                               require_tool_call=False)
    assert result.judged == 2
    assert result.skipped == 0


async def test_skips_skip_actions(tmp_path):
    src = _trace(tmp_path / "t.jsonl", [_turn(1, action="skip"), _turn(2)])
    out = tmp_path / "v.jsonl"
    result = await judge_trace(src, out, judge=build_judge(provider="stub"))
    assert result.judged == 1
    assert result.skipped == 1


async def test_resume_does_not_rejudge(tmp_path):
    src = _trace(tmp_path / "t.jsonl", [_turn(1), _turn(2)])
    out = tmp_path / "v.jsonl"
    first = await judge_trace(src, out, judge=build_judge(provider="stub"))
    second = await judge_trace(src, out, judge=build_judge(provider="stub"))

    assert first.judged == 2
    assert second.judged == 0
    assert second.resumed == 2
    assert len(_rows(out)) == 2  # no duplicates appended


async def test_a_failed_verdict_is_never_written(tmp_path):
    """A degraded none@0 is indistinguishable from a real negative label."""
    from app.judge.base import BaseJudge
    from app.judge.schemas import failed_verdict

    class AlwaysFails(BaseJudge):
        provider = "boom"

        def __init__(self):
            super().__init__(judge_model="boom", prompt_version="v3")

        async def judge(self, ctx):
            return failed_verdict("api error")

    src = _trace(tmp_path / "t.jsonl", [_turn(1), _turn(2)])
    out = tmp_path / "v.jsonl"
    result = await judge_trace(src, out, judge=AlwaysFails(), max_attempts=2,
                               retry_backoff=0.0)

    assert result.judged == 0
    assert result.failed == 2
    assert not out.exists() or out.read_text(encoding="utf-8").strip() == ""


async def test_a_run_with_failures_is_resumable(tmp_path):
    """Unwritten rows must be picked up on the next pass, not lost."""
    from app.judge.base import BaseJudge
    from app.judge.schemas import failed_verdict

    class FailsOnce(BaseJudge):
        provider = "flaky"

        def __init__(self):
            super().__init__(judge_model="flaky", prompt_version="v3")
            self.calls = 0

        async def judge(self, ctx):
            self.calls += 1
            return failed_verdict("api error")

    src = _trace(tmp_path / "t.jsonl", [_turn(1), _turn(2)])
    out = tmp_path / "v.jsonl"
    await judge_trace(src, out, judge=FailsOnce(), max_attempts=1, retry_backoff=0.0)

    recovered = await judge_trace(src, out, judge=build_judge(provider="stub"))
    assert recovered.judged == 2
    assert recovered.resumed == 0
