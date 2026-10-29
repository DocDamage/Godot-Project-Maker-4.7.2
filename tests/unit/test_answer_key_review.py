from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import answer_key


@pytest.fixture
def review(tmp_path: Path) -> Path:
    (tmp_path / "review_queue.json").write_text(
        json.dumps({"questions": [{"id": "H1", "choices": ["Crop", "Item"]}]})
    )
    (tmp_path / "marks").mkdir()
    (tmp_path / "marks" / "pack.json").write_text('{"group": {"mark": "mixed"}}')
    return tmp_path


def test_decision_round_trip_preserves_other_choices_and_original_marks(review: Path) -> None:
    original = (review / "marks" / "pack.json").read_bytes()
    (review / "review_decisions.json").write_text('{"other": {"choice": "Keep"}}')
    answer_key.save_review_decision(review, {"id": "H1", "choice": "Crop", "note": "For my farm"})
    saved = answer_key.review_data(review)["decisions"]
    assert saved == {
        "H1": {"choice": "Crop", "note": "For my farm"},
        "other": {"choice": "Keep"},
    }
    assert (review / "marks" / "pack.json").read_bytes() == original


@pytest.mark.parametrize(
    "data",
    [
        {"id": "missing", "choice": "Crop"},
        {"id": "H1", "choice": "Unlisted"},
        {"id": "H1", "choice": "Crop", "note": ["not text"]},
        {"id": "H1", "choice": "Crop", "note": "x" * 2001},
    ],
)
def test_invalid_decision_cannot_create_marks(review: Path, data: dict) -> None:
    with pytest.raises(ValueError):
        answer_key.save_review_decision(review, data)
    assert not (review / "review_decisions.json").exists()
    assert not (review / "review_decision_history.json").exists()


def test_changed_choice_preserves_previous_answer_and_note(review: Path) -> None:
    first = {"id": "H1", "choice": "Crop", "note": "Fruit trees"}
    answer_key.save_review_decision(review, first)
    answer_key.save_review_decision(review, {"id": "H1", "choice": "Item"})
    history = json.loads((review / "review_decision_history.json").read_text())
    assert history[-1] == {
        "id": "H1",
        "before": {"choice": "Crop", "note": "Fruit trees"},
        "after": {"choice": "Item", "note": ""},
    }
    answer_key.save_review_decision(review, {"id": "H1", "choice": "Item"})
    assert json.loads((review / "review_decision_history.json").read_text()) == history
