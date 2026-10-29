from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import answer_key


def test_fitting_draft_only_corpus_cannot_replace_the_shipped_table(tmp_path, monkeypatch):
    from rpggen import analyze_cmd
    from rpggen.core import calibration

    monkeypatch.setenv("RPGGEN_CALIBRATION", "off")
    table = tmp_path / "table.json"
    table.write_text('{"keep": true}')
    monkeypatch.setattr(calibration, "TABLE", table)
    monkeypatch.setattr(answer_key, "load_packs", lambda _: [])
    monkeypatch.setattr(
        analyze_cmd,
        "run_private_corpus",
        lambda *_: {
            "packs": {
                "draft": {
                    "pictures": [{"right": True, "calibration_eligible": False}],
                    "review_coverage": {"calibration_eligible": 0},
                }
            },
            "missing": [],
        },
    )
    with pytest.raises(ValueError, match="no independently supported bins"):
        answer_key.fit(tmp_path, True)
    assert table.read_text() == '{"keep": true}'
    assert "No calibration-eligible observations" in (tmp_path / "fit_report.md").read_text()


@pytest.mark.parametrize("held_out_right", [True, False])
def test_table_publication_requires_held_out_source_support(tmp_path, monkeypatch, held_out_right):
    from rpggen import analyze_cmd
    from rpggen.core import calibration

    monkeypatch.setenv("RPGGEN_CALIBRATION", "off")
    table = tmp_path / "table.json"
    table.write_text('{"keep": true}')
    monkeypatch.setattr(calibration, "TABLE", table)
    monkeypatch.setattr(answer_key, "load_packs", lambda _: [])
    packs = {}
    for name in ["a", "b"]:
        rows = [
            {
                "reader": "grid",
                "role": "GROUND",
                "confidence": 0.5,
                "sure": False,
                "right": held_out_right or name == "a",
                "source_sha256": f"{name}:{i}",
                "calibration_eligible": True,
            }
            for i in range(500)
        ]
        packs[name] = {"pictures": rows, "review_coverage": {"calibration_eligible": 500}}
    monkeypatch.setattr(
        analyze_cmd, "run_private_corpus", lambda *_: {"packs": packs, "missing": []}
    )
    if held_out_right:
        answer_key.fit(tmp_path, True)
        published = json.loads(table.read_text())
        assert published["version"] == calibration.VERSION
        assert all("|*|" not in key for key in published["bins"]), (
            "untested generic sure bins are removed"
        )
    else:
        with pytest.raises(ValueError, match="99% support"):
            answer_key.fit(tmp_path, True)
        assert table.read_text() == '{"keep": true}'


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
