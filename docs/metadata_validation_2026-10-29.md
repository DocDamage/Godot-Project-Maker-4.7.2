# Metadata validation and calibration safeguards, 2026-10-29

The saved choices remain authoritative: harvested vegetables are ITEM, fruit trees are CROP,
elemental floors receive individual game-specific hazard settings, and the beam is EFFECT.
All 44 affected entries match those roles. The choices file is unchanged. No hazards were
enabled and no additional answers were submitted.

## Validation results

This pass checks saved catalog snapshots for the 25 answer-key packs, using the newer orchard
snapshot for Farm RPG. It does not rerun every importer or establish new semantic ground truth.
The [machine-readable report](metadata_validation_2026-10-29.json) records scope and per-pack
counts. Artwork and detailed per-entry results remain outside Git.

| Check | Result |
| --- | ---: |
| Active images checked against image headers | 13,612 |
| Animations checked | 2,693 |
| Animation frame regions checked | 14,137 |
| Geometry/timing failures | 0 |
| Original corpus keys resolved | 26,378 / 26,378 |
| Saved-choice role entries matching | 44 / 44 |
| Stored complete metadata decisions rechecked against sprite pixels and static geometry | 6,070 / 6,070 |
| Distinct source files rehashed for those decisions | 174 / 174 unchanged |

The geometry checks cover missing image sources, grid frame bounds, explicit rectangles,
trimmed-frame offsets, growth-strip dimensions, positive finite playback speeds and durations,
duration/offset lengths, and active-frame indices. They read image headers without decoding
full sheets. The separate static-decision check decodes one sprite at a time; its sampled
peak process private memory was about 677 MiB. There were no missing source files or changed
pixel hashes in that check.

The CLI also passed against the real Farm RPG and Warped snapshots. Generated orchard strips
now score through their original inventory source keys, keeping their source identity after
the renderer writes a helper PNG. Existing generated-path corpus keys still work.

These results establish structural validity and consistency with stored decisions. They do
not independently verify animation names, artist-authored timing, terrain topology, building
entrances, collision design, or every inherited draft label. No new assets were promoted to
CONFIRMED by these checks.

## Calibration safeguards

Private score reports now identify the fields reviewed for each picture and whether the
observation is eligible for calibration. Legacy contact-sheet group marks are preserved;
they are not automatically expanded into full-field approval. A role-only owner choice does
not certify its frame layout, animation names, or other metadata.

For calibration, a corpus entry must explicitly list `reviewed_fields` per source key using
the scoring field names: `usage`, `role`, `frame`, `anims`, `cell`, `margin`, `separation`.
Coverage must include every scored field and the required geometry fields for its usage.
Those required fields must have expected values; listing their names as reviewed is insufficient.
The individual source hash must still match the corpus fingerprint. Already confirmed assets,
profiles, learned decisions, overrides, folder rules, applied region corrections and generated
helpers are excluded from detector calibration. Generated helpers need pixel-bound label
support before they can train a calibration table.

Calibration version 3 counts each source byte hash once per bin. A miss in any checked region
counts against that source. Leave-one-pack-out training excludes every source hash seen in
the held-out pack, including copies in other packs. Different encodings or visually similar
images are not detected as duplicates by this byte-hash grouping; it is not a claim of complete
statistical independence.

Writing a table is refused when packs are missing, no supported bins exist, or held-out sure
predictions lack a 95% Wilson lower bound of at least 99%, overall and for each publisher with
sure predictions. Sure bins without their own held-out support are removed, including generic
fallback bins that the folds never exercised. Successful writes are atomic. Version 2 tables
are no longer loaded because
their sample counts could treat correlated regions as independent evidence. The shipped empty
table remains byte-for-byte unchanged; unknown readers/bins retain their existing confidence.

The current corpus has **zero calibration-eligible observations**. Its inherited draft fields
and 44 owner-reviewed role entries therefore cannot raise confidence. Feeding the cached reports
through the production fitter exercised this rejection and left the shipped table unchanged.
Synthetic regression cases also check successful supported publication and rejection of failed
held-out results. This pass makes no 99% real-pack accuracy claim.

## Running the structural check

Use a catalog and its saved generated-file mapping, with one root per pack:

```powershell
.venv/Scripts/python.exe tools/validate_metadata.py --catalog PATH/catalog.json `
  --root "PACK_ID=PATH/TO/EXTRACTED/PACK" --generated PATH/generated.json `
  --out PATH/validation.json
```

The command returns 0 for a passing check and 1 for recorded geometry failures. It writes only
the requested report; catalogs, source art and owner choices are not changed. A saved report
must be checked again after its catalog or images change.

Private evidence is under `D:/rpggen_metadata_validation_20261029/`: `geometry.json`,
`scoring.json`, `static_decisions.json`, `owner_roles.json`, `safeguards.json`, the CLI reports,
and `fit_guard/fit_report.json`. Broader semantic certification, independently reviewed labels,
fresh held-out real-pack evaluation, whole-pack profiles and local-vision qualification remain
open under T17.34.

## Verification of these changes

The full Python unit run passed 2,593 tests with three skips. After the final source-binding
and required-value guards, the focused accuracy/calibration/metadata/answer-key run passed
45 tests. These runs cover all 2,595 unique current unit cases; lint, formatting and mypy
(217 source modules) also pass. Regression cases cover supported table publication, rejected
held-out results, unchanged tables on rejection, source overlap, correlated regions, changed
sources, missing expected values, generated source aliases and read-only CLI failure reports.
