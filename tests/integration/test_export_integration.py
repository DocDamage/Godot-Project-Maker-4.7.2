from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import config, export_check, godot, orchestrator

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("target", config.EXPORT_TARGETS)
def test_generated_project_exports(godot_exe: Path, tmp_path: Path, target: str) -> None:
    version = godot.detect_version(godot_exe)
    if not export_check.templates_installed(version, target):
        pytest.skip(f"{target} export templates are not installed")
    target_dir = tmp_path / "game"
    cfg = orchestrator.default_config_for_pack(paths.sample_pack_root(), "Export Game")
    cfg.export_targets = [target]
    result = orchestrator.run_in_memory(cfg, None, target_dir, godot_exe)
    assert result.ok, [i.code for i in result.issues]
    presets = (target_dir / "export_presets.cfg").read_text(encoding="utf-8")
    assert f'name="{export_check.TARGETS[target].preset}"' in presets
    assert "ENV-010" not in {i.code for i in result.issues}
    log = "godot_export.log" if target == "windows" else f"godot_export_{target}.log"
    assert (target_dir / "rpggen/logs" / log).is_file()
    assert not list(target_dir.rglob(export_check.TARGETS[target].test_file))  # output deleted
