import json

import pytest
from pydantic import ValidationError

from app.sweep.spec import MAX_SESSION_ID, ExperimentSpec, load_spec


def _spec(**over) -> dict:
    base = {
        "experiment": "cond-contrast",
        "roster": "rosters/cheap8.json",
        "conditions": ["neutral", "honesty"],
        "seeds": {"start": 1, "count": 3},
        "turns": 20,
        "out": "runs/cond-contrast",
    }
    base.update(over)
    return base


def test_cells_are_the_condition_seed_product():
    spec = ExperimentSpec.model_validate(_spec())
    cells = spec.cells()
    assert len(cells) == 6
    assert {c.condition for c in cells} == {"neutral", "honesty"}
    assert sorted({c.seed for c in cells}) == [1, 2, 3]


def test_explicit_seed_list_is_honoured():
    spec = ExperimentSpec.model_validate(_spec(seeds=[7, 9]))
    assert sorted({c.seed for c in spec.cells()}) == [7, 9]


def test_session_ids_are_unique_and_within_the_column_limit():
    spec = ExperimentSpec.model_validate(_spec())
    ids = [c.session_id for c in spec.cells()]
    assert len(set(ids)) == len(ids)
    assert all(len(i) <= MAX_SESSION_ID for i in ids)


def test_long_experiment_name_still_fits():
    spec = ExperimentSpec.model_validate(
        _spec(experiment="a-very-long-experiment-name-indeed-2026", seeds=[123456])
    )
    for cell in spec.cells():
        assert len(cell.session_id) <= MAX_SESSION_ID
        assert cell.natural_id.startswith("a-very-long-experiment-name")


def test_long_name_cells_stay_unique():
    spec = ExperimentSpec.model_validate(
        _spec(experiment="a-very-long-experiment-name-indeed-2026",
              conditions=["neutral", "honesty", "deception"],
              seeds={"start": 1, "count": 5})
    )
    ids = [c.session_id for c in spec.cells()]
    assert len(set(ids)) == len(ids)


def test_unknown_condition_rejected():
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate(_spec(conditions=["neutral", "nonsense"]))


def test_zero_seeds_rejected():
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate(_spec(seeds={"start": 1, "count": 0}))


def test_empty_seed_list_rejected():
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate(_spec(seeds=[]))


def test_trace_names_are_filesystem_safe_and_unique():
    spec = ExperimentSpec.model_validate(_spec())
    names = [c.trace_name for c in spec.cells()]
    assert len(set(names)) == len(names)
    assert all(":" not in n for n in names)


def test_load_spec_reads_json(tmp_path):
    path = tmp_path / "exp.json"
    path.write_text(json.dumps(_spec()), encoding="utf-8")
    spec = load_spec(path)
    assert spec.experiment == "cond-contrast"
    assert spec.turns == 20
