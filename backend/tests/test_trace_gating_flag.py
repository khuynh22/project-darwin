"""A trace says which rules it was recorded under, and replay believes it."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.trace.schema import RunManifest

BASE = {
    "kind": "run",
    "schema_version": 6,
    "run_id": "r1",
    "env": {"name": "darwin"},
    "horizon": 10,
    "agents": [],
}


def test_an_older_manifest_without_the_field_still_parses():
    manifest = RunManifest.model_validate(BASE)

    assert manifest.venue_gating is False


def test_the_flag_round_trips():
    manifest = RunManifest.model_validate({**BASE, "venue_gating": True})

    assert manifest.venue_gating is True
    assert manifest.model_dump(mode="json")["venue_gating"] is True


def test_a_non_boolean_flag_is_a_validation_error():
    with pytest.raises(ValidationError):
        RunManifest.model_validate({**BASE, "venue_gating": "maybe"})
