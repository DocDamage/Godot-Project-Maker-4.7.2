"""T17.34: Edit > Local vision model… is off by default, says what is missing, and saves."""

from __future__ import annotations

from pathlib import Path

from rpggen.core import app_settings
from rpggen.gui.dialogs.vision_dialog import VisionDialog


def test_off_by_default_and_nothing_is_sent(qtbot) -> None:
    dialog = VisionDialog()
    qtbot.addWidget(dialog)
    assert not dialog.enabled_box.isChecked()
    assert "nothing is sent" in dialog.state_label.text()
    assert dialog.port_box.value() == 8190


def test_missing_files_are_named_and_the_choice_is_saved(qtbot, tmp_path: Path) -> None:
    dialog = VisionDialog()
    qtbot.addWidget(dialog)
    dialog.enabled_box.setChecked(True)
    assert "Not found" in dialog.state_label.text()
    files = {}
    for key in ("vision_server", "vision_model", "vision_projector"):
        files[key] = tmp_path / f"{key}.bin"
        files[key].write_bytes(b"x")
        dialog.edits[key].setText(str(files[key]))
    assert "Ready" in dialog.state_label.text()
    dialog.port_box.setValue(8391)
    dialog.save()
    saved = app_settings.get()
    assert saved.vision_enabled and saved.vision_port == 8391
    assert Path(saved.vision_projector) == files["vision_projector"]
