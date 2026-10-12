# Project status

Where rpggen stands against its build plan (`docs/spec/`), and what is left before `v1.0.0` is
tagged. Updated 2026-10-09: `main` is the 1.0 candidate (commit `446b9f6`), and the branch `m13`
holds release 1.1.0, whose cards are all implemented; the branch `m14` (on top of `m13`) holds
release 1.2.0, the metroidvania, whose cards are all implemented too. The detail of every finished card is in
[docs/dev/implementation_notes.md](dev/implementation_notes.md); this page is the summary.

## In one paragraph

Every feature card of milestones M1 to M12 is implemented and tested: 70 of the 71 cards of M12,
and every card of M1 to M11 that a program can do. Locally on Windows the unit and GUI suites
(1395 tests), the GDScript suite (479 tests) and the integration suite pass. **Nothing has been released and no tag
exists.** What remains is the 1.0 gate
(T12.66), and the work that only a person can do: the held-out pack runs (T10.09), the manual test
pass (T11.29, extended for M12), and the manual checks the earlier gates left open. The work
after the tag: M13 (release 1.1.0) is implemented on the branch `m13` and waits for its gate
(T13.23); M14 (release 1.2.0) is implemented on the branch `m14` and waits for its gate's manual
rows (T14.13), below.

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
| M13 Polish (1.1.0) | Ten wizard UX cards, seven feature improvements, three additions, the lock-and-key planner, world repair (below) | On the branch `m13` (not part of 1.0): every card is implemented; T13.23 (the gate) is open. 23 of 24 cards done |
| M14 Metroidvania (1.2.0) | The third archetype (below) | On the branch `m14` (not part of 1.0 or 1.1): every card is implemented; the manual rows of the gate (T14.13) are open. It was built before the 1.1 tag existed, on top of `m13` |
| M15 Look, feel and ease of use (1.3.0) | A design system (tokens, one stylesheet, button kinds, icons, cards, a stepper sidebar, page headers), every page and dialog restyled, the Generate log without escape codes, actionable failures, a regeneration that skips what did not change, visual goldens (`docs/spec/M15_ui_polish.md`) | On the branch `m15` (on top of `main`, which holds M14): every card is implemented; the gate (T15.25) is open, below |
| M16 More kinds of game (1.4.0) | A shoot 'em up (vertical or horizontal), a run and gun with a grapple option, a racing game, on a shared arcade framework; three sample packs; the kinds for M17 sketched (`docs/spec/M16_arcade_archetypes.md`) | Started 2026-10-10 on the branch `m16` (on `m15`, before the 1.3 tag). T16.01 to T16.17 are done (the framework, detection, the three kinds, the wizard for them and their three sample packs); the kinds stay behind their feature flags until the gate. Open: T16.18 to T16.20 (smoke sequences, documentation, the gate), T16.21 (what the real packs need: most of the way) and T16.22 (choosing the packs of a bundle) |

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

**M15** (the look, feel and ease of use, release 1.3.0, `docs/spec/M15_ui_polish.md`) is implemented on the branch `m15`; what its gate still needs is under *What is left before 1.3.0*. **M16** (three more kinds of game, release 1.4.0, `docs/spec/M16_arcade_archetypes.md`) is specified with its order of work, index and gate, and not started.

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

All thirteen cards are done (2026-10-09). What the plan did not foresee, and what was decided:

* The smoke test of a metroidvania is a whole sequence of its own (sixteen steps from the title
  screen to the last room): the shared sequence walks a top-down village and cannot run in a
  room.
* The four new sound slots are fixed slots of the metroidvania only, so the sound table of a
  top-down project is unchanged.
* A pack without side-view tiles still makes a game: plain one-way platforms, ladders, spikes
  and breakable blocks are generated in its tile size (`side_kit.py`).
* A defeated player returns to the last save station with everything it had; a room change
  saves into the autosave slot.
* Godot writes a `Translation` resource in the order of its names in memory, which differs
  between runs now and then. The determinism test compares such a file as a set of lines; the
  generated table is the same.

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

These were the decisions and gaps that ship with 1.0. Every one of them is removed by a card of
M13 (release 1.1.0), so the list is empty on the branch `m13`; `main` (1.0) still has them: shops
sell one item at a time, every house leads to the same interior, the validator does not check the
ids a dialogue names, Zstandard map layers are not read, the action RPG has no followers, and the
sound slots are a fixed list.

## What is left before 1.3.0

The cards T15.01 to T15.24 are done (2026-10-10). The detail, with every deviation from the
spec, is in [the notes](dev/implementation_notes.md); the ones a reader should know:

* The icons are rpggen's own drawings in the manner of Lucide, not Lucide's files.
* The audit's filter row is two lines beside the detail panel in the default window (it was
  three, with *Profile* cut off); one line would mean moving the splitter.
* The visual goldens are rendered with a test font in the repository (DejaVu 2.37), on
  Windows. Whether Ubuntu draws the same font closely enough has not been seen yet: the first
  CI run says.
* *Run every check again* in the regeneration preview is the project's standing choice;
  `--full` is the switch for one run.
* A regeneration is a repeat only when your own files (`game/`, `project.godot`) are also what
  they were at the last run, so the validator and the smoke test still run over a map you
  changed. The spec only names the generated files; three older integration tests showed what
  that would have taken away.
* An unchanged regeneration of the 1,000-image pack takes 15 s on the development machine
  (a full one 90 s); the ceiling is 20 s with the allowance for CI hardware, not a bare 10 s.

The gate (T15.25) is open:

| Item | What to do |
|------|------------|
| The 1.2 tag | `v1.2.0` is an annotated tag on `433c96e` (the head of `main`, which `m15` is built on), made on 2026-10-10 **in the development checkout only**: pushing a `v*` tag starts the release workflow, which stops while `docs/coverage.md` has a pending row. `v1.0.0` (`446b9f6`, the 1.0 candidate) and `v1.1.0` (`38de73c`, the last commit of M13 before M14 began) were tagged the same way on the same day. Push each when its gate is closed (below and above). |
| CI on `m15` | Every suite green on Windows and Ubuntu, on both PySide6 legs. The visual goldens were made on Windows with the bundled font: the first run shows whether the Ubuntu legs (FreeType of the system, PySide6 6.7 and the newest) draw it within the limits. If one does not, look at its `_failed` artifact before widening a limit. Perf within its ceilings, with the two regeneration rows. |
| Frozen smoke test | `python tools/package.py --smoke` on the three systems: the icons and `style.qss.in` must be in the bundle. |
| Upgrade test | The upgrade test of M13 with the 1.3 build over a 1.0, a 1.1 and a 1.2 project: no prompt, nothing under `game/` changes, and the second regeneration repeats no check (the first one is full: those projects have no fingerprint). |
| Manual rows | Both themes at 100 %, 150 % and 200 % on every page and dialog; a 300-asset audit with the filter row; the seven pages with NVDA; keyboard only from the welcome view to Results; reduce motion on and off; the French wizard (the longer texts must fit the rows and the stepper). The new wizard texts of M15 are marked unfinished in the French file. |

## What is left before 1.2.0

The cards T14.01 to T14.12 are done, and the part of the gate (T14.13) a program can do:
`METROIDVANIA_AVAILABLE` is on, the wizard's metroidvania path has a GUI integration test, and
the suites pass locally on Windows (2026-10-09): unit and GUI 1,713 tests plus the 5 slow GUI
ones (the wizard paths and the screenshots), GDScript 599, integration 128 (89 shared, 11
action RPG, 28 metroidvania), perf 5 (the side-view sample as a metroidvania takes about half
a minute against a ceiling of 180 s); ruff and mypy are clean. Open:

| Item | What to do |
|------|------------|
| The 1.1 tag | M14 was built on `m13` before `v1.1.0` existed. Tag 1.1 first (its gate, above), then rebase or merge `m14` and run the suites again. |
| CI on `m14` | Every suite green on Windows and Ubuntu, on both PySide6 legs, with the new per-archetype integration jobs; perf within its ceilings, including the metroidvania's. Nothing has been pushed. |
| Upgrade test | Done with the templates of `m13` standing in for the 1.1 build: a turn-based and an action-RPG project regenerate without a prompt, with everything under `game/`, their TileSets and their sprite frames byte for byte what they were; a scene that instanced an enemy still loads and a script that preloads an old combat path still runs. To repeat with the real `v1.1.0` build. |
| Corpus | The private corpus (T12.26) must be unchanged on all four measures after the side-view detection (T14.02). It is not on the development machine. |
| Manual rows | Play the side-view sample to the last room with a gamepad (the feel of the jump, coyote time, the wall slide, the guardian's telegraphs); talk to the hermit and open a chest from both sides; drop an object from the dock into a room; add a room in the wizard and regenerate; break a block, save at a station, die, and check that the block stays broken; generate a metroidvania from a real side-view pack you own. |

## What is left before 1.1.0

The cards T13.01 to T13.22 and T13.24 are done. The gate (T13.23) is open:

| Item | What to do |
|------|------------|
| CI on `m13` | Every suite green on Windows and Ubuntu, on both PySide6 legs; perf within its ceilings. Locally on Windows (2026-10-09) the unit, GUI and perf suites (1,590 tests), the GDScript suite (536) and the integration suite (93) pass. |
| Frozen smoke test | `python tools/package.py --smoke` on Linux and macOS. On Windows it passes, including the Ogg Vorbis decode through the packaged libsndfile (`rpggen-cli audio-check`). |
| Upgrade test | Done with the code of `main`: a 1.0 project of each archetype regenerates with 1.1 without a prompt and with everything under `game/` byte-identical. Still to do with the real `v1.0.0` build: load a save it wrote in the regenerated game. |
| Corpus | The private corpus (T12.26) is unchanged on all four measures. It is not on the development machine. |
| Manual rows | Buy three of an item and sell all; enter two houses; use review mode and folder groups on a 300-asset pack at 150 % scaling; make a variant enemy and meet it in the game; edit a quest in the graph and a cutscene step, and press Test with the game running from the editor; generate a three-area world and regenerate it with a changed seed; add an area to it and see its neighbour mended; delete a door from an area you edited, use *Repair the world…*, then undo a Fix in the dock; set a loop point and hear it in the game; add a custom sound slot; open a Tiled map with a Zstandard layer; watch a follower help in the action RPG. |

