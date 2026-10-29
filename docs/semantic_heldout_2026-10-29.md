# Semantic certification and held-out engineering validation — 2026-10-29

This pass adds **25 source-bound static-art certifications**, fixes four failures exposed by
fresh native projects, and records the candidate runs without erasing failed trials. The
owner's four saved answers remain unchanged. T17.34 and the human release gate remain open.
The [machine-readable evidence](semantic_heldout_2026-10-29.json) includes the certification
IDs, source/pixel hashes, trial revisions, results and resource measurements. No pack art is
committed. Private evidence is under `D:\rpggen_semantic_heldout_20261029`.

## What is certified

Three Goblin Gang enemy illustrations and 22 animal poses from the earlier 30-input study
were visually inspected and given explicit `static_battler` / `static_animal` record kinds.
Each decision requires the original source SHA-256, unchanged pre-review facets, matching
normalized RGBA pixels, a whole-image frame, a valid pivot, a zero-margin whole-image grid,
and exactly one one-frame `idle_down` animation. Extra walking animations or behavior fields
invalidate these record kinds. Bottom-center pivots and idle presentation are authored defaults.
The certification covers static art metadata; movement, combat behavior, farming production
and collision are outside its scope. Detector confidence is unchanged.

Fresh imports of p02/p08/p15 confirm all 22 animal poses, and fresh Goblin analysis confirms
all three battlers. A final read-only check rehashes their sources, verifies all 25 decisions
against their input/pixel guards, and checks **1,654 active image headers and 25 animation
frames** across those four current catalogs: zero failures. The three larger pack imports
take 19.03 / 15.44 / 27.17 seconds, with peak descendant private memory below 0.8 GiB.

Two partial corrections remain unconfirmed: review entry 887 is a watchtower, corrected from
ANIMAL to BUILDING/object, whose footprint and entrance still need review; entry 908 contains
grouped cat poses, whose invented walking animation is removed pending segmentation.

Applying these dispositions to the original metadata ledger reduces its 2,513 unresolved
entries by 25 to **2,488**. This is a ledger delta, not a new import of all 30 inputs:

| Remaining blocker | Entries |
|---|---:|
| Crop stages and harvest behavior | 10 |
| Building entrance, footprint or composite structure | 133 |
| Segmentation, captions, completeness or functional-state ambiguity | 2,012 |
| Actor layout, timing or runtime behavior | 23 |
| Terrain topology, grid or material behavior | 310 |

The watchtower moves from the actor to building bucket; grouped cats move to segmentation.
The 23 remaining actor entries are moving/sitting/phone sheets from Modern Interiors, not
additional static poses to approve by default. Earlier orchard work has its own source-bound
scope and is not silently subtracted from this older ledger.

## Native art checks

A private Godot gallery builds and serializes 25 native-frame actor scenes, reloads their
pivots, and exports the imported frame textures. All 25 pivots and frame dimensions survive.
The normal Godot import preserves all 25 alpha channels and 22 normalized RGBA hashes.
Its default `process/fix_alpha_border` changes low-alpha RGB on the three antialiased Goblin
images (377 / 494 / 513 pixels). Disabling that setting only on the three private gallery
imports produces 25/25 source RGBA matches. Actual generated trial projects retain their
normal import settings. This controlled check does not claim default imports are byte-identical.
Invalid private-harness attempts are excluded from these successful checks.

## Candidate selection and trial safeguards

The five candidate inventories have **zero image-byte hash overlap** with 708 recorded
development evidence files containing 27,338 distinct hashes; no evidence files were unavailable.
This establishes byte disjointness from that evidence set, not complete historical novelty,
independent publishers, or novelty of edited art. Commercial purchase provenance is unverified,
and none of these five has verified Tiled metadata. They are engineering candidates, not a
fully qualified T10.09 release sample. Monster Gaja supplies nested HD/SD variants, the ruins
supply RPG Maker MV sheets, and Chest and Key supplies nested animated items.

`held_out_run.py` rejects escaping names and existing project/checkpoint paths, writes an
atomic per-trial checkpoint, and preserves the source inventory, catalog, revision, working-tree
state, timings, issues and failed staging path. Each rerun uses a fresh directory. Runs request
PLAYER and GROUND placeholders. Sequential subprocesses have an 8 GiB descendant-private-memory
guard and a 20-minute per-pack limit; no measured native candidate run trips either guard.

The first frozen batch (`0306fdf`, `trials_01`) fails all ten candidate runs before play because
shared tile hazards reference `RpgSideTiles`, omitted from top-down projects. The same issue
affects both known Goblin regression runs. Direct `TileMapLayer` discovery fixes that dependency;
two integration cases explicitly generate, validate and smoke-test projects without side-view
runtime files.

The second batch (`f6f7594`, `trials_02`) passes eight candidate runs. Both ruins runs fail the
map exit: suffixed B sheets were guessed as 12 px grids beside 48 px A sheets. Coherent-family
recognition now requires two distinct standard A layouts sharing directory, prefix and native
tile size, then admits only standard-sized family members. The repaired catalog has one 48 px
tileset; the rule admits no additional files in the other four candidates. Negative tests
reject isolated and inconsistent names. A compatibility check on all 25 cached development
inventories admits zero new family members, including all four owner-choice packs.
The Goblin ARPG regression separately exposes a
large-illustration combat body that cannot be reached. Static battlers now use tile-bounded
default combat bodies/feet; native visuals, pivots and explicit user footprints are preserved.

The third batch (`4018d29`, `trials_03`) passes the ruins turn-based project and both known
Goblin regressions. The ruins ARPG reaches a later follower-assist failure: a small placeholder
sprite stands one 48 px tile away, beyond its actual swing. Follower stopping distance now
uses its attack reach/shape. This behavior default does not certify artist-authored combat
metadata. A regression covers small sprites on large native tiles.

Final runs use frozen code `9391440` in `trials_06` (ruins) and `trials_05` (other candidates and
known Goblin regression). The successful `trials_04` ruins pair is also preserved; its first
run records untracked generated fixtures from an invalid direct test-harness invocation,
so the clean `trials_06` pair replaces it in the final table. All final snapshots have a clean
worktree. These are post-fix regressions, not an unbiased semantic accuracy
measurement. Original failures remain in their earlier directories.

**10/10 final candidate runs pass**, with both known Goblin regressions also passing.

| Candidate | Archetype | Analysis s | Generation s | Errors | Warnings |
|---|---|---:|---:|---:|---:|
| bomb_trio | arpg | 0.1 | 43.5 | 0 | 9 |
| bomb_trio | turn_based | 0.3 | 33.4 | 0 | 9 |
| chest_keys | arpg | 14.2 | 75.1 | 0 | 8 |
| chest_keys | turn_based | 14.8 | 64.5 | 0 | 8 |
| colony_extended | arpg | 0.6 | 51.0 | 0 | 7 |
| colony_extended | turn_based | 0.6 | 41.1 | 0 | 7 |
| monster_gaja | arpg | 5.5 | 60.9 | 0 | 9 |
| monster_gaja | turn_based | 5.7 | 55.8 | 0 | 9 |
| rmmv_ruins | arpg | 1.0 | 54.6 | 0 | 12 |
| rmmv_ruins | turn_based | 1.2 | 44.5 | 0 | 12 |

Final per-pack runs peak at 3,205,046,272 descendant private bytes (2.98 GiB). The largest measured peak across all frozen batches is 7,389,929,472 bytes (6.88 GiB). These are sampled process-private measurements, not total system commitment.


Warnings remain visible: ASSET-010 reports missing asset roles and VAL-012 reports validation concerns;
the ruins also reports TILE-006 for skipped unrecognized A1/A4 terrain layouts. Passing build
and smoke checks therefore does not certify every source asset or complete terrain support.
For example, enemy-art candidates can still report a missing ENEMY role while a starter
project builds. Their art has not received a semantic certification in this pass.
Manual first-paint and audit-edit columns remain blank. The two known Goblin runs are recorded
separately and do not count as held-out candidates.

## Saved answers, calibration and verification

The saved answers are H1 **Harvested produce (ITEM)**, H2 **Use orchard crops (CROP)**,
H3 **I want to define hazards for my game**, and H4 **Visual effect (EFFECT)**. Notes remain
empty. No hazard is enabled by this work and no additional owner choice is manufactured.
The 25 new certifications have zero source-hash overlap with the owner's 44 selected entries.
`review_decisions.json` remains SHA-256
`52294b9655fb46c2165751c05cb0d2245baf5f798d3dbcd3965a224458901128`.

The calibration safeguards from the [preceding pass](metadata_validation_2026-10-29.md) remain
in force. Applied corrections and confirmations are excluded from independent calibration
support. These 25 decisions and passing native projects cannot establish a 99% accuracy rate.
The shipped empty calibration table is unchanged, SHA-256
`73abface1d895568205ddc41c917dbfb0558daf7e6ca95e0ca2fcaf1a269b588`.

Verification: full Python unit suite **2,604 passed / 3 skipped**; the final focused
repair suite passes 25 tests, covering all **2,607 unique current unit cases** across
those runs. The two new top-down dependency integration cases pass. Final Godot suite:
**1,108 passed / 0 failed / 0 script errors**, with the same 53 known fixture/negative
engine diagnostics and 28 push diagnostics. Ruff and formatting (508 files) pass;
mypy passes for 217 source modules. Native project header/frame checks also pass
for all 12 final projects (230 active images, 246 animation frames across the projects).


T17.34 still needs the unresolved semantic metadata and independent calibration labels.
T10.09/T10.10 still need a qualified sample including two commercial inputs and verified Tiled
metadata, human first-paint timings, complete manual audit-edit counts and the remaining manual
release checks. No release gate is closed by this report.

Follow-up: the [actor-art certification pass](actor_metadata_2026-10-29.md) disposes of the 23
flagged actor-art entries and corrects Modern Interiors' license metadata. Its new ledger delta
is recorded separately; the trial evidence and counts above retain their original scope.
