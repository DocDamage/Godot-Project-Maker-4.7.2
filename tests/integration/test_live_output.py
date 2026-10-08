"""T12.19 with real Godot: every Godot phase of a generation reports its progress."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import config, orchestrator

pytestmark = pytest.mark.integration

PACK = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic" / "basic16"


def test_every_godot_phase_has_a_moving_sub_line(godot_exe: Path, tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    config.save(orchestrator.default_config_for_pack(PACK, "Live"), cfg_path)
    steps: list[tuple[str, int, int, str]] = []
    logs: list[str] = []
    phases: list[str] = []
    callbacks = orchestrator.Callbacks(
        on_phase=lambda name, i, n: phases.append(name),
        on_log=logs.append,
        on_step=lambda *a: steps.append(a),
    )
    result = orchestrator.run(cfg_path, tmp_path / "out", godot_exe, callbacks)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]

    def of(phase: str) -> list[tuple[str, int, int, str]]:
        return [s for s in steps if s[0] == phase]

    build = of("build")
    assert len(build) >= 15 and [s[1] for s in build] == list(range(1, len(build) + 1))
    assert all(s[2] == len(build) and s[3] for s in build)  # i of n with a label
    validate = of("validate")
    assert [s[1] for s in validate] == list(range(1, 13)) and validate[0][3] == "scripts"
    assert of("import"), "the import has no protocol: its last line stands in"
    assert all(s[2] == 0 for s in of("import"))
    assert of("smoke"), "the smoke test prints lines too"
    # the protocol lines are not log lines, and Godot's own lines carry the prefix
    assert not any("@rpggen step" in text for text in logs)
    assert any(text.startswith("[godot] ") for text in logs)
    assert phases.index("import") < phases.index("build") < phases.index("validate")
    log_file = result.target / "rpggen" / "logs" / "godot_build.log"
    assert not log_file.exists() or "@rpggen step build" in log_file.read_text(encoding="utf-8")
