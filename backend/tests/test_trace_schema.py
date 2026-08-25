import pytest
from pydantic import ValidationError

from app.trace.schema import (
    TRACE_SCHEMA_VERSION,
    RunManifest,
    TurnRecord,
    parse_record,
)


def _manifest_dict() -> dict:
    return {
        "kind": "run",
        "schema_version": 5,
        "run_id": "demo",
        "env": {"name": "darwin", "version": "abc123", "seed": 7, "actions": 20},
        "condition": "neutral",
        "horizon": 2,
        "state_fidelity": "full",
        "agents": [
            {
                "agent_id": "opus",
                "model": "anthropic/claude-opus-4.7",
                "provider": "openrouter",
                "specialty": "food",
                "turns_alive": 2,
                "eliminated_at_turn": None,
                "outcome": "survived",
            }
        ],
    }


def _turn_dict() -> dict:
    return {
        "kind": "turn",
        "turn": 1,
        "agent_id": "opus",
        "monologue": "build capital",
        "public_message": "hello",
        "action": "work",
        "arguments": {},
        "outcome": "earned $0.15 + 3 ore [ok]",
        "state": {"balance": 10.0, "trust_score": 50.0, "alive": ["opus"]},
        "instrument": {"tool_call_ok": True},
    }


def test_schema_version_is_five():
    assert TRACE_SCHEMA_VERSION == 5


def test_parse_record_discriminates_on_kind():
    assert isinstance(parse_record(_manifest_dict()), RunManifest)
    assert isinstance(parse_record(_turn_dict()), TurnRecord)


def test_turns_alive_is_mandatory():
    bad = _manifest_dict()
    del bad["agents"][0]["turns_alive"]
    with pytest.raises(ValidationError):
        parse_record(bad)


def test_v4_manifests_still_parse():
    """v4 files are released artifacts; they must keep loading."""
    older = _manifest_dict()
    older["schema_version"] = 4
    assert parse_record(older).schema_version == 4


def test_manifest_rejects_legacy_versions():
    for legacy in (2, 3):
        bad = _manifest_dict()
        bad["schema_version"] = legacy
        with pytest.raises(ValidationError):
            parse_record(bad)


def test_turn_defaults_are_permissive():
    minimal = {"kind": "turn", "turn": 1, "agent_id": "opus", "action": "work"}
    rec = parse_record(minimal)
    assert rec.monologue == ""
    assert rec.arguments == {}
    assert rec.instrument.tool_call_ok is True


def test_unknown_kind_raises():
    with pytest.raises(ValidationError):
        parse_record({"kind": "nonsense"})


def test_manifest_helpers_expose_lifespans_and_models():
    manifest = parse_record(_manifest_dict())
    assert manifest.lifespans() == {"opus": 2}
    assert manifest.models() == {"opus": "anthropic/claude-opus-4.7"}
