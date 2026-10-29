# Answer-key review, 2026-10-28

The owner's review list contained 26,408 image entries in 1,670 groups across 25 packs.
The systematic pass now leaves four grouped game-design choices covering 44 entries:

| Choice | Entries | Suggested interpretation |
| --- | ---: | --- |
| Soil-attached vegetables: harvested items or planted crops | 2 | Items |
| Fruit-tree stage sheets: scenery or orchard crops | 23 | Scenery |
| Elemental floors: ordinary ground or gameplay hazards | 18 | Ordinary ground |
| Boss beam: visual effect, projectile or stationary hazard | 1 | Visual effect |

The local review opens at <http://127.0.0.1:8765/>. Start it with:

```powershell
.venv/Scripts/python.exe tools/answer_key.py serve --out F:/rpggen_scratch/answer_key
```

The page displays these four choices first. The complete group browser remains available
under **Browse the full answer key**. Choices and optional notes save separately in
`review_decisions.json`; suggestions are not selected or submitted automatically. Saving a
choice records the owner's intent for subsequent corrections; it does not change game
behavior or fit calibration immediately.

## Applied work

The saved pass contains 638 explicit correction records affecting 629 distinct entries in
seven packs. These cover alternate-size exclusions, exact pixel duplicates, building kits
versus whole buildings, interiors, modular atlases, terrain ends and unverified animation
metadata. They have been applied to the private answer-key corrections with per-entry reasons
and backups. Original drafts and all 12 existing owner group marks were preserved byte for byte.

Every original entry has a recorded disposition:

| Disposition | Entries |
| --- | ---: |
| Family screened; reference retained | 21,231 |
| Technical issue or catalog convention resolved | 5,103 |
| Game-design choice | 44 |
| Changed or retired generated reference archived | 30 |

26,378 original entries match the current catalog by decoded picture pixels and source/variant
identity. The other 30 are changed crops/derived images or retired generated helpers. Those
differences remain documented in the agent's technical ledger, outside the owner's questions.
One inventory fingerprint difference is a text-file name encoding change; no image source
fingerprint changed.

A separate current-key corpus contains 26,334 entries, excluding the 44 choices and 30 changed
references. This corpus retains inherited draft fields as well as explicit corrections. It
is not independently certified ground truth and has not been used to raise confidence or fit
calibration. New catalog entries outside the original review set are not covered by this pass.
Native frame, collision and terrain certification, held-out validation, and the rest of T17.34
remain open. The reduced owner queue is complete; those engineering checks stay with the agent.

## Crash fix and verification

Both interrupted Modern Farm imports preceded out-of-memory failures. The first native dump
records a system commitment peak within about 6 MiB of its 65.09 GiB limit. The importer retained
a full-sheet NumPy mask for every extracted island, across up to eight sheets concurrently;
some source sheets contain 20–46 million pixels. `sheet_parts.islands` now processes component
bounding boxes and returns owned, trimmed masks.

A controlled 484-object comparison retained 126,877,696 bytes before the fix and 484 bytes
afterward, with matching pixels and coordinates in 100 additional deterministic cases. The
Modern Farm import completed in 151.88 seconds: 8,077 source files, 9,464 catalog assets,
1,686 generated files, and 5.71 GiB peak worker private memory. No Windows settings changed.

Validation: 2,575 unit tests passed and three skipped; Ruff, formatting (497 files), and mypy
(214 source files) passed. All 26,334 current-corpus keys resolve to current catalog assets.
Browser checks covered the four image sheets, the full-key link, explicit choice/note saving
and reload persistence on an isolated fixture; the live queue starts with no choices submitted
by the agent. The review page had no browser console errors.

Private pictures, catalogs, contact sheets and machine-readable evidence remain outside Git
under `F:/rpggen_scratch/answer_key/systematic_review_20261028/`. The successful import's output
is under `D:/rpggen_crash_verification_20261028/`; crash evidence is under
`C:/Users/dferr/.codex/diagnostics/crash-repair-2026-10-28/`.
