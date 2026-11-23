# Terrain, building and segmentation certification — 2026-10-29

This follows the [crop-art pass](crop_metadata_2026-10-29.md). It adds 13 source-bound
art/placement decisions and resolves 12 entries of the earlier metadata ledger. One grouped
entry becomes two static poses. The remaining ledger is **2,443**: building 123,
segmentation/state 2,011 and terrain 309. This is a disposition delta, not a fresh import of
all 30 packs. No independent accuracy rate or release-gate completion is claimed.

The owner's actual saved choices remain in force: harvested produce is ITEM, fruit trees are
orchard crops, hazards are authored individually for the game, and the beam is EFFECT.
No hazards are enabled by this batch. Calibration remains unchanged.

## Buildings

Ten previously flagged whole buildings on Fantasy Houses Tileset now have exact-source,
input-facet and rendered-pixel guards. Their native canvas, bottom-center origin, stable IDs
and logical project image paths are preserved. Each receives a visually located front door
and an editable rectangular main-body collision footprint. The pivot and footprint are
authored placement defaults, **not artist-authored physics**. Destinations, interior maps,
alternate entrances and gameplay rules are outside this certification.

One house included 23 orphan pixels from its neighbor in the top eight rows. An exact-source
mask removes those pixels while retaining the original canvas and all main-house pixels.
Versioned physical render caches prevent stale output without changing review keys.

A builder failure was also fixed: extracted assets discarded explicit door metadata and
fell back to the frame's bottom center. The schema now carries an optional door point
through detected facets, profiles and nullable project overrides. Object entries pass that
point to the scene recipe; the recipe version changes so regeneration updates existing output.
An unreviewed barn touching the source sheet's bottom edge remains outside these ten decisions.

## Segmentation

The grouped cats in Medieval Fantasy Town's `n18#o435_192` are two distinct static poses.
Their disjoint native rectangles contain 322 and 376 painted pixels. Both receive a native
frame, bottom-center pivot and single-frame idle presentation. No walking, production or
combat behavior is certified. The old parent ID and image remain available as UNUSED with
the reason `segmented`, preserving old review references while avoiding a duplicate actor.

The segment reader rejects out-of-bounds or overlapping rectangles and unassigned painted
pixels. Its cropped arrays own their pixels, avoiding retention of full-sheet image buffers.

## Terrain

The LPC floors atlas is certified against its native 32×32 grid and its companion
`floors.tsx`: 40 source-authored rug styles with 13 corner patterns each, totaling 520
declared tiles. Certification binds the TSX bytes and interpreted terrain definitions as well
as the PNG, input facets and rendered pixels. A byte-only TSX edit must invalidate it even
when the interpreted image facets remain identical. Terrain names/material meanings are not
invented; non-blocking floor collision is an explicit editable placement default.

Regeneration now records automatic-review provenance and rechecks its guards instead of
inheriting a previous CONFIRMED status. Legacy catalogs on sources covered by built-in reviews
are rechecked too. Explicit saved overrides remain authoritative. This also prevents a removed
automatic record from retaining confirmation in catalogs saved with the new provenance field.

The source omits the two checkerboard corner patterns. They are neither synthesized nor
certified. The native painting check covers compact filled rectangles for all 40 styles;
it does not establish arbitrary topology, collision or navigation support for the whole atlas.

## Memory safeguards and validation

Validation encountered Windows commit exhaustion. The analysis prewarm and inventory pools
were configured to spawn up to eight workers, each loading application imports. A guarded
prewarm attempt reached 6,137,925,632 descendant-private bytes. Windows now uses bounded
threads for inventory reads and at most two threads for image analysis; POSIX keeps its
existing process pools. Catalog-equivalence, cache, cancellation and huge-image checks cover
the change. Huge images continue to be analyzed serially.

Concurrent host activity also consumed available commit: UnrealEditor was observed at
24.62 GiB private memory while total system commit was 60.35 of 61.12 GiB. No other application
was terminated and no Windows settings were changed. Interrupted validation logs are retained.
The private validation runner now checks system commit headroom and owns workers in a Windows
kill-on-close job, assigned before resuming them. A monitor allocation failure therefore
stops descendants too. An injected monitor failure verifies parent, child and grandchild
cleanup. Completed test cases are checkpointed across host-memory interruptions.

All 2,641 current Python unit cases are accounted for: **2,638 passed / 3 skipped** across 7
sequential checkpointed attempts, with no test failures. Host-memory guard stops are interruptions,
not passes. The final focused provenance/pool/catalog checks pass **161 tests**. The Godot suite
passes **1,110 tests / 0 failures / 0 script errors**, retaining the same 53 known fixture/negative
engine diagnostics and 28 push diagnostics. Ruff, formatting and mypy pass.

Fresh analysis validates all reviewed records at their unchanged detector confidence and checks 724
active image headers and ten animation frames. All original catalog IDs and project image
paths remain available; all 737 pre-change and 739 current source-relative review keys resolve.
These three inputs are outside the separate 25-pack owner-review queue. The 44 owner-selected
entries' sources have zero overlap with the new review sources, and saved choices/calibration are
byte-identical.

All three fresh assets-only projects build and validate. Native serialized scenes verify ten
building images, pivots, exact entrances/exits and body footprints; each footprint blocks its
body-center query while a radius-four probe clears all 13 front-approach samples. Both cat scenes
preserve their native image, pivot and single-frame idle. Every imported image matches the reviewed
normalized RGBA hash. The terrain resource matches all 520 independently parsed source assignments
and 40 colors; all 40 five-by-five rectangle paints have 25 cells, declared source art and matching
shared corner bits. Existing undeclared tiles retain no terrain assignment. The byte-only companion
drift fixture is withheld from confirmation on both fresh analysis and regeneration.

The private terrain probe initially called a TileSet method that belongs to TileData, returned a
script error and wrote an incomplete result despite exit 0. The final log review rejected that
result. The corrected probe requires its terrain section to finish, and the final acceptance check
rejects script errors and verifies all 520 cells and 40 styles. This harness error is not counted as
a product failure.

The checkpointed unit worker peaks at 983,408,640 descendant-private bytes; final assets-only
generation peaks at 1,629,454,336. Final import/build/native checks complete without guard stops.
These engineering checks do not establish a semantic accuracy rate or arbitrary terrain topology
support.

Machine-readable evidence is in [the companion JSON](terrain_building_segmentation_2026-10-29.json).
Private source art, native projects, checks and failed logs remain under
`D:/rpggen_terrain_building_20261029`; no pack art is committed. Independent calibration labels,
the remaining semantic ledger and qualified/human release requirements stay open.
