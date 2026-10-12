"""The arithmetic of the calendar (T17.03), the same the runtime counts by.

``RpgCalendar`` (``world/calendar.gd``) has every function of this module with the same
numbers; ``cases()`` is a table of inputs and results that both are tested against
(``godot_templates/tests/unit/calendar_math_cases.json``, written by ``python -m
rpggen.core.calendar_math``). The planner of the farm uses it for what a date is after some
days.

A day runs from 6:00 to 2:00 of the night. The minute of the day is counted from the midnight
before its morning, so 6:00 is 360, noon 720, midnight 1440 and 2:00 of the night 1560: a
minute never goes back within a day. A season has 28 days (7 or 14 in a shorter game), a year
has the four seasons, and a week seven days. Days and years are counted from 1 and seasons from
0 (spring); the *index* of a day is how many days lie before it since the first day of the
first year. No Qt, no Godot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SEASONS = ("spring", "summer", "autumn", "winter")
DAY_START = 360  # 6:00
DAY_END = 1560  # 2:00 of the night
DAY_MINUTES = 1200  # from the one to the other
MINUTE_S = 0.7  # real seconds a game minute
DAYS_PER_SEASON = 28
SEASON_LENGTHS = (7, 14, 28)
WEEK_DAYS = 7


def season_length(days_per_season: int) -> int:
    """The length of a season a game may have: 7, 14 or 28 days, 28 for anything else."""
    return days_per_season if days_per_season in SEASON_LENGTHS else DAYS_PER_SEASON


def day_index(day: int, season: int, year: int, days_per_season: int = DAYS_PER_SEASON) -> int:
    """How many days lie before a date since the first day of the first year."""
    length = season_length(days_per_season)
    seasons = (max(1, year) - 1) * len(SEASONS) + max(0, min(len(SEASONS) - 1, season))
    return seasons * length + max(1, min(length, day)) - 1


def date_of(index: int, days_per_season: int = DAYS_PER_SEASON) -> tuple[int, int, int]:
    """The date of the day with this index: (day of the season, season, year)."""
    length = season_length(days_per_season)
    index = max(0, index)
    seasons = index // length
    return index % length + 1, seasons % len(SEASONS), seasons // len(SEASONS) + 1


def date_after(
    day: int, season: int, year: int, days: int, days_per_season: int = DAYS_PER_SEASON
) -> tuple[int, int, int]:
    """The date ``days`` days after a date."""
    return date_of(day_index(day, season, year, days_per_season) + days, days_per_season)


def season_of(index: int, days_per_season: int = DAYS_PER_SEASON) -> int:
    """The season of the day with this index."""
    return date_of(index, days_per_season)[1]


def season_name(season: int) -> str:
    return SEASONS[season % len(SEASONS)]


def weekday(index: int) -> int:
    """The day of the week of the day with this index: 0 for the first day of a year."""
    return max(0, index) % WEEK_DAYS


def add_minutes(minute: int, span: int) -> tuple[int, int]:
    """The minute of the day ``span`` game minutes after ``minute``, and how many days ended
    on the way. A day that reaches 2:00 ends, and the next begins at 6:00."""
    passed = max(DAY_START, min(DAY_END - 1, minute)) - DAY_START + max(0, span)
    return DAY_START + passed % DAY_MINUTES, passed // DAY_MINUTES


def clock(minute: int) -> tuple[int, int]:
    """The time a clock shows at a minute of the day: (hour from 0 to 23, minute)."""
    return minute // 60 % 24, minute % 60


def hour_of(minute: int) -> float:
    """The hour of the day and night light (0 to 24) at a minute of the day."""
    return minute % 1440 / 60.0


def day_seconds(minute_s: float = MINUTE_S) -> float:
    """How long a whole day is in real seconds."""
    return DAY_MINUTES * minute_s


# --------------------------------------------------------------------------- the shared table

CASES_FILE = "godot_templates/tests/unit/calendar_math_cases.json"


def _r(value: float) -> float:
    return round(float(value), 6)


def cases() -> list[dict[str, Any]]:
    """Inputs and results of every function, for the GDScript mirror to be tested against."""
    out: list[dict[str, Any]] = []

    def add(fn: str, args: list[Any], result: Any) -> None:
        if isinstance(result, tuple):
            result = list(result)
        elif isinstance(result, float):
            result = _r(result)
        out.append({"fn": fn, "args": args, "result": result})

    for length in (7, 14, 28, 0, 10, 30, -1):
        add("season_length", [length], season_length(length))
    dates = ((1, 0, 1), (28, 0, 1), (1, 1, 1), (14, 2, 1), (28, 3, 1), (1, 0, 2), (7, 3, 5))
    for length in SEASON_LENGTHS:
        for day, season, year in dates:
            add("day_index", [day, season, year, length], day_index(day, season, year, length))
            for days in (0, 1, 6, 27, 28, 111, 112, 500):
                add(
                    "date_after",
                    [day, season, year, days, length],
                    date_after(day, season, year, days, length),
                )
        for index in (0, 1, 6, 7, 13, 14, 27, 28, 55, 56, 83, 84, 111, 112, 113, 336, 1000):
            add("date_of", [index, length], date_of(index, length))
            add("season_of", [index, length], season_of(index, length))
    add("day_index", [0, -1, 0, 28], day_index(0, -1, 0, 28))  # what is not a date is the nearest
    add("day_index", [99, 9, 2, 28], day_index(99, 9, 2, 28))
    add("date_of", [-5, 28], date_of(-5, 28))
    for season in range(-1, 9):
        add("season_name", [season], season_name(season))
    for index in (0, 1, 6, 7, 8, 27, 28, 111, 112, 365):
        add("weekday", [index], weekday(index))
    for minute in (360, 361, 719, 720, 1439, 1440, 1500, 1559):
        add("clock", [minute], clock(minute))
        add("hour_of", [minute], hour_of(minute))
        for span in (0, 1, 59, 60, 600, 1199, 1200, 1201, 2400, 5000):
            add("add_minutes", [minute, span], add_minutes(minute, span))
    add("add_minutes", [0, 10], add_minutes(0, 10))  # before the morning counts as 6:00
    add("add_minutes", [1560, 10], add_minutes(1560, 10))
    add("add_minutes", [700, -30], add_minutes(700, -30))  # time does not go back
    for minute_s in (0.7, 0.5, 1.0, 2.0):
        add("day_seconds", [minute_s], day_seconds(minute_s))
    return out


def write_cases(repo: Path) -> Path:
    path = repo / CASES_FILE
    path.write_text(json.dumps(cases(), indent=1) + "\n", encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":  # pragma: no cover
    print(write_cases(Path(__file__).resolve().parents[2]))
