from __future__ import annotations

from rpggen.core import catalog
from rpggen.gui.edits import EditSession
from rpggen.gui.widgets.hazard_settings import HazardSettings


def test_individual_hazards_preserve_neighbors_other_metadata_and_undo(qtbot):
    asset = catalog.Asset(
        id="pack.floor",
        pack_id="pack",
        path="floor.png",
        sha256="0" * 64,
        kind="image",
        status="NEEDS_REVIEW",
        detected={
            "usage": "tiles",
            "role": "GROUND",
            "size": [32, 16],
            "grid": {"cell": [16, 16]},
            "tile_overrides": {
                "0,0": {"custom": {"sound": "mud"}},
                "1,0": {"custom": {"hazard": False}},
            },
        },
    )
    cat = catalog.Catalog(assets=[asset])
    session = EditSession(cat)
    widget = HazardSettings(session)
    qtbot.addWidget(widget)
    widget.load_asset(asset.id, catalog.effective(asset))
    assert not widget.enabled.isChecked()
    assert session.undo_stack.count() == 0, "displaying defaults never saves them"
    widget.enabled.setChecked(True)
    widget.damage.setValue(7)
    widget.cooldown.setValue(2.5)
    changed = catalog.effective(session.catalog.asset(asset.id))["tile_overrides"]
    assert changed["0,0"]["custom"] == {
        "sound": "mud",
        "hazard": True,
        "hazard_damage": 7,
        "hazard_cooldown": 2.5,
    }
    assert changed["1,0"] == {"custom": {"hazard": False}}
    widget.column.setValue(1)
    assert not widget.enabled.isChecked() and widget.damage.value() == 1
    session.undo_stack.undo()
    assert (
        catalog.effective(session.catalog.asset(asset.id))["tile_overrides"]["0,0"]["custom"][
            "hazard_cooldown"
        ]
        == 1.0
    )
    assert asset.overrides == {}, "the source catalog stays untouched"
