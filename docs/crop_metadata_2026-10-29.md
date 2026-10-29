# Field-crop metadata certification — 2026-10-29

This pass adds ten source-bound crop-art certifications, restores a missing garlic sprout,
excludes neighboring-row residue, and fixes rendering when saved crop data and available art
have different stage counts. The actual saved owner choices remain unchanged. The earlier
ledger falls from 2,465 to **2,455 unresolved entries** by art disposition; broader T17.34 and
release requirements remain open.

[JSON evidence](crop_metadata_2026-10-29.json) records source/pixel hashes, preserved references,
native checks and resources. Private evidence is under `D:\rpggen_crop_terrain_metadata_20261029`.
No pack art is committed.

## Source review and saved choices

All ten strips from *Farm Tileset – Pixel Art*, `farm/1.png`, were visually inspected against
the whole source image. The complete source remains SHA-256
`df333ba9f08d137f17715e4b60ac35f9824d3bd0e20677fbf459de8ee791800a`.
The layout is bound to those exact bytes. Visual names are reviewer-assigned, editable labels;
the source file itself does not name the plants.

| Visual label | Stages | Native frame |
|---|---:|---|
| corn | 4 | 48 × 96 |
| cabbage | 3 | 48 × 48 |
| chili_pepper | 5 | 48 × 96 |
| strawberry | 5 | 48 × 96 |
| carrot | 4 | 48 × 96 |
| tomato | 5 | 48 × 96 |
| watermelon | 3 | 48 × 96 |
| cotton | 5 | 48 × 96 |
| garlic | 4 | 48 × 96 |
| potato | 3 | 48 × 96 |


Garlic previously began at the second source sprout. The canonical strip now includes its
first sprout and has four stages. The stable asset ID still ends in `#crop432_384` so saved
projects keep their references. Three frame rectangles omit their top four canvas rows, then
pad them back at the same offset: 51 opaque pixels belonging to neighboring rows are excluded
from tomato, garlic and potato frames. Native frame size, plant pixels and bottom-center pivot
conventions are preserved.

The owner's H1 **Harvested produce (ITEM)** choice specifically covers `o4_448` (the isolated
potato tuber) and `o580_410` (the isolated bulb). Both remain confirmed ITEM assets with exactly
the same fields and image paths. The potato tuber is not added as a planted stage; potato
retains three green growth stages. Other isolated produce stays outside the crop rectangles.
The standalone garlic sprout remains available as its existing decoration alternative.

H2 **Use orchard crops (CROP)**, H3 **I want to define hazards for my game**, and H4
**Visual effect (EFFECT)** remain unchanged, with empty notes on all four answers. This pass
does not enable hazards or redefine orchard behavior. Saved choices and calibration remain
byte-identical, with hashes recorded in the JSON evidence. This source overlaps the owner's
two ITEM choices, so variant-level preservation was checked rather than assuming disjoint files.

## Confirmation and compatibility safeguards

`crop_layouts.json` records exact source rectangles and padding offsets. The renderer replaces
heuristic crop strips only for the reviewed source hash, keeps all non-crop parts, and uses
the existing ten crop IDs. Source edits cannot inherit these layouts by name.

The explicit `crop_art` record kind accepts only growth-strip geometry, stage count, native
pivot, known reviewed-layout tags and a visual produce label. Incomplete strips, other roles,
animation fields, collision, timing and regrowth fields prevent confirmation. Exact pre-review
facets, source hash and normalized strip pixels must still match. Detector confidence remains
0.6. User overrides retain priority. Days, seasons, regrowth, yields, prices and consumption
effects remain editable game defaults, not certified artist-authored metadata.

An early implementation changed logical helper paths while invalidating the render cache.
The final implementation keeps the original project image paths and review keys, while
physical cache filenames include the layout fingerprint. A stale pre-review cache therefore
cannot hide new rectangles or padding. All catalog IDs and project image paths are preserved;
all **590 current review keys** for this pack resolve. Every non-crop catalog entry is unchanged.
The original failed compatibility iteration remains private evidence and is not the final result.

New crop names and garlic's extra frame do not rewrite stored plans. A stored plan with custom
days/prices is byte-equivalent after planning against the new facts. At runtime, `RpgCrop`
maps logical stages over available art only when the counts differ; a saved three-stage garlic
still displays the fourth, ripe native frame. Matching counts keep their requested frame.
The logical stage and saved gameplay values remain unchanged.

## Validation

Fresh final analysis confirms all ten decisions and passes header/strip validation for **583
active images**. This validator reports animation frames separately; these crops are growth
strips, with **41 reviewed stages**, not animations. All source rectangles and padded output
pixels match their explicit layouts.

Native Godot probes use the production farm crop recipe to build and serialize ten crop scenes.
All 41 imported stage images match the reviewed RGBA pixels, native dimensions and pivots.
Unripe and withered crops do not emit a harvest request; ripe crops do. The old three-stage
garlic configuration reaches its final native frame without changing its logical stage.

A complete assets-only project also builds and validates. Its catalog preserves the ten
confirmed crops, both owner-selected ITEM assets and their stable image paths; generated crop
strip pixel hashes match the reviewed outputs. Its two messages are informational ASSET-021
(no license file in this pack) and VAL-032 (an assets-only project was not played or test-exported).
No generated maps or games were used to judge the artwork. The farm crop scenes are tested
separately; this pass does not claim a new assets-only crop-placement workflow.

The full Python unit run passes **2,627 tests / 3 skipped** in 708.02 seconds. The final focused
cache-path, crop, metadata, sheet and coverage checks pass **58 tests** after the cache-path fix,
including a stale-cache regression. The Godot suite passes **1,109 tests / 0 failures / 0 script
errors**, retaining its same 53 known fixture/negative engine diagnostics and 28 push diagnostics.
Ruff, formatting and mypy (218 modules) pass.

Final fresh analysis peaks at about 0.7 GiB descendant private memory, and assets-only generation
at about 1.3 GiB, under the 8 GiB guard. No guard stops or crashes occur.

The loose wall/floor composites and road poses reviewed during terrain triage still need
source-specific grids, segmentation, connectivity and material decisions. No terrain entry
is promoted merely because a cut image or a build passes. Remaining ledger blockers are building
133, segmentation/state 2,012 and terrain 310. This is a ledger delta, not a fresh import of all
30 packs. Independent calibration labels, the remaining semantic metadata and qualified/human
release requirements remain open; no confidence table is published.

The subsequent [terrain, building and segmentation pass](terrain_building_segmentation_2026-10-29.md)
records the next 12 ledger dispositions and the remaining 2,443 entries.
