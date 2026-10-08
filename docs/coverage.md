# Coverage: how well rpggen handles real packs

This page is the published record for the pack-coverage study (ARCHITECTURE §51) and the held-out
validation of the Definition of Done (§50, task T10.09). **Numbers below are marked with where they
come from.** Anything that needs packs this repository cannot contain (commercial or unseen packs)
is a human step and is marked *pending* until a maintainer fills it in. Nothing here is estimated.

## What is measured automatically

| Evidence | Result | Source |
|----------|--------|--------|
| Detection accuracy on the synthetic corpus (12 packs: tile grids with gutters and margins, strips, RPG Maker-like, LPC-like, Tiled and Aseprite metadata, objects in sheets, weird names, zips) | grid 1.000, usage 1.000, role 1.000, animations 1.000 (thresholds 0.95 / 0.95 / 0.85 / 0.90) | `python -m rpggen analyze --corpus test_packs/synthetic`, enforced in CI |
| End-to-end generation of every synthetic pack and the sample pack, both archetypes: validation and smoke test | pass | `tests/integration/test_all_synthetic_packs.py`, `test_m7_sample.py`, `test_m9_sample.py` |
| 1,000-image generated pack (tile sheets, strips, icons) | analysis 4.4 s cold / 0.9 s warm (targets 60 s / 5 s); full generation 47 s (target under 5 min medium pack) | `pytest -m slow tests/perf` on the author's PC |
| Frozen Windows build generates the sample pack | pass | `python tools/package.py --smoke` |

The synthetic corpus is the set the heuristics were tuned on, so its 1.000 guards against
regressions and says little about unfamiliar packs. That is what the held-out runs are for.

## Accuracy on real packs without keeping their art (T12.26)

The packs a person buys cannot be committed, but what a person *decided* about them can. A corpus
**entry** is one JSON file with the fingerprint of a pack (the path, size and SHA-256 of every
file) and the decisions confirmed in the Audit (the exported profile: roles, grids, animations,
objects). It holds no pixels.

```bat
python tools/corpus_fingerprint.py --pack "C:\Packsorest" --profile forest.rpgprofile.json --out corpusorest.corpus.json
python -m rpggen analyze --private-corpus corpus --packs "C:\Packs" --report private_report.json
```

The second command finds each pack under `--packs` by its fingerprint (at least 80% of the files
unchanged), analyzes it and writes `private_report.json` and `private_report.md`: per pack the grid,
usage, role and animation accuracy, per role the precision and recall, the confusion matrix (which
role a confirmed role was detected as) and how many of the confirmed objects were found. A pack
that is not there is listed as not found. CI runs it on a self-hosted runner when the repository
variables `PRIVATE_CORPUS` and `PRIVATE_PACKS` name the two folders. Use it to fill the held-out
table below.

## Pack-coverage study (ARCHITECTURE §51)

*Pending (human).* Sample about 30 popular top-down RPG packs, free and paid. For each record the
tier that handles it (1: Tiled/Aseprite/LDtk metadata, 2: layout standard such as RPG Maker or
LPC, 3: vendor layout needing a profile, 4: none) and what had to be fixed in the audit. If one
vendor family covers a large share of the packs in tier 3 or 4, ship its profile in the registry.
Record each pack in the table:

| Pack (source, license) | Tier | Audit edits | Notes |
|------------------------|:----:|------------:|-------|
| *(none recorded yet)* | | | |

## Held-out validation (T10.09)

*Pending (human).* The maintainer picks **5 packs not used during development**: at least 2
commercial, 1 in RPG Maker format, 1 with Tiled metadata and 1 "messy" pack (inconsistent names,
mixed sizes, nested folders). For each pack and each archetype run

```bat
python tools/held_out_run.py --pack "C:\Packs\unseen1" --name unseen1 --godot "<Godot 4.7.2 exe>"
```

which generates both archetypes headless and appends one row per run to
`validation_runs/results.md` (analysis time, generation time, passed, errors, warnings). Fill in
the two columns only a person can measure: **time to first paint** (wizard start until painting
tiles in Godot) and **manual audit edits**. Every bug found is fixed or ticketed.

The release ships when **all 10 runs pass** and the **median time to first paint is under 10
minutes**. Paste the final table here:

| Pack | Archetype | Time to first paint (min) | Audit edits | Passed | Bugs |
|------|-----------|--------------------------:|------------:|:------:|------|
| *(pending)* | | | | | |

The release gate (`docs/spec/M10_release.md` T10.10) stays open until this table is filled.
