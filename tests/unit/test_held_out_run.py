from __future__ import annotations

import pytest

from tools import held_out_run


@pytest.mark.parametrize("name", ["../escape", "a/b", "a\\b", "..", "", "a:b"])
def test_trial_name_cannot_escape_the_output_directory(tmp_path, name):
    with pytest.raises(ValueError):
        held_out_run.run_target(tmp_path, name, "arpg")


def test_prior_projects_and_evidence_are_preserved(tmp_path):
    path = held_out_run.run_target(tmp_path, "unseen", "arpg")
    path.mkdir(parents=True)
    owned = path / "my-game.txt"
    owned.write_text("keep this")
    with pytest.raises(FileExistsError):
        held_out_run.run_target(tmp_path, "unseen", "arpg")
    assert owned.read_text() == "keep this"
    evidence = tmp_path / "unseen" / "turn_based.run.json"
    evidence.write_text('{"state": "analyzing"}')
    with pytest.raises(FileExistsError):
        held_out_run.run_target(tmp_path, "unseen", "turn_based")
