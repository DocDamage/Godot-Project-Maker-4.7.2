from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RESULTS: list[dict[str, object]] = []  # what the tests measured, in seconds


def record(name: str, seconds: float) -> None:
    """Remember a timing for ``perf.json`` (the trend that CI publishes)."""
    RESULTS.append({"name": name, "unit": "s", "value": round(seconds, 2)})


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ANN001
    """Write ``perf.json`` (the format of benchmark-action's ``customSmallerIsBetter``) when
    something was measured. ``RPGGEN_PERF_JSON`` says where; the default is the working folder."""
    if not RESULTS:
        return
    out = Path(os.environ.get("RPGGEN_PERF_JSON", "perf.json"))
    out.write_text(json.dumps(RESULTS, indent=2) + "\n", encoding="utf-8")


@pytest.fixture(scope="session")
def big_pack(tmp_path_factory: pytest.TempPathFactory) -> Path:
    spec = importlib.util.spec_from_file_location("make_big_pack", REPO / "tools/make_big_pack.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path_factory.mktemp("big") / "bigpack"
    module.make_big_pack(out, 1000)
    return out
