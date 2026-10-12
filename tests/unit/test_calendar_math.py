"""T17.03: the arithmetic of the calendar, and the table of cases the GDScript mirror
(``RpgCalendar``) is tested against."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from rpggen.core import calendar_math

REPO = Path(__file__).resolve().parents[2]


def test_the_table_of_cases_is_what_the_module_gives() -> None:
    """The file the GDScript test reads is written by ``python -m rpggen.core.calendar_math``;
    a change of the arithmetic that is not written there fails here, and then in Godot."""
    stored = json.loads((REPO / calendar_math.CASES_FILE).read_text(encoding="utf-8"))
    assert stored == calendar_math.cases()
    names = {case["fn"] for case in stored}
    public = {
        name
        for name, value in vars(calendar_math).items()
        if callable(value)
        and not name.startswith("_")
        and value.__module__ == calendar_math.__name__
    }
    assert public - {"cases", "write_cases"} == names, "every function is in the table"
    assert len(stored) > 300


def test_the_runtime_has_the_same_numbers() -> None:
    text = (REPO / "godot_templates/addons/rpg_runtime/world/calendar.gd").read_text(
        encoding="utf-8"
    )
    for name in ("DAY_START", "DAY_END", "DAY_MINUTES", "MINUTE_S", "DAYS_PER_SEASON", "WEEK_DAYS"):
        value = re.escape(repr(getattr(calendar_math, name)))
        assert re.search(rf"^const {name} := {value}(\s|$)", text, re.MULTILINE), name
    seasons = ", ".join(f'"{name}"' for name in calendar_math.SEASONS)
    assert f"const SEASONS: Array[String] = [{seasons}]" in text
    lengths = ", ".join(str(n) for n in calendar_math.SEASON_LENGTHS)
    assert f"const SEASON_LENGTHS: Array[int] = [{lengths}]" in text


def test_a_day_runs_from_six_to_two_at_night() -> None:
    assert calendar_math.clock(calendar_math.DAY_START) == (6, 0)
    assert calendar_math.clock(calendar_math.DAY_END) == (2, 0)
    assert calendar_math.DAY_END - calendar_math.DAY_START == calendar_math.DAY_MINUTES == 20 * 60
    assert calendar_math.clock(1439) == (23, 59) and calendar_math.clock(1440) == (0, 0)
    assert calendar_math.hour_of(720) == 12.0 and calendar_math.hour_of(1500) == 1.0
    assert calendar_math.day_seconds() == pytest.approx(14 * 60), "a day is about 14 minutes"


def test_the_minute_after_a_time_span() -> None:
    assert calendar_math.add_minutes(360, 0) == (360, 0)
    assert calendar_math.add_minutes(360, 90) == (450, 0)
    assert calendar_math.add_minutes(1559, 1) == (360, 1), "2:00 is the next morning"
    assert calendar_math.add_minutes(360, 1199) == (1559, 0)
    assert calendar_math.add_minutes(720, 3 * 1200) == (720, 3)
    assert calendar_math.add_minutes(700, -30) == (700, 0), "time does not go back"


def test_days_seasons_and_years() -> None:
    assert calendar_math.date_of(0) == (1, 0, 1)
    assert calendar_math.date_after(28, 0, 1, 1) == (1, 1, 1), "28 days are a season"
    assert calendar_math.date_after(28, 3, 1, 1) == (1, 0, 2), "four seasons are a year"
    assert calendar_math.date_after(1, 0, 1, 4 * 28) == (1, 0, 2)
    assert calendar_math.date_after(7, 0, 1, 1, 7) == (1, 1, 1), "a season of seven days"
    assert calendar_math.date_after(1, 0, 1, 4 * 14, 14) == (1, 0, 2)
    for length in calendar_math.SEASON_LENGTHS:
        for index in range(0, 3 * 4 * length + 5):
            day, season, year = calendar_math.date_of(index, length)
            assert calendar_math.day_index(day, season, year, length) == index
            assert 1 <= day <= length and 0 <= season <= 3 and year >= 1
            assert calendar_math.season_of(index, length) == season
    assert [calendar_math.season_name(s) for s in range(4)] == list(calendar_math.SEASONS)
    assert calendar_math.season_length(10) == 28 and calendar_math.season_length(14) == 14
    assert [calendar_math.weekday(i) for i in (0, 6, 7, 28)] == [0, 6, 0, 0]
    # whatever the length of a season, a year begins on the first day of a week
    assert all(calendar_math.weekday(4 * n) == 0 for n in calendar_math.SEASON_LENGTHS)
