# Actor-art metadata certification — 2026-10-29

This follow-up certifies the **23 previously flagged actor-art entries** in Modern Interiors
Free v2.2, fixes four mislabeled seated direction pairs and a false commercial-license grant,
and verifies the actual generated character scenes. The owner's saved choices and the empty
calibration table remain byte-identical. T17.34 remains open.

The [JSON evidence](actor_metadata_2026-10-29.json) records the entry IDs, source/pixel hashes,
approved frame sizes and directions, native checks, resource measurements and test results.
Private sources and outputs remain under `D:\rpggen_actor_metadata_20261029`; no pack art is
committed. The original archive still hashes to
`1e38aae8896ec14764a5484a6d6a90a5026c233560ee97865dc8751053fba7f0`.

## Reviewed scope and corrections

The source images were visually inspected at whole-cell scale, including all four characters
in the RPG Maker MV sheet. The 23 decisions cover 20 distinct source images:

| Art | Entries | Native frame | Reviewed grouping |
|---|---:|---|---|
| Phone | 4 | 16 × 32 | Nine front-facing frames each |
| Sit / sit2 | 8 | 32 × 32 | Six right-facing and six left-facing frames each |
| Sit3 | 4 | 16 × 32 | Six front-facing and six back-facing frames each |
| RPG Maker MV characters | 4 | 48 × 96 | Separate three-column character blocks; down, left, right, up rows |
| Legacy idle, RPG Maker walk, horizontal run | 3 | 16 × 32 | Four idle poses; four three-frame direction rows; four six-frame groups |

The `sit3` reader previously labeled the front/back groups as right/left. It now produces
`sit3_down` / `sit3_up`, with the second group starting at column six. Existing side-facing
sit/sit2 layouts keep their 32-pixel width. Three legacy sheets lacked an explicit origin;
their reviewed decisions now supply the same editable bottom-center pivot convention as the
other actor scenes. Native MV frames retain their 48 × 96 canvas and padding.

The explicit `actor_art` confirmation kind approves NPC art cells, facing and sequence.
It permits only the reviewed art fields, whole grid cells, known presentation animation names,
valid source bounds and cells inside the selected RPG Maker character block. Missing tags,
other roles, external sources, trimmed rectangles, invalid cells, unsupported rates and
collision/movement/combat fields prevent confirmation. Exact pre-review facets, original source
SHA-256 and normalized RGBA pixels must still match; user edits and installed profiles retain
priority. Detector confidence remains 0.5 or 0.6.

The records explicitly identify bottom-center pivots, looping and 1/6/8 fps playback as
**editable importer defaults**. No artist-authored timing, collision, autonomous movement,
interaction or combat behavior is certified. These confirmations do not become independent
calibration labels or evidence of a 99% accuracy rate.

## License metadata failure

The shipped `LICENSE.txt` permits non-commercial projects and explicitly disallows commercial
projects. The old positive-permission expression matched the word “commercial” inside
“non commercial” and could also match “can” inside “can't.” The importer consequently recorded
`commercial` for this free pack.

Custom prohibitions now produce `noncommercial`, shown as **Non-commercial use only** in the
existing license selector. They are not relabeled as a Creative Commons license. The positive
grant scan normalizes non-commercial wording so it cannot grant commercial permission on its
own. Tests cover straight/curly apostrophes, explicit prohibitions, non-commercial-only terms,
positive permission for both commercial and non-commercial use, resale restrictions and license
file priority. Existing user overrides remain authoritative.

A matched-document comparison runs both the old and new detectors on the same seven available
license documents across the original 30 inputs: only p22 changes. This is a document-detector
comparison, not a fresh import of every pack. Some cached pack licenses come from reader facts
instead of documents; those are recorded separately rather than treated as detector regressions.

## Fresh and native validation

Fresh analysis confirms all 23 decisions at unchanged confidence. All 20 sources are rehashed
and every decision is checked against its input and pixel guards. The current pack's **34 active
images, 104 animations and 492 playback frames** pass header, bounds and timing validation.
Seven tile-sheet entries remain NEEDS_REVIEW, and four primary multi-source idle/walk actors
remain AUTO_DETECTED; they receive no new certification in this pass.

The new decisions contain **72 animations, 300 playback frames and 268 distinct source cells**.
A private native gallery builds SpriteFrames and serialized scenes, checking frame counts,
rates, looping, native dimensions and pivots. All 300 exported normalized RGBA frame hashes
match the reviewed source cells.

An actual **assets-only** project then builds and validates successfully, without a game,
placeholder art or smoke-play claim. Each of the 23 entries appears in
`rpggen/character_index.json`. Loading those actual generated NPC scenes checks their pivots,
unit visual scale, animation properties and all 300 exported frame images again: zero failures.
Project header validation also passes for 34 active images and 492 playback frames. The only
reported issue is informational VAL-032: an assets-only project was not played or test-exported.
The first private dock-probe fixture incorrectly used the object index; the corrected character
index probe is the successful result counted here. No product fix was needed for that harness.

Analysis and project generation use an 8 GiB descendant-private-memory guard. Fresh analysis
peaks below 6 GiB; the assets-only generation also remains below 6 GiB. No guard stops or import
crashes occur. These are sampled process measurements, not total Windows system commitment.

Full Python unit suite: **2,620 passed / 3 skipped** in 756.28 seconds.
The final focused run passes **83 tests**, including the final resale-wording guards and three
additional cases after the full run. All **2,623 unique current unit cases** pass across those
runs. The pack-license GUI tests pass (4). Ruff, formatting (508 files) and mypy (217 modules)
pass. The two native art probes and the assets-only project validation pass. No repository
GDScript runtime or template code changes in this pass.


## Saved choices and remaining work

The live saved values remain H1 **Harvested produce (ITEM)**, H2 **Use orchard crops (CROP)**,
H3 **I want to define hazards for my game**, H4 **Visual effect (EFFECT)**, with empty notes.
The new sources have zero source-hash overlap with those 44 selected entries. Hazards remain
individually authored. Saved choices SHA-256 remains
`52294b9655fb46c2165751c05cb0d2245baf5f798d3dbcd3965a224458901128`; the shipped calibration
table remains `73abface1d895568205ddc41c917dbfb0558daf7e6ca95e0ca2fcaf1a269b588`.

The earlier [ledger delta](semantic_heldout_2026-10-29.md) falls from 2,488 to **2,465 unresolved
entries** after these 23 art dispositions: crop 10, building 133, segmentation/state 2,012 and
terrain 310. This closes the previously flagged actor-art bucket, not every actor or gameplay
question in the library. It is a ledger delta, not a new all-30-pack status measurement.
Independent calibration labels, the remaining semantic metadata and the human/qualified-sample
release requirements remain open.

Follow-up: the [field-crop pass](crop_metadata_2026-10-29.md) records ten further art dispositions
and the updated 2,455-entry unresolved ledger. The actor results above retain their original scope.
