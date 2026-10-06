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
