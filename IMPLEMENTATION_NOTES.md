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
