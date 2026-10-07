from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import export_check, godot, orchestrator

pytestmark = pytest.mark.integration


def test_generated_project_exports(godot_exe: Path, tmp_path: Path) -> None:
    version = godot.detect_version(godot_exe)
    if not export_check.templates_installed(version):
        pytest.skip("export templates are not installed")
    target = tmp_path / "game"
    cfg = orchestrator.default_config_for_pack(paths.sample_pack_root(), "Export Game")
    result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert result.ok, [i.code for i in result.issues]
    assert (target / "export_presets.cfg").is_file()
    assert "ENV-010" not in {i.code for i in result.issues}
    assert (target / "rpggen/logs/godot_export.log").is_file()
    assert not list(target.rglob("test.exe"))  # the check deletes its output
