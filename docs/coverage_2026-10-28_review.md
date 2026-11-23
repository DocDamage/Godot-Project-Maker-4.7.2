# Review of the remaining 9,478 entries: 2026-10-28

**All 9,478 entries from the previous run were visually screened.** The pass used 99 numbered contact sheets, grouped by 249 image hashes (247 source-image groups and two generated atlases). It found 786 region corrections and additional source-layout problems. The same 30 inputs were analyzed again; 8,583 active entries retain NEEDS_REVIEW status.

This is a screening pass over visible roles, cropping and sheet layouts, followed by targeted enlarged checks and structural validation. It is not a complete answer key for animation names, frame timing, collision or terrain semantics. NEEDS_REVIEW means full metadata confirmation is still needed; it does not mean those cards were skipped in this pass. Partial checks do not raise confidence.

The [entry ledger and machine evidence](coverage_2026-10-28_review.json) account for every original ID and its current source or replacement. The [first repeat](coverage_2026-10-28_fixed.md) remains as a historical snapshot. Source art, numbered contact sheets, full catalogs, scripts and Godot projects remain locally under `F:\rpggen_scratch\real_pack_review_20261028`; no art is committed.

## Confirmed corrections

| Scope | Result |
|---|---|
| Region classifications | 786 checked region facts, bound to the full image SHA-256 and variant ID. This includes 109 printed headings/captions set aside, 132 buildings, 132 items, 97 tools, 23 animals, 21 weapons, 46 road pieces and 226 scenery corrections. Living animals get a static idle/walk fallback rather than being scenery. Confidence remains unchanged. |
| Preview and scale copies | Modern Interiors’ overview no longer contributes 138 bogus ground/character pieces. The original 16/32/48px atlases retain their cell coordinates; normal size selection keeps one size. Four full-image comparisons prove the 32/48px sheets are exact nearest-neighbor copies of the 16px originals. |
| Characters | Phone strips use 16x32 frames; seated poses use their verified 32x32 or 16x32 frames. Enlarged source checks establish right/up/left/down order for standing/running strips and right/left order for seated strips, fixing reversed horizontal directions. Older character exports are actors rather than ground. Unverified action timing remains flagged. |
| Fire and battlers | PNG fire sheets use columns of six frames at 44x48 or 32x32; the Tiled versions retain their original 16px atlas coordinates. Whole goblin battlers get an idle frame so their enemy scenes can be placed. |
| False terrain and construction fragments | Two metal strips no longer become animated blob terrains. Verified mixed construction atlases carry `terrain:manual`; their raw tiles remain available but unverified automatic terrain inference is withheld. `objects:manual` prevents captions, isolated animation frames and room edges from becoming loose props. This removes false automatic results instead of inflating accuracy. |
| Opaque pillar atlas | Corrected from backdrop to scenery. Its black matte and individual column boundaries still need manual extraction review; no arbitrary grid or background removal is claimed. |

These facts cover 54 source/layout readings in addition to the 786 region decisions. These scopes overlap, so their counts must not be added into an error rate. Profiles, learned decisions and carried user overrides retain precedence. Reviewed semantic corrections to Tiled atlases cannot change their grid, animation coordinates or map references.

## Before and after

| Measurement | Previous repeat | This review |
|---|---:|---:|
| Inputs / input image files | 30 / 443 | 30 / 443 |
| Catalog image entries | 13,858 | 13,059 |
| Active entries | 13,545 | 12,644 |
| Confident entries | 4,067 | 4,061 |
| NEEDS_REVIEW | 9,478 | 8,583 |
| Unused entries | 313 | 415 |

The NEEDS_REVIEW count falls by 895. The reduction largely reflects removal of preview/caption pieces and replacement of enlarged or fragmented sheets with their correct source layout, not automatic confirmation of the remaining cards. Confident entries decrease because false generated terrain is removed.

| Outcome for the original 9,478 IDs | Count |
|---|---:|
| No additional defect confirmed in this screening | 7,855 |
| Corrected fields on a retained entry | 727 |
| Replaced by a reviewed source layout | 787 |
| Retained as unused caption/duplicate | 109 |

All 27 errors from the first 109-entry sample still pass their correction checks. Of its 55 previously accepted field judgments, 53 remain unchanged. Two were reconsidered: the loose cabbage is an item, and the 32px furniture cut is represented by the native atlas with its enlarged copy unused. These are intentional revisions to earlier review decisions, not silently changed expectations.

## Validation

All 30 analyses completed without errors or warnings. Independent decoded-image and animation bounds checks cover 2,040 active animation frames with no out-of-bounds frames. All 786 region decisions agree with the rerun. All four enlarged-atlas pixel comparisons pass. Eight original archives and 232 accepted direct-folder files were rehashed and are unchanged.

Ten real-pack assets-only projects generated and validated in Godot. Editor probes report 17 terrain checks with zero holes/mismatches and 102 dock placements. All ten renders were inspected. These paint probes check topology and placement; they do not certify every tile's meaning. The three final affected projects (town, interiors and dungeon) were generated again after the final terrain/direction corrections. The first Western probe hit a CP1252 logging error in the private harness and passed when rerun with UTF-8; the initial failed result is retained in the scratch logs.

| Check | Result |
|---|---|
| unit | 2560 passed, 3 skipped, 10 warnings in 394.84s (0:06:34) |
| gui | 43 passed in 13.67s |
| editor_integration | 6 passed in 110.13s (0:01:50) |
| focused | 21 passed in 1.52s |
| Static checks | Ruff check/format, mypy (213 modules), git diff --check pass |

## What remains

The 8,583 flagged active entries still need complete metadata confirmation: naming ambiguous objects and crops, deciding which modular pieces form terrain, checking animation actions/timing and collision/footprints. Static effect variants are not assumed to be animation frames. The opaque pillar sheet still needs a trustworthy matte/extraction treatment. Native room-construction and dungeon atlases can be painted as tiles while unverified terrain assignments stay manual.

This pass does not establish whole-pack accuracy, complete profiles, owner approval, first-paint timings, market coverage or held-out release qualification. T17.34 and the held-out validation rows remain open.

## Reproduction

The local scratch scripts `prepare_review.py`, `record_fixes.py`, `record_layouts.py`, `run_study.py`, `audit_review.py`, `compare_study.py` and the editor checks retain the numbered baseline, independent decisions and reruns. The JSON records the final source-code/data hashes, exact input manifest, every review disposition, all expected region changes, bounds/scale checks, test log hashes and native probe results. Run with the repository’s Python 3.12 virtual environment and isolated scratch/cache paths on F:.
