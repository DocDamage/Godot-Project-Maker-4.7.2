# Implementation Notes

## Decisions

* The git repository root is `F:\Godot Project Maker` (the GitHub repo). The spec folder
  `Implementation Plan and Specs/` stays at the root as the source of truth; T1.03 also copies it
  to `docs/spec/` as the card requires.
* Local development uses Python 3.12 in `.venv` and Godot 4.7.1 (installed locally;
  4.7.2 is the validated version, so ENV-003 warnings are expected locally).

## Task log

T1.01 done — scaffold, CLI version command, tests/ruff green — repo root is the existing GitHub repo root; pyproject adds build-system/setuptools config and ruff excludes (not in spec)
T1.02 done — jsonio, ids, paths, six JSON schemas (generated once from a throwaway script, hand-maintainable now) with tests — schema/jsonio raise ValueError until T1.03; detected facets require role+usage; added optional-field choices (FacetsPartial for rules/profiles)
T1.03 done — error table generator (docs/spec copy is source), errors.py/IssueList, generated py/gd/md outputs; jsonio/schema now raise CAT-001/CAT-002 — RpgGenError/IssueList.add take message optionally (T1.05 calls RpgGenError('ENV-002', found=...)) and code is positional-only so detail may contain a 'code' key (BUILD-001); errors_table.py excluded from ruff; CI diff step arrives in T1.12
T1.04 done — deterministic basic16 synthetic pack + expected.json, committed under test_packs/synthetic — no deviation (expected.json written through jsonio so keys are sorted)
T1.05 done — godot.py (parse/check/find_console/detect/run_godot/auto_find) with unit+integration tests (integration verified locally on Godot 4.7.1) — run_godot uses Popen+taskkill /T for the timeout (os.name check in godot.py); the integration test project needs a main scene because 'godot --headless --quit' hangs without one (observed on 4.7.1); local Godot is 4.7.1, 4.7.2 download not yet done
T1.06 done — template project.godot (unchanged by import), icon.svg, runtime plugin.cfg (no script= key; not an EditorPlugin), godot.import_project(), api doc seeded — --import verified on 4.7.1; committed icon.svg.import and error_codes.gd.uid
T1.07 done — builder lib (paths/json_util/log/results/catalog_reader/build_context/geometry), build.gd, project_settings/tileset/sprite_frames recipes, probes, GDScript+Python tests, shared effective_cases fixture — decisions: builder uses script-relative preload (works at res://builder and res://generated/builder); BOTTOM/TOP/LEFT/RIGHT_EDGE thickness = clamp(side/4, 2, 4); rpggen/core/catalog.py gains merge()/effective() early (T1.10 extends it); fixture lives at godot_templates/tests/fixtures; extra test test_scene_owner.gd; T1.08 runner was written before T1.07's tests could run (committed in order T1.07, T1.08); recipes are exercised end-to-end in T1.11
