# START HERE — Instructions for the Implementing Model

You are implementing **rpggen**, a Windows desktop tool that turns 2D RPG asset packs into ready-to-edit Godot 4.7.2 projects. The architecture is in `ARCHITECTURE.md` (the v2 plan). **This folder is the build manual.** When the two disagree, this folder wins, because it is more specific.

Read these files in order before writing any code:

1. `00_START_HERE.md` — this file: how to work.
2. `01_CONVENTIONS.md` — repository layout, code style, naming, logging, and Godot rules.
3. `02_SCHEMAS.md` — every JSON file format, field by field.
4. `03_ERROR_CODES.md` — every error code the program may emit.
5. `M01_walking_skeleton.md` … `M12_review_followups.md` — task cards, done strictly in order,
   up to the `v1.0.0` tag. `M13_polish.md` (release 1.1.0), `M14_metroidvania.md` (release
   1.2.0), `M15_ui_polish.md` (release 1.3.0), `M16_arcade_archetypes.md` (release 1.4.0)
   and `M17_farm_isometric.md` (release 1.5.0, specified, not started) follow the tag, in that
   order.
   What is finished and what is left is summed up in `docs/status.md`.

---

## 1. How to work

### 1.1 One task card at a time

Each milestone file contains numbered task cards like `T1.04`. For every card:

1. Read the whole card, including **Depends on**, **Files**, **Spec**, **Tests** and **Done when**.
2. Confirm that every card listed in **Depends on** is complete. If one is not, stop and complete it first.
3. Create or modify **only** the files listed under **Files**. If you believe another file must change, write a note in `IMPLEMENTATION_NOTES.md` explaining why, then make the smallest possible change.
4. Write the tests listed under **Tests** first, or at the same time as the code.
5. Run the full test command (§1.4). Every test must pass, including the older ones.
6. Check every bullet under **Done when**. If any bullet is false, the task is not done.
7. Append a line to `IMPLEMENTATION_NOTES.md`: `T1.04 done — <one-sentence summary> — <any deviation>`.
8. Commit with the message `T1.04: <card title>`.

### 1.2 Never do these

* **Never hand-write `.tscn`, `.tres` or `project.godot` content** (except the minimal template `project.godot` defined in card T1.06). Scenes and resources are built by GDScript "recipes" that run headless and save through `ResourceSaver`. See `01_CONVENTIONS.md` §6.
* **Never write a `uid://` value** anywhere. Godot assigns UIDs. Commit the `.uid` files Godot creates next to scripts; never edit them.
* **Never modify files inside an input asset pack**, and never write anything into the folder the pack came from.
* **Never invent a Godot API.** If a card uses a Godot method you have not verified, follow §2 below.
* **Never catch an exception and continue silently.** Either handle it with a specific error code (`03_ERROR_CODES.md`) or let it propagate.
* **Never use randomness without a seed**, and never use the current time inside generated content.
* **Never delete or weaken a test to make it pass.** If a test seems wrong, explain why in `IMPLEMENTATION_NOTES.md` and stop.
* **Never skip ahead** to a later milestone "because it's easy".

### 1.3 When something is ambiguous

Use this order of preference:

1. The task card.
2. `02_SCHEMAS.md` and `01_CONVENTIONS.md`.
3. `ARCHITECTURE.md`.
4. The simplest implementation that passes the tests and keeps the documented contracts.

Record every judgment call in `IMPLEMENTATION_NOTES.md` under a heading `Decisions`.

If two documents directly contradict each other in a way that changes behavior, **stop and report the contradiction**. Do not guess.

### 1.4 Test commands

Python (from the repository root):

```bat
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

Godot (from the repository root, after T1.06):

```bat
python -m rpggen.dev godot-test
```

T1.08 defines this command. It runs the template project's GDScript tests headless.

Integration (after T1.10):

```bat
python -m pytest -q -m integration
```

Integration tests need the environment variable `RPGGEN_GODOT` to point at a Godot 4.7.2 console executable (`Godot_v4.7.2-stable_win64_console.exe`). If it is unset, integration tests are **skipped, not failed**. CI always sets it.

---

## 2. Verifying Godot APIs

The plan targets Godot **4.7.2**. Your training data may describe older Godot versions. Some APIs changed across 4.x releases.

Before using any Godot class or method for the first time:

1. Check that it appears in `docs/godot_api_verified.md`. That file is created in T1.07 and grows over time.
2. If it is not listed, verify it. Either:
   * write a 5-line probe script under `godot_templates/tests/probes/` that calls the API, and run it headless (`godot --headless --path godot_templates --script res://tests/probes/<probe>.gd`), or
   * read the official class reference for 4.7 at `https://docs.godotengine.org/en/4.7/classes/`.
3. Add a row to `docs/godot_api_verified.md`: `Class.method | signature | verified by (probe file or doc URL) | date`.

Task cards mark APIs that are especially likely to have changed with **⚠ VERIFY**. Never skip those.

If an API in a card does not exist in 4.7.2, find the closest equivalent. Record the substitution in `docs/godot_api_verified.md` and `IMPLEMENTATION_NOTES.md`, and continue.

---

## 3. Milestone overview

| File | Milestone | What exists at the end |
|------|-----------|------------------------|
| `M01_walking_skeleton.md` | M1 | CLI generates a project from one synthetic pack. The project has one TileSet and a moving player, validated headless in CI. |
| `M02_asset_intelligence.md` | M2 | Safe archive handling, image analysis, adapters (Tiled, Aseprite, RPG Maker, LPC, generic), classifier, full catalog. |
| `M03_wizard_audit.md` | M3 | PySide6 wizard with audit grid, bulk edit, object cutter, pack profiles, sample pack. |
| `M04_world_placement.md` | M4 | Layered starter map, object/building scenes, Y-sort origins, interior transition. |
| `M05_regeneration.md` | M5 | Ownership ledger, staging promotion, TileSet merge, pack diffing, backups. |
| `M06_shared_systems.md` | M6 | Runtime addon: Events, GameState, SceneRouter, SaveManager, stats, items, inventory, dialogue, settings, UI. |
| `M07_turn_based.md` | M7 | Encounters, battle, rewards, persistence, full smoke test. |
| `M08_editor_dock_terrain.md` | M8 | Asset Library dock, catalog overrides in the editor, terrains, content validator, demo removal. |
| `M09_arpg.md` | M9 | ARPG player, enemies, hitboxes, HUD, ARPG smoke test. |
| `M10_release.md` | M10 | Packaging, signing, diagnostics, docs, profile registry, export test. |
| `M11_pre_release.md` | M11 | Pre-release fixes, wizard UX, sound, autosave, game over, a second map, docs. |
| `M12_review_followups.md` | M12 | Review follow-ups: fixes, engineering, UX and 25 features; the 1.0 gate. |
| `M13_polish.md` | M13 | Release 1.1.0, after the 1.0 tag: ten wizard UX cards, seven feature improvements, three additions, the lock-and-key planner; the first milestone under the post-release compatibility contract. |
| `M14_metroidvania.md` | M14 | Release 1.2.0: the Metroidvania archetype (platform actor, abilities, rooms, guardian, save stations, a side-view sample pack). |
| `M15_ui_polish.md` | M15 | Release 1.3.0: the look, feel and ease of use of the wizard (design tokens, one stylesheet, button kinds, icons, cards, the stepper sidebar, page headers, every page and dialog), the Generate log fix, actionable failures, regeneration that skips unchanged work, visual goldens. |
| `M16_arcade_archetypes.md` | M16 | Release 1.4.0: three more kinds of game on a shared arcade framework (shoot 'em up, run and gun with a grapple, racing), three sample packs, and the kinds sketched for M17. |
| `M17_farm_isometric.md` | M17 | Release 1.5.0, specified and not started: a farm and life sim (the calendar, tools, soil and crops, animals, the shop and the shipping bin, people with schedules and friendship, fishing, weather) and isometric tiles as a second view of the top-down kinds and the racing game; the kinds left for later. |

Each milestone ends with a **Milestone Gate** card. All its checks must pass before the next milestone starts.

---

## 4. Glossary

| Term | Meaning |
|------|---------|
| **Pack** | One asset pack supplied by the user: a `.zip`, `.7z` or folder. |
| **pack_id** | Stable slug for a pack, e.g. `forest_pack`. See `01_CONVENTIONS.md` §4. |
| **Inventory** | Immutable list of every file in a pack, with hashes and basic image facts. |
| **Analysis** | Derived facts about one image: grid, frames, baseline. Cached by hash. |
| **Adapter** | Python plugin that recognizes a known pack layout or metadata format and emits catalog entries. |
| **Catalog** | `rpggen/asset_catalog.json` in the generated project. It holds every asset's detected facts and user overrides. |
| **Override** | A user decision stored in the catalog. It always wins over detection. |
| **Recipe** | GDScript function that builds one scene or resource in code and saves it. |
| **Builder** | Headless GDScript entry point that runs all recipes from the catalog and config. |
| **Staging** | `<target>/.rpggen_staging/`, the folder where a generation happens before promotion. |
| **Promotion** | Copying validated staging output into the target project. |
| **Ledger** | `rpggen/ownership_ledger.json`. It records every file the generator wrote, with its hash. |
| **Generated-owned** | Files under `generated/`, `addons/rpg_runtime/` and `addons/rpg_project_tools/`. The generator may rewrite them, subject to the ledger. |
| **User-owned** | Files under `game/`. They are created once and never rewritten. |
| **Smoke test** | Headless run of the generated game through a scripted scenario. |
| **Archetype** | `turn_based` or `arpg`; `metroidvania` from M14 (release 1.2.0); `shmup`, `run_and_gun` and `racing` from M16 (release 1.4.0); `farm` is specified in M17. The wizard calls it the *kind of game*. |
