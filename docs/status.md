# Project status

Where rpggen stands against its build plan (`docs/spec/`), and what is left before `v1.0.0` is
tagged. Updated 2026-10-08, at commit `84f239b` on `main`. The detail of every finished card is in
[docs/dev/implementation_notes.md](dev/implementation_notes.md); this page is the summary.

## In one paragraph

Every feature card of milestones M1 to M12 is implemented and tested: 70 of the 71 cards of M12,
and every card of M1 to M11 that a program can do. Locally on Windows the unit and GUI suites
(1395 tests), the GDScript suite (479 tests) and the integration suite pass. **Nothing has been released and no tag
exists.** What remains is the 1.0 gate
(T12.66), and the work that only a person can do: the held-out pack runs (T10.09), the manual test
pass (T11.29, extended for M12), and the manual checks the earlier gates left open. The work
after the tag is planned: M13 (release 1.1.0) and M14 (release 1.2.0), below.

## Milestones

| Milestone | What it delivers | Status |
|-----------|------------------|--------|
| M1 Walking skeleton | CLI makes a project from a synthetic pack; headless validation | Done |
| M2 Asset intelligence | Safe archives, image analysis, adapters, classifier, catalog | Done; manual check open (real packs, below) |
| M3 Wizard and audit | The PySide6 wizard, audit grid, bulk edit, object cutter, profiles, sample pack | Done; usability timing open |
| M4 World placement | Layered starter map, object and building scenes, Y-sort, interiors | Done; editor check open |
| M5 Regeneration | Ledger, staging and promotion, TileSet merge, pack diffs, backups | Done; editor-open check open |
| M6 Shared systems | The runtime addon: state, maps, saving, items, dialogue, settings, UI | Done; the gate (T6.18) has no entry of its own in the notes, its checks run in every later suite |
| M7 Turn-based | Encounters, battle, rewards, the full smoke test | Done; gamepad check open |
| M8 Editor dock and terrain | Assets dock, overrides in the editor, terrains, validator, demo removal | Done; the gate (T8.09) has no entry of its own in the notes; the dock is in the manual pass (T11.29 rows 1 and 2) |
| M9 Action RPG | Player combat, enemies, hitboxes, HUD, smoke test | Done; feel and controller check open |
| M10 Release | Packaging, signing, diagnostics, docs, registry, export test | Done except T10.09 (held-out runs, human) and the T10.10 gate |
| M11 Pre-release | Wizard UX, sound, autosave, game over, second map, docs | Done except T11.29 (manual pass, human); T11.30 gate passed automatically |
| M12 Review follow-ups | Fixes, engineering, UX and 25 features (below) | 70 of 71 cards done; T12.66 (the gate) open |
| M13 Polish (1.1.0) | Ten wizard UX cards, seven feature improvements, three additions, the lock-and-key planner, world repair (below) | Started 2026-10-09 on the branch `m13` (not part of 1.0); 2 of 24 cards done |
| M14 Metroidvania (1.2.0) | The third archetype (below) | Planned 2026-10-08, starts after the 1.1 tag; 0 of 13 cards done |

## M12 in detail

**Part A, fixes (T12.01–T12.15).** All done: the Mapping and Audit layouts, hashing each pack
once, the tile size read from the packs, the strict CLI, exact editor-open detection, analysis
progress and cancel, skipped checks shown as skipped, safe save rotation, archive extraction
limits, the settings, data and cache folders, one settings store, git commits of only rpggen's
files and the pack-art choice, network timeouts, release hygiene.

**Part B, engineering (T12.16–T12.29).** All done: the layout regression test, parallel analysis,
the folder inventory cache, live Godot output, lean failed runs, the hardened Godot download, the
PySide6 6.7 / 6.11 matrix, error reports, one log location, view-models, the private accuracy
corpus, performance trends, the scriptable CLI, strict GDScript.

**Part C, UX (T12.30–T12.44).** All done: quit versus cancel, audit cards with audio and fonts,
the filter bar, pack cards, archetype cards with the pack's art, the sidebar with step status,
inline mapping candidates, the options summary, the map legend, the Results page's *Play* and
grouped warnings, the regeneration preview, one-click fixes, the system theme, the audit history,
the game's save and load screens.

**Part D, features (T12.45–T12.64 and T12.67–T12.71).** All done:

| Card | Feature | Card | Feature |
|------|---------|------|---------|
| T12.45 | Equipment | T12.57 | Contact sheet export |
| T12.46 | Shops | T12.58 | Conflict resolver |
| T12.47 | Party members (turn-based) | T12.59 | Learned rules |
| T12.48 | Quest journal | T12.60 | Custom recipes |
| T12.49 | Tiled and LDtk map import | T12.61 | Dialogue authoring dock |
| T12.50 | Frame sequences, more actions, eight directions | T12.62 | Lighting and day/night |
| T12.51 | Credits from pack licences | T12.63 | Linux and macOS packages |
| T12.52 | Web, Linux and macOS export presets | T12.64 | Minimap and world map |
| T12.53 | Random-encounter zones | T12.67 | Projectiles and ranged weapons |
| T12.54 | Event sequencer (cutscenes) | T12.68 | Shooter, turret and charger enemies |
| T12.55 | Input glyphs | T12.69 | Party followers on the map |
| T12.56 | Languages (game and wizard) | T12.70 | Keys, switches and gates |
| | | T12.71 | Battle depth: skills, MP, elements, statuses, AI |

**Part E.** T12.65 (documentation) is done: the user guide, both READMEs, the generated READMEs,
both changelogs, `00_START_HERE.md`, this page and the 16 screenshots (regenerated 2026-10-09,
with the pack cards, the regeneration preview, the conflict resolver and the Storage dialog).
T12.66 (the gate) is open; see below.

## After 1.0: M13 and M14

Planned on 2026-10-08 from the second review. Neither blocks the 1.0 tag: 1.0 ships from M12, M13
is release 1.1.0 (`docs/spec/M13_polish.md`) and M14 is release 1.2.0
(`docs/spec/M14_metroidvania.md`). Both are written under a post-release compatibility contract:
a 1.0 project regenerates without a prompt, its maps and `game/` folder untouched, its saves
loading, and no runtime script path breaks (moved scripts keep a shim for all of 1.x).

**M13 in detail.**

**Part A, wizard UX (T13.01–T13.10).** Audit review mode, the grid grouped by folder, a live
preview in the detail panel, *select similar* assets, the Mapping picker gallery, factory presets
and option dependencies, a remaining-time estimate, a project dashboard on the welcome view, a
first-run tour, accessibility and display scaling.

**Part B, feature improvements (T13.11–T13.17).** Shop quantities and sell all, one interior per
house, validator checks for every id, Zstandard layers, followers in the action RPG, custom sound
slots, audio waveforms and loop points.

**Part C, feature additions (T13.18–T13.20).** Recolour variants, quest and cutscene tabs in the
dock, a world of connected maps.

**T13.21** is the lock-and-key planner (pure Python, shared with M14); **T13.24** the world
repair (a generated map that nobody edited mends its own doors and reachability after a build,
with a backup; an edited map gets a one-click fix in the wizard and an undoable Fix in the dock);
**T13.22** the documentation and **T13.23** the 1.1.0 gate, which includes an upgrade test over a
project the 1.0 build generated.

**M14 in detail.** T14.01 moves the real-time combat scripts to a shared folder with shims at the
old paths; T14.02 side-view detection; T14.03 the platform actor (the side-view TileSet layers
exist only for this archetype); T14.04 side-view NPCs, objects and the camera; T14.05 abilities
and gates; T14.06 rooms and the world graph (the plan is stored in the project and reused on
regeneration; unreachable rooms and unpaired exits are warnings); T14.07 enemies and the
guardian; T14.08 the HUD, room map and save stations; T14.09 a second, side-view CC0 sample pack
so the top-down sample and its goldens do not change; T14.10 the wizard; T14.11 the smoke test
with a perf ceiling and CI split per archetype; T14.12 the docs; T14.13 the 1.2.0 gate.

## What is left before 1.0.0

### 1. Work a program can do

| Item | Card | What to do |
|------|------|------------|
| CI on `main` | T12.66 | The last push (`84f239b`, the T12.57–T12.64 batch) has not been checked. Every job must be green: Windows and Ubuntu, both PySide6 legs, GDScript, integration and perf. |
| Frozen smoke test on three systems | T12.66 | `release.yml` (or `python tools/package.py --smoke`) on Windows, Linux and macOS. The macOS build has never run on a Mac. |
| Workflow dry run | T12.15 / T12.66 | The release workflow has not run on GitHub yet; run it on a branch or a test tag and fix what it finds. |
| Lock files and actions | T12.66 | Confirm `requirements/release*.txt` are current and every action is pinned by SHA (CI checks the Windows lock). |

### 2. Work only a person can do

| Item | Card | What to do |
|------|------|------------|
| Held-out packs | T10.09, T10.10 | Five packs not used during development (2 commercial, 1 RPG Maker, 1 Tiled, 1 messy), both archetypes, with `tools/held_out_run.py`; fill in time to first paint and audit edits in [coverage.md](coverage.md). All 10 runs must pass and the median time to first paint must be under 10 minutes. **A tag build refuses to run while the table says *(pending)*.** |
| Pack-coverage study | ARCHITECTURE §51 | About 30 popular packs: the tier that handles each, the audit edits; ship profiles for any big vendor family. Table in [coverage.md](coverage.md). |
| Manual test pass | T11.29 | The 15 rows of `docs/spec/M11_pre_release.md` T11.29 on a frozen build: dock placement and rebuild, a real RPG Maker A2 sheet, the installer on a clean account, regeneration with the editor open, gamepad play of both archetypes, layers and Y-sort, audio, cancel, the Godot download, the online profile, display scaling at 150 % and 200 %, a 300–500 asset audit, the SmartScreen screenshot. |
| Manual rows for M12 | T12.66 | Equip, buy and sell, recruit, finish the demo quest; walk an encounter zone and run a cutscene; switch the game's language and open the credits; use the minimap, world map and lighting; use the dialogue dock and a custom recipe in the editor; import a Tiled and an LDtk map; export to Web, Linux and macOS; resolve a conflict; check learned rules on a second pack. |
| French translation | T12.56 | A native speaker reviews the 83 translated wizard texts (flagged in CONTRIBUTING). |
| Code signing | M10 | Windows signing waits for the code-signing application ([release.md](release.md)); macOS has no Developer ID or notarization in 1.0 (the README explains the Gatekeeper step). Not a gate item. |

When all of section 1 and 2 is done, T12.66 is closed and `v1.0.0` is tagged
([release.md](release.md#procedure)).

## Known limits in 1.0

These are decisions or gaps that ship with 1.0, not bugs to fix before it. Each names the M13
(release 1.1.0) card that removes it:

* The action RPG has no party members or followers. (T13.15)
* Every house leads to `interior_1`, which leads back to the first house. (T13.12)
* Shops sell one item per press (no quantity choice). (T13.11)
* The content validator does not check that `open_shop:`, `quest_*` and `join_party:` ids exist. (T13.13)
* No Windows taskbar progress; wizard pixmaps are not device-pixel-ratio aware. (T13.10)
* Sound slots are a fixed list (`sfx_step_<surface>` is not allowed by the schema). (T13.16)
