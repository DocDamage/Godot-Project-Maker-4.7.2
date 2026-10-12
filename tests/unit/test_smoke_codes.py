"""The smoke sequences of the three arcade kinds report a failed step with the kind's own error
code (T16.18): `SMOKE-010` to `SMOKE-012`, which have the placeholders of `SMOKE-001`."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import orchestrator
from rpggen.errors import CODES

SMOKE = paths.templates_root() / "builder" / "smoke"
RUNNER = paths.templates_root() / "addons" / "rpg_runtime" / "debug" / "smoke_runner.gd"
OWN = {"shmup": "SMOKE-010", "run_and_gun": "SMOKE-011", "racing": "SMOKE-012"}


def _placeholders(code: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", CODES[code].message))


@pytest.mark.parametrize(("archetype", "code"), sorted(OWN.items()))
def test_every_step_of_a_kinds_sequence_carries_the_kinds_code(archetype: str, code: str) -> None:
    script = Path(orchestrator.OWN_SMOKE_STEPS[archetype].removeprefix("res://generated/"))
    text = (SMOKE / script.name).read_text(encoding="utf-8")
    assert f'const CODE := "{code}"' in text
    assert '"code": CODE' in text, "the helper that makes a step puts the code into it"
    body = text[text.index("func steps()") : text.index("func _step(")]
    made = re.findall(r'_step\("(\w+)", _(\w+), [\d.]+\)', body)
    assert len(made) >= 11 and all(name == fn for name, fn in made)
    assert '{"name"' not in body, "no step is made without the helper"
    for name, _fn in made:
        assert f"func _{name}() -> String:" in text, name
    assert CODES[code].severity == "error"
    assert _placeholders(code) == _placeholders("SMOKE-001") == {"step", "name", "detail"}


def test_the_runner_reports_a_step_with_its_code_and_any_other_with_smoke_001() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert 'step.get("code", "SMOKE-001")' in text
    assert '_issue(code, {"step": index, "name": step["name"], "detail": detail})' in text
    # the sequences of the older kinds name no code: their failures are SMOKE-001 as before
    for name in ("smoke_steps_m1.gd", "smoke_steps_m6.gd", "smoke_steps_metroidvania.gd"):
        assert '"code"' not in (SMOKE / name).read_text(encoding="utf-8"), name
