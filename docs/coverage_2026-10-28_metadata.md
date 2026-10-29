# Metadata confirmation, 2026-10-28

All 8,583 entries left by the preceding review received a disposition. **6,070 static
entries are now confirmed; 2,513 remain NEEDS_REVIEW.** The same 30 inputs in
`G:\All 2D Assets Stay Here` were analyzed again. This is a review of this owner's
collection, not a detection-accuracy benchmark or a complete certification of every pack.

The [machine-readable ledger](coverage_2026-10-28_metadata.json) records every original
entry, its source hash, changed fields, current status and remaining confirmation blocker.
The original art is not included.

## What confirmation means here

The visual pass inspected 100 numbered sheets of static candidates and eight sheets of the
remaining entries. Confirmed entries have a complete individual image, a reviewed static
role and usage, measured image/frame dimensions, a base pivot and an empty animation map.
The 60 standalone plant/scenery images previously described as generic sprites were also
checked and confirmed as placeable static objects.

**Collision NONE is an authored, non-blocking default for these static placements.** It is
not a claim that the artist supplied collision rules. Pivots are based on the visible base
of the art; these are placement choices, not source-author annotations. The user can change
them in Audit. Confirmation does not invent pickup, damage, door, harvest or actor behavior.

The decisions in `rpggen/data/confirmed_metadata.json` require an exact source SHA-256,
variant, decoded sprite-pixel hash and complete pre-review facets. A changed source, changed
crop or changed reader output is not silently reconfirmed. User overrides, folder rules,
installed profiles and learned decisions retain priority. Partial readings in
`reviewed_regions.json` do not confer confirmation or raise detector confidence.

## Further fixes

- Corrected 64 partial role readings, including wall faces labeled ground, detached
  decorative pieces and a chicken labeled building. Four additional confirmed static
  entries had incorrect weapon/item roles corrected.
- Corrected two standalone fire-sheet readings using the source pack's embedded Tiled
  map and the sheet pixels. The first sheet has a 32-pixel column followed by three
  48-pixel columns, six phases 48 pixels apart. Explicit rectangles and padding preserve
  their alignment. The second has two interleaved styles in each of three columns,
  each with three phases, rather than six frames that mix the styles. Playback uses
  the map's 150 ms timing. These partial animation corrections remain NEEDS_REVIEW.
- Profile export now keys generated crops/strips by their original source files.
  Profiles containing generated helpers preserve per-source hashes beyond the fingerprint
  sample and let the normal readers recreate the helper images during reimport. Ordinary
  v1 profiles keep their established representation.
- The assets-only dock now includes tools, weapons and static terrain-role stamps.
  It no longer substitutes an inventory icon for a demo chest, which would defeat a
  confirmed item's non-blocking placement. The scene recipe also respects explicit NONE
  with no footprint instead of adding a fallback blocking polygon. Ordinary game chest
  fallback and explicit isometric footprints are preserved.

## Remaining work

| Blocker | Entries |
|---|---:|
| Crop completeness, segmentation, captions or functional-state ambiguity | 2,011 |
| Terrain topology, placement grid or material behavior | 310 |
| Building entrance/footprint or composite structure | 132 |
| Actor layout, animation timing or runtime behavior | 50 |
| Crop stages and harvest behavior | 10 |
| Total | 2,513 |

These flags were retained deliberately. They include partial construction pieces, grouped
objects, possible state/stage grids, labels mixed with art, modular floors/walls/water,
building entrances and actor sheets. A usable static stamp does not by itself establish
autotiling, walkability, animation semantics or functional collision. Whole-pack profiles,
held-out packs, owner acceptance and first-paint timing remain open under T17.34.

## Verification

All 30 analyses completed. There are 13,059 image entries: 12,644 active, comprising
6,070 confirmed, 4,061 auto-detected and 2,513 needing review; 415 are unused. Detector
confidence was not increased to produce these statuses. All 6,070 confirmed sprite hashes
and resulting metadata were independently checked against the saved review decisions.
Eight original archives and 232 accepted direct-folder files were rehashed and unchanged.

Validation results and native scene checks are recorded with the machine-readable ledger.
Three real-pack projects were generated and validated, with seven terrain checks and 32
dock placements; their renders were inspected. Additional native probes checked the pivots,
scene availability and absence of blocking polygons for all 915 confirmed scenes in the
Western and plant projects, including 75 tools/weapons. The dungeon project's 42 generated
fire frames passed exact rectangle, padding, style separation and playback-speed checks.
The Python unit run passed 2,567 cases with three skips; its sole schema-copy mismatch was
fixed and all four registry checks passed on rerun. All 2,568 unique unit cases therefore
passed across those runs. The GUI run passed 721 cases; the two sample-profile export
mismatches were fixed, then both passed in a 73-case focused unit/GUI rerun. All 723 unique
GUI cases passed across those runs. The final six assets-only integration cases and the
Godot test suite passed. Ruff lint/format, mypy
(214 modules) and whitespace checks also passed.
The private contact sheets and runnable study outputs are under
`F:\rpggen_scratch\metadata_confirmation_20261028`.
