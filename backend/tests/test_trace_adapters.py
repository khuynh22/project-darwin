import json

from app.trace.adapters.legacy_jsonl import is_fallback, upgrade_legacy_jsonl


def _write_legacy(tmp_path, rows):
    path = tmp_path / "legacy.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def test_is_fallback_detects_both_markers():
    assert is_fallback("model returned no tool call") is True
    assert is_fallback("falling back to work") is True
    assert is_fallback("I will work to build capital") is False
    assert is_fallback(None) is False


def test_upgrade_builds_manifest_with_lifespans(tmp_path):
    src = _write_legacy(tmp_path, [
        {"schema_version": 2, "turn": 1, "agent_id": "opus", "monologue": "a",
         "public_message": "", "action": "work", "arguments": {}, "outcome": "ok"},
        {"schema_version": 2, "turn": 5, "agent_id": "opus", "monologue": "b",
         "public_message": "", "action": "work", "arguments": {}, "outcome": "ok"},
        {"schema_version": 2, "turn": 2, "agent_id": "grok", "monologue": "c",
         "public_message": "", "action": "steal", "arguments": {}, "outcome": "ok"},
    ])
    manifest, turns = upgrade_legacy_jsonl(
        src, run_id="r1", models={"opus": "anthropic/claude-opus-4.7", "grok": "x-ai/grok-4.3"}
    )
    assert manifest.schema_version == 4
    assert manifest.horizon == 5
    assert manifest.lifespans() == {"opus": 5, "grok": 2}
    assert manifest.models()["grok"] == "x-ai/grok-4.3"
    assert manifest.state_fidelity == "partial"
    assert len(turns) == 3


def test_upgrade_marks_fallback_turns(tmp_path):
    src = _write_legacy(tmp_path, [
        {"schema_version": 2, "turn": 1, "agent_id": "kimi",
         "monologue": "no tool call returned, falling back", "action": "work",
         "arguments": {}, "outcome": ""},
        {"schema_version": 2, "turn": 2, "agent_id": "kimi", "monologue": "trade now",
         "action": "trade", "arguments": {}, "outcome": "ok"},
    ])
    _, turns = upgrade_legacy_jsonl(src, run_id="r1", models={"kimi": "moonshotai/kimi-k2.6"})
    assert turns[0].instrument.tool_call_ok is False
    assert turns[1].instrument.tool_call_ok is True


def test_upgrade_drops_excluded_agents(tmp_path):
    src = _write_legacy(tmp_path, [
        {"schema_version": 2, "turn": 1, "agent_id": "kimi", "monologue": "x",
         "action": "work", "arguments": {}, "outcome": ""},
        {"schema_version": 2, "turn": 1, "agent_id": "opus", "monologue": "y",
         "action": "work", "arguments": {}, "outcome": ""},
    ])
    manifest, turns = upgrade_legacy_jsonl(
        src, run_id="r1", models={"opus": "m"}, exclude={"kimi"}
    )
    assert [t.agent_id for t in turns] == ["opus"]
    assert "kimi" not in manifest.lifespans()


def test_upgraded_trace_passes_validation(tmp_path):
    from app.trace.io import TraceWriter
    from app.trace.validate import validate_trace

    src = _write_legacy(tmp_path, [
        {"schema_version": 2, "turn": 1, "agent_id": "opus", "monologue": "a",
         "action": "work", "arguments": {}, "outcome": "ok"},
        {"schema_version": 2, "turn": 2, "agent_id": "grok", "monologue": "b",
         "action": "slander", "arguments": {"target": "opus"}, "outcome": "ok"},
    ])
    manifest, turns = upgrade_legacy_jsonl(src, run_id="r1", models={})
    out = tmp_path / "v4.jsonl"
    with TraceWriter(out, manifest) as w:
        for turn in turns:
            w.append(turn)

    report = validate_trace(out)
    assert report.ok, report.errors
    assert report.n_turns == 2
