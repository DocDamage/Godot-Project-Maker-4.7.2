"""Confidence calibrated on the answer key (T17.34): a bin is sure only when its pictures are
right 99 % of the time or more, surely; the shipped table changes nothing it was not fitted on."""

from __future__ import annotations

import pytest

from rpggen.core import calibration, catalog

AUTO, CONFIRMED = catalog.AUTO_CONFIDENCE, catalog.CONFIRMED_CONFIDENCE


def _pictures(reader: str, role: str, confidence: float, right: int, wrong: int) -> list[dict]:
    row = {"reader": reader, "role": role, "confidence": confidence}
    return [{**row, "right": True}] * right + [{**row, "right": False}] * wrong


def test_the_lower_end_of_the_interval_is_cautious() -> None:
    assert calibration.wilson_low(0, 0) == 0.0
    assert calibration.wilson_low(10, 10) < 0.75  # ten right of ten proves little
    assert calibration.wilson_low(1000, 1000) > 0.99
    assert calibration.wilson_low(990, 1000) < 0.99


def test_a_bin_right_almost_always_is_sure_and_one_that_is_not_is_not() -> None:
    pictures = _pictures("grid", "GROUND", 0.5, 2000, 0)  # cautious reader, always right
    pictures += _pictures("grid", "ITEM", 0.8, 900, 100)  # sure-looking reader, 90 % right
    table = calibration.fit(pictures, AUTO, CONFIRMED)
    raised = calibration.calibrate_with(table, "grid", "GROUND", 0.5)
    lowered = calibration.calibrate_with(table, "grid", "ITEM", 0.8)
    assert AUTO <= raised < CONFIRMED
    assert lowered < AUTO


def test_a_role_the_key_saw_too_little_of_falls_back_to_the_reader() -> None:
    pictures = _pictures("grid", "GROUND", 0.5, 400, 0) + _pictures("grid", "WATER", 0.5, 5, 0)
    table = calibration.fit(pictures, AUTO, CONFIRMED)
    assert f"*|grid|WATER|{calibration.bin_of(0.5)}" not in table["bins"]
    assert calibration.calibrate_with(table, "grid", "WATER", 0.5) == pytest.approx(
        calibration.calibrate_with(table, "grid", "*", 0.5)
    )


def test_what_the_key_never_saw_keeps_its_confidence() -> None:
    table = calibration.fit(_pictures("grid", "GROUND", 0.5, 400, 0), AUTO, CONFIRMED)
    assert calibration.calibrate_with(table, "other", "GROUND", 0.42) == 0.42
    assert calibration.calibrate_with(table, "grid", "GROUND", 0.95) == 0.95  # another bin


def test_calibration_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPGGEN_CALIBRATION", "off")
    assert calibration.calibrate("anything", "GROUND", 0.33) == 0.33


def test_a_publisher_s_own_bins_come_first() -> None:
    # Kenney's grounds are right; another publisher's, read by the same reader, are not
    pictures = [{**p, "publisher": "kenney"} for p in _pictures("iso", "GROUND", 0.6, 600, 0)]
    pictures += [{**p, "publisher": "other"} for p in _pictures("iso", "GROUND", 0.6, 300, 300)]
    table = calibration.fit(pictures, AUTO, CONFIRMED)
    assert calibration.calibrate_with(table, "iso", "GROUND", 0.6, "kenney") >= AUTO
    assert calibration.calibrate_with(table, "iso", "GROUND", 0.6, "other") < AUTO
    assert calibration.calibrate_with(table, "iso", "GROUND", 0.6, "") < AUTO  # unknown: all


def test_the_publisher_is_read_from_the_licence() -> None:
    lime = {"author": "LimeZu", "url": "https://limezu.itch.io"}
    assert calibration.publisher_id(lime) == "limezu"
    assert calibration.publisher_id({"url": "http://support.kenney.nl"}) == "kenney"
    assert calibration.publisher_id({}) == ""
