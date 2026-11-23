# Coverage: how well rpggen handles real packs

This page is the published record for the pack-coverage study (ARCHITECTURE §51) and the held-out
validation of the Definition of Done (§50, task T10.09). **Numbers below are marked with where they
come from.** The real-pack baseline below uses the owner's local collection; only measurements
and review decisions are committed. Complete audits, owner checks and first-paint timings remain
pending where they have not been measured. Nothing here is estimated.

## What is measured automatically

| Evidence | Result | Source |
|----------|--------|--------|
| Detection accuracy on the synthetic corpus (12 packs: tile grids with gutters and margins, strips, RPG Maker-like, LPC-like, Tiled and Aseprite metadata, objects in sheets, weird names, zips) | grid 1.000, usage 1.000, role 1.000, animations 1.000 (thresholds 0.95 / 0.95 / 0.85 / 0.90) | `python -m rpggen analyze --corpus test_packs/synthetic`, enforced in CI |
| End-to-end generation of every synthetic pack and the sample packs, every archetype: validation and smoke test | pass | `tests/integration/test_all_synthetic_packs.py`, `test_m7_sample.py`, `test_m9_sample.py` |
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
python tools/corpus_fingerprint.py --pack "C:\Packs\forest" --profile forest.rpgprofile.json --out corpus\forest.corpus.json
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

**Baseline, fixes, repeat study and remaining-entry screening completed 2026-10-28** on 30 inputs from
`G:\All 2D Assets Stay Here`: 28 top-down inputs and two isometric extensions, across seven
library folder groups. The [per-pack table and findings](coverage_2026-10-28.md) record each
input's local source, detected license, reader tier, confidence counts and sampled corrections.
The [repeat report](coverage_2026-10-28_fixed.md) and its
[JSON evidence](coverage_2026-10-28_fixed.json) record the fixes and their verification against
the same inputs. The [remaining-entry review](coverage_2026-10-28_review.md) and its
[complete ID ledger](coverage_2026-10-28_review.json) screen all 9,478 previously flagged entries
and record further corrections. The original evidence is retained. No pack art is committed.

| Measured evidence | Result |
|-------------------|--------|
| Inputs completing analysis / input image files | 30 / 443; no analysis errors or warnings in the repeat |
| Active catalog image entries after cutting and terrain generation | 12,644: 4,061 confident (32.1%), 8,583 NEEDS_REVIEW (67.9%) |
| Agent screening | All 9,478 previously flagged entries screened in 99 contact sheets; 786 region corrections verified. All 27 original correction checks still pass; 53 earlier accepted field judgments remain unchanged and two are explicitly revised. This is not full metadata certification. |
| Assets-only editor checks | Ten projects built and validated; 17 terrain checks with zero holes/mismatches, 102 dock placements, inspected renders. Unverified mixed-atlas terrain inference is withheld; three projects have no terrain checks. |
| Input integrity | Eight original archives (including a wrapped archive) and 232 accepted direct-folder files rehashed; all unchanged |

This is a convenience sample of the owner's library, not a popularity survey or a measured
free/paid market sample. Confidence is not accuracy, and successful analysis/generation is not
proof of pack support. The follow-up applies 786 further region corrections and 54 source/layout
readings bound to complete image hashes; these scopes overlap and do not form an accuracy rate.
Partial field checks do not increase confidence. Complete audit edit counts and first-paint times
remain unmeasured. Whole-pack
profiles for the CuteSCKR and SakPix families (14/30 inputs) still need complete audits.
The repeat report also corrects two original findings: the pink Elements tile is legitimate art,
and LPC's 128 reported perimeter errors were a probe bug. T17.34 remains open.

## Held-out validation (T10.09)

The subsequent [metadata confirmation pass](coverage_2026-10-28_metadata.md) reviewed all
8,583 remaining entries and confirmed 6,070 static placements with explicit non-blocking
defaults. The repeated 30-pack analysis has 6,070 CONFIRMED, 4,061 AUTO_DETECTED and 2,513
NEEDS_REVIEW active entries. This does not certify functional doors, actors, crops, terrain
topology or ambiguous extractions; the per-entry ledger records what remains unresolved.

*Pending (human).* The maintainer picks **5 packs not used during development**: at least 2
commercial, 1 in RPG Maker format, 1 with Tiled metadata and 1 "messy" pack (inconsistent names,
mixed sizes, nested folders). For each pack and each archetype run

```bat
python tools/held_out_run.py --pack "C:\Packs\unseen1" --name unseen1 --godot "<Godot 4.7.2 exe>"
```

which generates the archetypes headless and appends one row per run to
`validation_runs/results.md` (analysis time, generation time, passed, errors, warnings). Fill in
the two columns only a person can measure: **time to first paint** (wizard start until painting
tiles in Godot) and **manual audit edits**. Every bug found is fixed or ticketed.

The release ships when **all 10 runs pass** and the **median time to first paint is under 10
minutes**. Paste the final table here:

| Pack | Archetype | Time to first paint (min) | Audit edits | Passed | Bugs |
|------|-----------|--------------------------:|------------:|:------:|------|
| *(pending)* | | | | | |

The release gate (`docs/spec/M10_release.md` T10.10) stays open until this table is filled.
