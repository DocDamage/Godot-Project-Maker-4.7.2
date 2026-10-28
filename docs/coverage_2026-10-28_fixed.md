# Coverage fixes and repeat study: 2026-10-28

Historical snapshot. The [subsequent 9,478-entry screening](coverage_2026-10-28_review.md)
records further corrections and supersedes the remaining-entry counts below.

**All 27 concrete errors from the original 109-entry review are resolved.** The same 30 inputs were analyzed again. The 55 originally accepted field checks still agree. Ten real-pack projects generated and validated, with 20 terrain checks reporting no holes or wrong tiles and 75 dock placements. Character-only packs have no terrain checks; their actors were placed and rendered.

Full evidence: [repeat-run JSON](coverage_2026-10-28_fixed.json). The [original study](coverage_2026-10-28.md) and its measurements remain available. The repeat uses the same input manifest, normal pack IDs and isolated profiles/settings, with the fixes in the uncommitted working tree. The JSON records source-code hashes, per-entry resolutions, per-pack counts, editor results and unchanged input hashes.

## What changed

| Finding | Fix and verification |
|---|---|
| COV-01: false roles | Named furniture/props are no longer overridden by the house silhouette heuristic; furniture means DECORATION, keys mean ITEM. Thirteen independently reviewed region corrections are bound to full source-image hashes plus region IDs; only reviewed fields are supplied. User overrides retain precedence. The cottage, stove, pump, table, sacks, sign, barrel, stump, cliff and beach-block checks pass. |
| COV-02: non-art used as assets | Coupons, instructions and animation legends are excluded before object cutting; unused images cannot seed terrains. Numbered tileset-template names are recognized. The sheet label B is unused, and the How To image no longer makes a terrain atlas. |
| COV-03: animation layouts | Added a reader before generic island cutting. The BDragon legend identifies 80px action rows: 11 animated enemies replace over 1,100 individual objects. Verified top-down layouts retain their view even when they have jump animations. Modern Interiors idle/run strips use 16x32 cells and named directions; the RPG Maker sheet uses character variants. The small dungeon pack has one actor with directional walks instead of loose ITEM frames and idle-only GIFs. |
| COV-04: fragmented battlers | Recognized whole RPG-style battler pictures are retained as ENEMY sprites with a single idle frame, including their attached effect artwork. Static battlers also produce usable enemy scenes. No detached dragon-flame props remain. |
| COV-05: mixed/house atlases | The complete folder name supplies layout clues even when the pack ID truncates them. Named house atlases are cut instead of being forced into an anonymous RPG Maker grid; ordinary unnamed B-E sheets retain their existing handling. p03/p04 now expose hundreds of parts; p11-p13 expose individual buildings/props. Unnamed roles and terrain meaning still require review; this is not a claim that every region is correct. |
| COV-06: probe/report corrections | LPC Floors' 128 errors were false perimeter constraints in the probe: empty exterior corners are unconstrained when painting ignores empty terrain. Interior corner joins are still checked, and a synthetic corner-terrain regression passes. The pink isometric patch was legitimate textured Elements art, not leaked transparency; the solid FF00FF background is correctly removed. The report is corrected, and a test preserves that distinction. |
| COV-07: lost map layer | Tiled atlases are protected from generic tile-copy removal because map coordinates refer to their exact layout. The dungeon's Windows layer is retained and TILE-009 no longer appears in the 30-pack run. |
| COV-08: packaging/licenses | A sole RAR inside a wrapper opens as a pack; archive-only wrappers with multiple choices now identify the archives to select instead of silently yielding zero art. Original wrapper context survives for parent-license discovery, including Vendor License.txt names. Both BDragon licenses are now detected. |

The editor probe now supports character-only projects without inventing ground. Its screenshot camera uses actual sprite bounds so large battlers are not cropped. A 512x480 synthetic battler regression checks placement and verifies the rendered art does not touch the image edge.

## Counts before and after

| Measurement | Original | Repeat |
|---|---:|---:|
| Inputs / input image files | 30 / 443 | 30 / 443 |
| Catalog image entries | 13,924 | 13,858 |
| Active entries | 13,645 | 13,545 |
| Confident entries | 3,974 (29.1%) | 4,067 (30.0%) |
| NEEDS_REVIEW entries | 9,671 | 9,478 |
| Unused entries | 279 | 313 |
| Known errors remaining in the reviewed correction set | 27 | 0 |

Counts change in both directions: repairing character grouping removes bogus islands, while decoding previously unread mixed sheets adds real regions. Confidence is not accuracy. The remaining 9,478 entries must not be treated as confirmed merely because the known errors were fixed. The original 27 unresolved sample entries do not become a fully audited answer key; their changed sources/replacements are documented in the JSON.

| ID | Input | Active before → after | Needs review before → after |
|---|---|---:|---:|
| p01 | CuteSCKR / Farm Tileset - Pixel Art | 583 → 583 | 564 → 564 |
| p02 | CuteSCKR / Medieval Fantasy Town Pixel Art Tileset Pack | 688 → 688 | 675 → 675 |
| p03 | CuteSCKR / Medieval Castle Fantasy - Pixel Art Tileset | 12 → 482 | 9 → 476 |
| p04 | CuteSCKR / Medieval Fantasy Dungeon & Prison Pixel Art Tileset Pack | 11 → 575 | 7 → 566 |
| p05 | CuteSCKR / Modern Interior Pixel Art Tileset | 1,263 → 1,263 | 1,245 → 1,245 |
| p06 | CuteSCKR / Cyberpunk City Tileset | 1,300 → 1,300 | 1,275 → 1,275 |
| p07 | CuteSCKR / Wild West Pixel Art Tileset | 1,142 → 1,142 | 1,112 → 1,112 |
| p08 | CuteSCKR / Survival Island Pixel Art Tileset | 520 → 520 | 494 → 494 |
| p09 | haydeos / Fantasy Forest RPG Maker Tileset | 90 → 90 | 78 → 78 |
| p10 | haydeos / Fantasy Houses Tileset | 35 → 35 | 34 → 34 |
| p11 | haydeos / Dieselpunk Houses | 1 → 17 | 1 → 0 |
| p12 | haydeos / Elven Forest Asset Pack | 2 → 42 | 2 → 31 |
| p13 | haydeos / Great War RPG Maker Houses | 2 → 40 | 2 → 0 |
| p14 | SakPix / Cozy Farming Village Asset Pack | 346 → 346 | 36 → 36 |
| p15 | SakPix / Medieval village town | 509 → 508 | 161 → 160 |
| p16 | SakPix / Dungeon Asset Pack | 393 → 393 | 307 → 307 |
| p17 | SakPix / Magic Forest Asset Pack | 1,142 → 1,142 | 471 → 471 |
| p18 | SakPix / Cyberpunk Pixel Art Asset Pack | 1,282 → 1,282 | 820 → 820 |
| p19 | SakPix / Snowy Village Pixel Art Asset Pack | 710 → 710 | 203 → 203 |
| p20 | RPGMAKERASSETS / lpc-floors.zip | 1 → 1 | 1 → 1 |
| p21 | RPGMAKERASSETS / lpc-jungle-v2.zip | 88 → 88 | 34 → 34 |
| p22 | RPGMAKERASSETS / Modern_Interiors_Free_v2.2.zip | 813 → 768 | 813 → 764 |
| p23 | RPGMAKERASSETS / [FREE] Mini Dungeon Tileset.zip | 26 → 3 | 25 → 2 |
| p24 | RPGMAKERASSETS / craftpix-net-169442-free-2d-top-down-pixel-dungeon-asset-pack.zip | 73 → 73 | 67 → 67 |
| p25 | Screaming Brain / Isometric Tiles - Floor Pack (Large 256x128) | 504 → 504 | 0 → 0 |
| p26 | Screaming Brain / Isometric Tiles - Town Pack | 873 → 873 | 0 → 0 |
| p27 | Nemo / Goblin Gang | 3 → 3 | 3 → 3 |
| p28 | Nemo / Dragon Evolutions | 6 → 3 | 6 → 0 |
| p29 | BDragon / Topdown Monsters Part 1 | 1,167 → 11 | 1,166 → 0 |
| p30 | BDragon / Pixel Tree All | 60 → 60 | 60 → 60 |

## Editor checks

Godot 4.7.2, assets-only generation, the editor's terrain painting and dock placement, then inspected renders. A completed probe alone is insufficient: the table reports its measured topology and placements.

| Pack | Generation / probe | Terrain checks | Holes | Wrong tiles | Placed scenes |
|---|---|---:|---:|---:|---:|
| p01 | passed | 2 | 0 | 0 | 12 |
| p03 | passed | 3 | 0 | 0 | 11 |
| p04 | passed | 3 | 0 | 0 | 12 |
| p20 | passed | 1 | 0 | 0 | 10 |
| p22 | passed | 4 | 0 | 0 | 13 |
| p23 | passed | 1 | 0 | 0 | 1 |
| p24 | passed | 3 | 0 | 0 | 12 |
| p25 | passed | 3 | 0 | 0 | 0 |
| p28 | passed | 0 | 0 | 0 | 2 |
| p29 | passed | 0 | 0 | 0 | 2 |

The complete battler pictures, animated enemies and small dungeon character were visible in the renders. The renders also leave the remaining semantic review work visible: a structurally valid terrain can still use an unsuitable region from a mixed sheet (for example, the striped interior construction pieces in p22). Zero topology errors do not certify visual suitability.

## Validation

* Full unit suite: **2,555 passed, 3 skipped**.
* Focused coverage regressions plus naming tests: **97 passed**; the coverage regression module has 16 cases.
* GUI worker, pack-info, audit-edit and farm-pack checks: **43 passed**.
* Assets-only editor integration suite: **6 passed**, including corner boundaries and large battlers without ground.
* Ruff lint and format checks passed; mypy passed on 213 source files.
* The original 109 entries were compared, and all six updated contact sheets were visually inspected. All 27 corrections passed their field or replacement checks; all 55 previously accepted field checks were preserved.
* Rehashed eight original archives (including the archive inside the tree-pack wrapper) and 232 accepted files of direct folder inputs. Every hash matched. No source art changed.

## Corrections and remaining work

The original report's pink-mask finding is withdrawn after inspecting the source Elements sheet. Its LPC perimeter finding is a probe bug, not an asset-reader failure. The original license count also conflated 17 ASSET-021 messages with unknown IDs: there were 18 unknown license IDs originally, and 16 now. Two missing parent licenses were fixed; absent or unread license evidence remains unknown.

Complete per-pack audits, owner approval, true first-paint timings, calibration/vision accuracy measurement and genuinely held-out release validation remain open. The fixes do not supply invented values for those gates, and unreviewed profiles were not promoted as complete answers. The shipped region data is a partial reviewed correction set, not a whole-pack certification.

Private catalogs, inventories, scripts, projects and images remain under `F:\rpggen_scratch\real_pack_coverage_20261028_fixed\`. Only code, synthetic tests, metadata and reports enter this repository.
