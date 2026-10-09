# Implementation Plan — v2

## Godot 4.7.2 RPG / ARPG Project Generator

---

## 0. What Changed From v1 (Read This First)

v1 had the right goals and the right instincts (non-destructive, Godot-validated, human-in-the-loop). v2 keeps all of them and fixes the parts that would have caused rework or broken users' projects later.

| # | Change | Why it matters |
|---|--------|----------------|
| 1 | **Godot builds the engine resources; Python only emits data.** TileSets, SpriteFrames, scenes and `project.godot` settings are created by a GDScript builder running headless, using engine APIs and `ResourceSaver`. | Hand-writing `.tscn`/`.tres`/`project.godot` text from Python breaks silently on format details and UIDs. The engine never writes a format it can't read. |
| 2 | **Stable TileSet IDs are a hard contract.** Atlas source IDs, atlas coordinates and alternative IDs are recorded in the catalog and never reused or renumbered. | Painted maps store `(source_id, atlas_coords, alternative_id)`. If regeneration renumbers anything, every map the user painted is silently corrupted. v1 didn't address this. |
| 3 | **Explicit file ownership model** (`generated/` vs `game/`) with a hash ledger, plus in-place merge for TileSets. | v1 said "generated/ and user/ where practical" — that isn't enforceable. Regeneration safety needs a mechanism, not an intention. |
| 4 | **Source assets are copied once**, verbatim, under `assets/packs/<pack_id>/`. Categories live in the catalog and editor dock, not in duplicated folders. | v1 had both `assets/source/` and `assets/characters/` etc., which would double-import every texture and make "which file is real?" ambiguous. |
| 5 | **Known pack-format adapters** (RPG Maker MV/MZ layout, LPC layout, generic grid) run before heuristics. | A large share of commercial RPG packs follow one of a few layouts. Recognizing them gives near-certain results; heuristics are the fallback, not the main path. |
| 6 | **Atlas margins and separation detection** added to tile analysis. | Many sheets have 1px gutters or outer padding. Without this, tile size detection succeeds but every tile is offset. |
| 7 | **Validation from Milestone 1**, not Milestone 8. CI runs Godot headless on every commit against a fixture corpus. | Building 7 milestones before validating anything is how a generator ends up with hundreds of subtle engine incompatibilities. |
| 8 | **Walking-skeleton MVP, one archetype first.** | v1's MVP contained both combat systems, an editor plugin, and a full smoke test — that's most of the product, not an MVP. |
| 9 | **Smoke test runs through a test harness with seeded RNG** and service-level drivers, not simulated keypresses alone. | "Complete combat" can't be reliably automated by pressing keys at a random enemy. |
| 10 | **Testing strategy for the generator itself**, a risk register, measurable acceptance criteria, licensing handling, and Windows-specific archive hardening. | All were missing. |
| 11 | **Several internal inconsistencies resolved** (Event system vs autoload list, `DialogueResource` vs JSON example, `debug_placeholders/` location, bootstrap script vs permanent builder). | See the relevant sections. |

---

## 1. Project Objective

Build a standalone Windows desktop application that takes one or more purchased 2D RPG asset packs and produces a **fully structured, immediately editable Godot 4.7.2 project** that functions as a workbench for those assets.

The generated project provides foundations for:

* Classic turn-based RPG or real-time action RPG (selectable; shared core)
* TileMapLayer-based map painting with working TileSets, collision and (where possible) terrains
* Drag-and-drop placement of characters, NPCs, buildings and decor via an editor dock
* Animated characters with standardized animation names
* Dialogue, encounters, combat, inventory, save/load, scene transitions, basic UI
* Keyboard, mouse (where appropriate) and gamepad input

Non-negotiables:

1. Source asset files are never modified.
2. Regeneration never destroys user-authored work — including painted maps.
3. Every generated project is validated by Godot 4.7.2 before it is handed to the user.

**Success is measured by time-to-first-paint:** a user with a supported pack should be painting tiles on a working map within 10 minutes of launching the wizard.

---

## 2. Core Design Principles

### 2.1 Pin the engine version, verify it at runtime

Target: **Godot 4.7.2**.

* Detect the version by running the selected executable with `--version` and parsing the `major.minor.patch.status` prefix.
* Policy:
  * `4.7.2.stable` → supported.
  * Other `4.7.x` stable → allowed with a warning ("validated against 4.7.2").
  * Anything else → rejected before generation.
* The validated version is a single constant in the generator (`TARGET_GODOT = "4.7.2"`). Upgrading targets is a deliberate release of the generator, with the template suite re-validated in CI.
* Before implementation begins, verify every engine behavior this plan relies on (TileMapLayer, terrain modes, TileSetAtlasSource margins/separation, `--import`, `--check-only`, `ResourceUID`) against the 4.7.2 documentation and record the findings in `docs/engine_assumptions.md`. Each assumption gets a CI test.

### 2.2 The asset pack is the source of truth; the user is the final authority

Pipeline:

1. Archive inventory
2. Pack-format adapter matching (§9)
3. Image analysis (heuristics, only where no adapter matched)
4. Candidate-role assignment with confidence
5. **Human confirmation** in the visual audit
6. Catalog registration

The audit UI is not a side feature — it is where the product's correctness actually comes from. Heuristics reduce the user's work; they do not replace the user's judgment.

### 2.3 Division of labor

| Layer | Owns | Never does |
|-------|------|-----------|
| Python generator | Archive handling, image analysis, classification, wizard, catalog, config, ownership ledger, orchestration, reporting | Write `.tscn`, `.tres` or `project.godot` by hand |
| Godot builder (GDScript, headless) | Import, TileSets, SpriteFrames, scenes, project settings, input map, validation, smoke test | Analyze images or make classification decisions |
| Static templates | Runtime GDScript, base scenes, UI scenes, editor plugin — authored and tested in a real Godot 4.7.2 project in this repo | Contain pack-specific data |
| User | Classification decisions, map design, game content | — |

### 2.4 Determinism

Same pack(s) + same config + same generator version → same catalog, same file set, same IDs.

Rules:
* Walk files in sorted, case-normalized order.
* Derive asset IDs from normalized relative paths (`characters/Hero_01.png` → `characters.hero_01`); resolve collisions with a deterministic suffix.
* Serialize JSON with sorted keys and fixed float formatting.
* No timestamps or random values inside generated content (timestamps go only in the report).
* Godot-managed values (UIDs, import metadata) are excluded from determinism comparisons.

---

## 3. High-Level Architecture

```text
┌───────────────────────────────────────────────────────────────┐
│               RPG Project Generator (Windows app)             │
├───────────────────────────────────────────────────────────────┤
│ Wizard (PySide6) ── gathers config only, no generation logic  │
├───────────────────────────────────────────────────────────────┤
│ Generator Core (Python, also usable via CLI)                  │
│  archive → adapters → analyzer → classifier → catalog         │
│  ownership ledger → staging → orchestrator → report           │
└───────────────────────────────┬───────────────────────────────┘
                                │ writes: catalog.json, config.json,
                                │ static templates, copied packs
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ Godot 4.7.2 headless (in the staging folder)                  │
│  1. import         2. builder (TileSets, SpriteFrames, scenes,│
│  3. validate          project settings, input map)            │
│  4. smoke test                                                │
└───────────────────────────────┬───────────────────────────────┘
                                │ results.json
                                ▼
          promote staging → target, write GENERATION_REPORT.md
```

The CLI is a first-class entry point from day one (`rpggen generate --config x.json`). The GUI calls the same core. This makes CI, batch generation and debugging trivial.

---

## 4. Technology Choices

| Concern | Choice | Notes |
|---------|--------|-------|
| Language | Python 3.12+ | |
| GUI | PySide6 (Qt) | Mature, good image grid performance, LGPL — dynamic linking keeps distribution simple |
| Image analysis | Pillow + NumPy | Grid/gutter detection is array math |
| Archives | `zipfile` (stdlib); `py7zr` for .7z; RAR via optional external `unrar`/7-Zip if present | RAR support is best-effort; tell the user to extract manually otherwise |
| Schema validation | `jsonschema` | For catalog and config |
| Packaging | PyInstaller (one-folder build) or Nuitka | One-folder starts faster and triggers fewer antivirus false positives than one-file |
| Distribution | GitHub Releases (zip + installer), then winget | Open source (§51) |
| Code signing | Apply to an open-source signing program (e.g., SignPath Foundation); otherwise a low-cost signing service | Unsigned executables trigger SmartScreen warnings that drive away non-technical users |
| Tests | pytest + golden files; Godot headless in CI | §46 |
| CI | GitHub Actions `windows-latest`, Godot 4.7.2 downloaded and cached | |

---

## 5. Generator Repository Layout

```text
rpggen/
├── rpggen/
│   ├── cli.py
│   ├── gui/                    # wizard pages, audit grid, log view
│   ├── core/
│   │   ├── archive.py          # safe extraction, inventory
│   │   ├── adapters/           # rpgmaker.py, lpc.py, generic_grid.py, ...
│   │   ├── analyzer.py         # dimensions, alpha, gutters, grid, frames
│   │   ├── classifier.py       # role candidates + confidence
│   │   ├── catalog.py          # load/save/merge/migrate
│   │   ├── ownership.py        # hash ledger, conflict detection
│   │   ├── staging.py          # transaction model
│   │   ├── godot.py            # executable detection, version, invocation
│   │   ├── orchestrator.py     # phase pipeline
│   │   └── report.py
│   └── errors.py               # error codes
├── godot_templates/            # a REAL Godot 4.7.2 project, opened & tested in CI
│   ├── project.godot
│   ├── addons/rpg_project_tools/
│   ├── generated/              # base scenes/scripts copied into output
│   ├── builder/                # headless GDScript builder + validators + smoke test
│   └── fixtures/
├── schema/
│   ├── catalog.schema.json
│   ├── config.schema.json
│   └── ledger.schema.json
├── test_packs/                 # synthetic + permissively licensed fixture packs
└── tests/
```

Key point: `godot_templates/` is itself a runnable Godot project. Template scripts and scenes are developed in the editor, not as strings in Python. The generator copies them; it does not author them.

---

## 6. Project Generation Modes

### Shared core (every archetype)

Actor stats, inventory, item definitions, save data, dialogue, scene transitions, world state, event bus, UI infrastructure, asset catalog access.

### Turn-based archetype adds

Encounter triggers, battle scene, turn manager, battle commands, XP/levels, enemy rewards, battle UI.

### ARPG archetype adds

Real-time attacks, hitboxes/hurtboxes, enemy AI, knockback, invulnerability frames, combat HUD.

### Archetype boundary

Archetypes plug into the shared core through a small, explicit contract so neither duplicates shared systems:

```gdscript
# generated/core/combat_mode.gd
class_name CombatMode extends Node
## Implemented by TurnBasedCombatMode and RealtimeCombatMode.
func start_encounter(encounter: EncounterData) -> void: pass
signal encounter_finished(result: EncounterResult)
```

Shared code depends on `CombatMode`, `EncounterData` and `EncounterResult` only. Every archetype ships in the template repo and is tested in CI even though each generated project contains one.

---

## 7. Phase 0 — Environment Preflight

Validate before touching any assets:

* Windows 10/11, 64-bit
* Godot executable exists, runs, reports a supported version (§2.1)
* Output folder: writable, not inside the asset pack, not inside a cloud-sync folder that locks files mid-write (warn for OneDrive/Dropbox paths)
* Long paths: estimate the longest output path; warn if any exceed 260 characters and the system's long-path support is off
* Free disk space ≥ 3× the uncompressed pack size (copy + import cache + staging)
* Archive readable and not password-protected

Godot is always invoked with an explicit project path: `godot --headless --path "<staging>" ...`. Each invocation has a timeout, and stdout/stderr are captured to `logs/godot_<phase>.log`.

---

## 8. Phase 1 — Archive Inventory

### Safe extraction (mandatory)

* Reject entries with absolute paths or `..` components (zip-slip).
* Normalize Unicode filenames; handle legacy CP437-encoded zip names.
* Detect case-insensitive collisions (`Tree.png` vs `tree.png` — both valid in a zip, one overwrites the other on Windows).
* Detect nested archives; offer to extract them (one level).
* Cap total extracted size and file count (zip-bomb protection).
* Ignore OS junk (`__MACOSX/`, `.DS_Store`, `Thumbs.db`) but list them in the report.
* Plain folders are also accepted as input — many users have already extracted their packs.

### Inventory record (per file)

```text
relative_path, sha256, size, extension, kind (image/audio/font/doc/other),
width, height, mode, has_alpha, frame_count (GIF/APNG)
```

The inventory is immutable once created and saved as `inventory.json` in the cache.

### Multiple packs

A project can include several packs (common in practice: a tileset pack + a character pack + a UI pack). Each pack gets a `pack_id` and its own namespace in the catalog.

### Licensing

* `README*`, `LICENSE*`, `credits*` and similar files are always preserved and listed.
* The report includes a **Licenses** section listing each pack and its license file.
* The generated `README.md` reminds the user that pack licenses govern redistribution of assets in their game.
* The generator never uploads or transmits assets anywhere.

### Incremental cache

Analysis results are cached by file hash in `%LOCALAPPDATA%/rpggen/cache/`. Re-running on the same pack skips unchanged files, which matters for 1,000+ image packs.

---

## 9. Phase 2 — Pack-Format Adapters

Before generic analysis, each pack is offered to a list of adapters. An adapter recognizes a known layout and produces high-confidence catalog entries.

Adapters are prioritized in three tiers (decision record §51, item 4):

**Tier 1 — metadata adapters (build first).** These read files that already describe the art, so nothing is guessed. They work across vendors.

| Adapter | Reads | Produces |
|---------|-------|----------|
| Tiled | `.tsx` tilesets, `.tmx` maps: tile size, margin, spacing, per-tile collision objects, Wang sets, tile properties, animated tiles | Exact atlas grid, collision, terrains (from Wang sets), tile animations, optionally the sample maps converted to TileMapLayers |
| Aseprite JSON | Sprite-sheet `.json` exports: frame rectangles, durations, frame tags | Exact SpriteFrames with per-frame timing and named animations |
| LDtk | `.ldtk` project: tilesets, IntGrid layers, auto-layer rules | Atlas grid, collision from IntGrid, sample maps |
| Generic grid | Uniform sheets with a detectable grid | Tile atlases, frame strips |
| Per-file strips | `name_action_direction` naming | Animations assembled across files |

**Tier 2 — layout-standard adapters.** Each covers a large ecosystem of packs from many vendors that follow a shared convention.

| Adapter | Recognizes | Produces |
|---------|-----------|----------|
| RPG Maker MV/MZ (also VX Ace via 32px variant) | Folder names (`img/tilesets`, `img/characters`, `img/faces`), `A1`–`A5`/`B`–`E` naming, 48px (MV/MZ) or 32px (VX Ace) grids, `$`/`!` prefixes, 3×4 blocks per character (12×8 sheets of 8 characters) | Tile atlases, autotile terrains, 4-direction walks, portraits |
| LPC (Liberated Pixel Cup) | 64×64 frames in the standard row layout (spellcast, thrust, walk, slash, shoot, hurt) | 4-direction walk/attack/hurt animations |

**Tier 3 — vendor-family profiles.** These are shipped as declarative **pack profiles** (JSON), not as code (§53). They cover popular product lines that use their own consistent layout. Candidates are chosen by checking what currently sells and gets downloaded on itch.io's top-down RPG asset listings at the start of M2, and they are reviewed each release. Contributors add new profiles without touching core code.

Adapters are plugins with a common interface (`match(pack) -> score`, `extract(pack) -> CatalogEntries`). New adapters for popular vendor layouts can be added without touching core code. Users can also save their confirmed mapping for a pack as a **pack profile** and share it — a pack mapped once by anyone never needs remapping.

Adapter matches still appear in the audit; they are just pre-confirmed with high confidence.

**Licensing note:** RPG Maker RTP assets are licensed for RPG Maker use only. If the adapter detects RTP files, flag them in the report. Third-party packs in RPG Maker format are fine subject to their own license.

---

## 10. Phase 3 — Image Analysis (Heuristic Fallback)

For images no adapter claimed:

### Grid detection

1. **Gutter detection:** scan rows and columns for fully transparent or uniform-color lines. Regular gutter spacing gives `margin`, `separation` and cell size directly.
2. **Autocorrelation:** for gutterless sheets, compute row/column autocorrelation of the alpha (or luminance) channel; peaks suggest periodicity.
3. **Candidate scoring:** for each candidate size in `{8, 12, 16, 24, 32, 48, 64, 96, 128}` plus any detected periodicity, score by:
   * divisibility after accounting for margin/separation
   * fraction of cells that are fully empty or fully non-empty (real grids have clean cells)
   * edge discontinuity at cell boundaries
   * consistency with other sheets in the same pack (packs almost always use one base tile size)
4. Report top candidates with confidence. Never silently pick the smallest divisor.

### Character/animation detection

* Frame strips: images whose width is an integer multiple of height (or vice versa) with similar non-empty bounding boxes per cell.
* Directional grids: 4 or 8 rows of equal frame counts.
* Per-frame **content bounding box** and **feet baseline** (lowest opaque row) — used later for sprite offsets so characters stand on their tile, not float.

### Other signals

* Transparent border (tight crop suggestion for objects)
* Large opaque images with no grid → probably background or UI panel
* Small square images with alpha → items/icons
* 9-slice candidates for UI (uniform edges, varied center)

All analysis is read-only and cached by hash.

---

## 11. Phase 4 — Role Classification

Roles (unchanged from v1, plus `PORTRAIT` already present, and `AUTOTILE`, `AUDIO_MUSIC`, `AUDIO_SFX`, `FONT` added):

```text
GROUND  WALL  CLIFF  WATER  ROAD  AUTOTILE  DECORATION  BUILDING  INTERIOR
PLAYER  NPC  ENEMY  BOSS  WEAPON  ITEM  EFFECT  PROJECTILE  UI  PORTRAIT
BACKGROUND  AUDIO_MUSIC  AUDIO_SFX  FONT
```

Signals, in descending weight: adapter result → folder names → file names → analysis structure → dimensions → transparency.

Each asset can hold several candidate roles with confidences. One is marked primary after confirmation. Audio is classified by duration and loop points (long/loopable → music; short → SFX).

---

## 12. The Catalog

`asset_catalog.json` is the permanent bridge between packs and project. It has two layers:

* **Detected** — written by the generator; replaced on regeneration.
* **Overrides** — written by the user (via wizard or the in-editor dock); never discarded. Effective value = override if present, else detected.

```json
{
  "catalog_version": 2,
  "generator_version": "1.0.0",
  "packs": [
    { "pack_id": "forest_pack", "source_sha256": "…", "license_files": ["LICENSE.txt"] }
  ],
  "assets": [
    {
      "id": "forest_pack.tiles.grass",
      "pack_id": "forest_pack",
      "path": "assets/packs/forest_pack/Tilesets/grass.png",
      "sha256": "…",
      "detected": {
        "role": "GROUND",
        "confidence": 0.94,
        "grid": { "tile_size": [16, 16], "margin": [0, 0], "separation": [1, 1] },
        "collision_profile": "NONE"
      },
      "overrides": {},
      "tileset": { "tileset": "overworld", "source_id": 3 }
    },
    {
      "id": "forest_pack.characters.hero",
      "pack_id": "forest_pack",
      "path": "assets/packs/forest_pack/Characters/hero.png",
      "detected": {
        "role": "PLAYER",
        "frame_size": [16, 24],
        "origin": [8, 23],
        "directions": 4,
        "animations": {
          "walk_down": { "row": 0, "frames": [0, 1, 2, 3], "fps": 8, "loop": true }
        }
      },
      "overrides": { "animations": { "walk_down": { "fps": 6 } } }
    }
  ],
  "id_allocations": {
    "overworld": { "next_source_id": 7, "retired_source_ids": [2] }
  }
}
```

Rules:
* `source_id` values are allocated once and **never reused** — `retired_source_ids` records removed sources.
* Catalog versions are migrated forward by explicit migration functions with tests.
* If an asset's file disappears from a new pack version, the entry becomes `MISSING`, not deleted, until the user confirms.

---

## 13. Phase 5 — Visual Asset Audit

The audit is a virtualized thumbnail grid (Qt model/view) so 2,000+ assets stay responsive.

Each card: preview (with detected grid overlay), filename, pack, dimensions, tile size, role, frames, confidence bar, collision profile, status.

Statuses: `CONFIRMED`, `AUTO-DETECTED`, `NEEDS REVIEW`, `MISSING`, `UNUSED`, `CONFLICT`.

Workflow features that make it fast:

* **Filter to "Needs review"** by default — users fix only what's uncertain.
* **Bulk actions** — select 40 tree images, set role `DECORATION`, collision `BOTTOM_EDGE`, done.
* **Folder-level rules** — "everything in `Characters/Enemies/` is ENEMY" applies to current and future files.
* **Grid editor** — adjust tile size, margin, separation with the overlay updating live.
* **Animation preview** — play detected animations at their FPS; fix frame ranges by clicking cells.
* **Required-roles checklist** — the archetype needs at minimum one PLAYER, one ground tileset; the checklist shows what's satisfied.
* Contact sheet export (PNG/PDF) for offline review.

---

## 14. Missing Assets and Placeholders

When a required role has no asset, the user chooses: assign a replacement, use a debug placeholder, continue without it (feature disabled), or abort.

Placeholders:
* Live in `generated/debug_placeholders/` (inside the generated area, so regeneration manages them).
* Are visually unmistakable (magenta/black checker with text, e.g., `MISSING PLAYER 32x48`).
* Are listed in the report and flagged with a `debug_placeholder` metadata tag so a validation step can warn before export.

---

## 15. Phase 6 — Asset Installation

```text
assets/
└── packs/
    └── <pack_id>/          # verbatim copy of the pack, original structure preserved
        ├── LICENSE.txt
        └── …
```

* Each file copied exactly once. No category folders duplicating textures.
* Categories are presented by the editor dock (§21) using the catalog, so the user still browses by "Buildings", "NPCs", etc.
* Import defaults for pixel art: nearest filtering set project-wide; mipmaps off; compression lossless. Large non-pixel art (backgrounds) can override per file via the catalog.
* Unused assets are still copied (the user may want them later) but can be excluded per-pack to reduce import time.

---

## 16. Phase 7 — TileSet Generation

TileSets are built by the Godot builder from the catalog, saved as external `.tres` resources:

```text
generated/tilesets/overworld.tres
generated/tilesets/interior.tres
```

Each TileSet gets:
* tile size (one base size per TileSet; mixed-size packs get separate TileSets)
* one `TileSetAtlasSource` per sheet, with `texture_region_size`, `margins`, `separation` from the catalog
* tiles created only for non-empty cells
* physics layers, collision polygons per profile (§17)
* custom data layers: `asset_id` (String), `footstep` (String), `move_cost` (float) — cheap to add, useful later
* terrain sets where the catalog defines them (§18)
* optional navigation and occlusion layers

### Regeneration of TileSets: merge, don't replace

If the TileSet already exists, the builder **loads and updates it in place**:
* existing sources keep their `source_id`
* new sheets are added with newly allocated IDs
* tiles that still exist keep their data, including any collision the user hand-edited in Godot
* tiles whose cells became empty are reported, not silently removed
* removed sheets are reported; their source is kept until the user confirms removal (removing it would erase painted tiles)

This is the single most important regeneration rule in the plan.

---

## 17. Collision

### Profiles

```text
NONE  FULL  BOTTOM_HALF  BOTTOM_EDGE  TOP_EDGE  LEFT_EDGE  RIGHT_EDGE  ALPHA_POLYGON  CUSTOM
```

* `ALPHA_POLYGON` traces the tile's opaque pixels into a simplified polygon (Godot's `BitMap.opaque_to_polygons` in the builder) — useful for irregular rocks and cliff edges.
* Filename keywords (`wall`, `tree`, `rock`, `cliff`, `fence`) only *suggest* a profile; suggestions appear in the audit as `AUTO-DETECTED`.
* Objects/buildings (scenes, not tiles) get **footprint collision**: a shape covering the bottom portion of the sprite, so the player can walk "behind" the top of a tree or house.

### Physics layer matrix (generated, named in project settings)

| Layer | Name | Collides with |
|-------|------|---------------|
| 1 | world | player, enemies, npcs |
| 2 | player | world, enemies, npcs, triggers |
| 3 | enemies | world, player |
| 4 | npcs | world, player |
| 5 | interactables | (detected by player interaction area) |
| 6 | triggers | player |
| 7 | player_hitbox | enemy_hurtbox |
| 8 | enemy_hitbox | player_hurtbox |
| 9 | player_hurtbox | enemy_hitbox |
| 10 | enemy_hurtbox | player_hitbox |

Defining this once prevents the most common class of ARPG bugs (hitboxes hitting their owner, enemies blocked by triggers).

---

## 18. Terrain

Terrain metadata is generated only when the pack provides compatible sets:

* RPG Maker A1/A2 autotiles → converted by the RPG Maker adapter into terrain sets (the adapter assembles the sub-tile quarters into a full set the Godot terrain system can use; generated composites live in `generated/terrain_atlases/`, never overwriting sources).
* 47-tile "blob" layouts and 16-tile "Wang/corner" layouts → recognized by tile count and arrangement; mapped to Godot's match-corners-and-sides / match-corners modes.
* Anything else → no terrain. The user still paints tiles manually. The generator never invents connectivity.

Terrain mapping is shown in the audit with a preview of the bitmask so the user can confirm it before generation.

---

## 19. Phase 8 — World Foundation

```text
game/maps/starter_map.tscn            (user-owned, created once)
Node2D "World"
├── Ground                (TileMapLayer)
├── GroundDetails         (TileMapLayer)
├── Walls                 (TileMapLayer, collision)
├── YSorted               (Node2D, y_sort_enabled)
│   ├── Props             (TileMapLayer, y_sort_enabled)
│   └── Entities          (Node2D — player, NPCs, enemies, placed objects)
├── Overhead              (TileMapLayer, drawn above entities)
├── Triggers              (Node2D — doors, exits, encounter zones)
├── SpawnPoints           (Node2D — Marker2D children with spawn_id)
└── Camera bounds         (computed from Ground used rect at runtime)
```

Y-sorting depends on consistent origins: every character and object scene positions its sprite so the node origin is at the feet/base (from the analyzer's baseline, §10). Without this, Y-sort looks wrong regardless of node setup.

Layer list is configurable in the wizard; this is the default.

---

## 20. Map Editing Acceptance Criteria

The generated project must open with no errors, and the user must be able to: select a TileMapLayer, see the TileSet, paint, erase, use terrain painting where terrains exist, toggle collision debug view, place characters/buildings/decor from the dock, save, close, reopen and continue.

Automated check: the builder opens the starter map, writes tiles via the TileMapLayer API on each layer, saves, reloads, and verifies the cells — proving the TileSet/layer wiring works without a human.

---

## 21. Editor Asset Library Dock

`addons/rpg_project_tools/` — an EditorPlugin providing:

* Searchable, filterable grid by category (from the catalog)
* Drag into the 2D viewport to instance (objects as scenes, single tiles as nothing — tiles stay in the TileMap editor)
* Placement defaults per asset: snap size, Y-sort parent, collision preset
* Flip H, rotate (where the asset allows), duplicate
* "Open in catalog" — edit overrides (role, collision profile, animation FPS) and write them to the catalog's override layer, with a "Regenerate affected resources" button that calls the builder in-editor
* "Rescan packs" — detects added/changed files and opens the wizard's audit for just those

Placed instances go under `YSorted/Entities` by default, with undo/redo support through `EditorUndoRedoManager`.

---

## 22. Object and Building Scenes

Generated base scenes in `generated/scenes/objects/`, one per catalog object:

```text
Node2D (script: world_object.gd, exported: asset_id, entity_id)
├── Sprite2D           (offset so origin = base)
├── StaticBody2D       (footprint collision)
├── InteractionArea    (Area2D, optional)
└── Entrance           (Marker2D, buildings only)
```

Template selection by role:

| Role | Template |
|------|----------|
| DECORATION (small) | `prop.tscn` — sprite + optional footprint |
| DECORATION (tree/rock) | `obstacle.tscn` — sprite + footprint collision |
| BUILDING | `building.tscn` — footprint + door trigger + interior link |
| Chest/sign (detected or user-tagged) | `interactable.tscn` — interaction + persisted state |

Users customize by creating an **inherited scene** in `game/`, never by editing the generated base (see §43).

---

## 23. Actor Scenes

```text
generated/scenes/actors/actor_base.tscn   CharacterBody2D
├── Visual (AnimatedSprite2D)
├── CollisionShape2D (feet)
├── Components (Node)
│   ├── Stats
│   ├── Movement
│   ├── AnimationDriver
│   └── Interaction
```

`player.tscn`, `npc.tscn`, `enemy.tscn` inherit from `actor_base.tscn`. Archetype-specific components (hitbox, hurtbox, AI) are added in archetype scenes.

Each concrete character (e.g., "hero", "merchant") is a small generated inherited scene that swaps in its `SpriteFrames` resource — so changing art never touches logic.

---

## 24. Animation Generation

Sources: adapter layouts, directional grids, per-file strips, GIFs.

Standard names (only those the art supports are created):

```text
idle_{down,up,left,right}   walk_{…}   attack_{…}   hurt_{…}   death
```

Rules:
* Missing `left` but present `right` → `left` generated by flipping at runtime (`flip_h` flag in the AnimationDriver), not by duplicating frames.
* Missing `idle_*` → first frame of `walk_*`.
* RPG Maker 3-frame walks use the 1-2-3-2 ping-pong order.
* FPS defaults: walk 8, idle 4, attack 12; overridable per animation.
* ARPG attacks record **active frames** (default: middle third) in the catalog; the hitbox is enabled only on those frames.

SpriteFrames are built by the Godot builder into `generated/sprite_frames/<asset_id>.tres`.

---

## 25. Project Settings

Set by the builder via `ProjectSettings` and saved — never hand-written.

Pixel-art defaults (all overridable in the wizard):

| Setting | Default |
|---------|---------|
| Base resolution | 640×360 (or derived: 320×180 for 16px packs is offered as an option) |
| Window override | 1280×720 |
| Stretch mode | `canvas_items` |
| Stretch aspect | `keep` |
| Scale mode | `integer` |
| Default texture filter | Nearest |
| Snap 2D transforms / vertices to pixel | On |
| Physics ticks | 60 |
| Main scene | `res://generated/scenes/bootstrap/boot.tscn` |

Camera: `Camera2D` with limits from the map's used rect; position smoothing off by default (smoothing plus pixel snapping causes visible jitter — the README explains how to enable it properly).

---

## 26. Input

Actions defined data-first in `config.json`, applied by the builder with keyboard, gamepad and (where relevant) mouse bindings:

* Shared: `move_up/down/left/right`, `interact`, `confirm`, `cancel`, `menu`
* ARPG: `attack`, `secondary_attack`, `dodge`, `quick_item`
* Turn-based: reuses `confirm`/`cancel`/`move_*` for menus — v1's separate `combat_*` actions are dropped as redundant; contexts are handled by which UI has focus

Keyboard bindings use physical keycodes so layouts like AZERTY work. Gameplay scripts read actions only, never devices. A small `InputGlyphs` helper reports whether the last input was keyboard or gamepad so UI prompts can show the right glyph.

---

## 27. Runtime Architecture

Autoloads (deliberately few):

| Autoload | Responsibility |
|----------|---------------|
| `Events` | Signal bus for decoupled cross-system events (`item_picked_up`, `entity_defeated`, `dialogue_finished`) |
| `GameState` | Pure gameplay data, no scene references |
| `SceneRouter` | Scene changes, transitions, spawn restoration |
| `SaveManager` | Serialization, atomic writes, migration |

Everything else (dialogue, inventory UI, combat) lives in scenes. This resolves v1's mention of an "event system" with no home.

### GameState

```gdscript
var player: ActorData
var party: Array[ActorData]
var inventory: Inventory
var gold: int
var current_map: StringName
var current_spawn_id: StringName
var pending_encounter: EncounterData
var world_flags: Dictionary   # entity_id -> {defeated, opened, collected}
var quest_state: Dictionary
var rng_seed: int
```

### SceneRouter

`go_to(map_id, spawn_id)`, `push_scene(scene, payload)` / `pop_scene()` for combat and interiors, fade transitions, optional loading screen for large maps via threaded loading. Only SceneRouter calls `change_scene_*`.

### Entity IDs

Every persistent entity (enemy, chest, NPC with state) has an exported `entity_id`. The editor dock auto-assigns unique IDs on placement (`<map>_<type>_<n>`), and a validation pass reports duplicates or empty IDs across all maps.

---

## 28. Save System

* Format: JSON with explicit serialization (Vector2 and similar stored as arrays; no `var_to_str` of arbitrary objects, which is brittle across versions and unsafe to load from untrusted files).
* Schema-versioned with forward migrations and tests for each migration.
* **Atomic write:** write `slot_N.tmp` → flush → verify by re-reading and parsing → move existing `slot_N.json` to `slot_N.backup.json` → rename tmp to `slot_N.json`.
* **Corruption detection:** a content checksum field; on load failure, fall back to backup and notify the player.
* Multiple slots (`user://saves/slot_1.json`, …), each with a small header (timestamp, map, playtime, level) for the load menu.

```json
{
  "save_version": 1,
  "checksum": "…",
  "header": { "timestamp": "…", "map": "starter_map", "playtime_s": 512 },
  "player": {}, "party": [], "inventory": [], "gold": 100,
  "world": { "current_map": "…", "spawn_id": "…", "position": [128, 96] },
  "world_flags": {}, "quests": {}
}
```

---

## 29. Dialogue

Dialogue is a Godot Resource so it's editable in the Inspector without extra tooling:

```gdscript
class_name DialogueResource extends Resource
@export var lines: Array[DialogueLine]   # speaker, portrait, text, choices, condition, event
```

* `condition` and `event` are simple strings evaluated against `GameState` flags (e.g., `has_item:key_01`, `set_flag:met_merchant`) — no arbitrary code execution.
* A one-way importer converts JSON (v1's example format) into resources for users who prefer writing dialogue as text.
* The design leaves room to swap in a third-party dialogue addon later; NPCs depend on a `DialogueSource` interface, not the concrete format.

---

## 30. Items, Inventory, Stats

* `ItemDefinition` (Resource): id, name, icon (from catalog), category, stack size, value, stat modifiers, use effect.
* `Inventory`: slots of `{item_id, quantity}` — references by ID so saves don't embed resources.
* Categories: Consumable, Weapon, Armor, Accessory, Quest, Key, Material.
* Item resources generated for catalog assets with role ITEM (as editable starting points) into `game/data/items/` — created once, user-owned thereafter.

Stats: a base `Stats` resource (`level, experience, max_hp, hp, attack, defense, speed`) with archetype extensions via composition (`RealtimeStats`: move_speed, attack_speed, crit_chance, knockback; `TacticalStats`: magic, resistance, initiative). Derived stats come from a single `get_stat(name)` that applies equipment modifiers, so combat code never reads fields directly.

---

## 31. Turn-Based Archetype

Files: `battle.tscn`, `battle_controller.gd`, `turn_manager.gd`, `battle_actor.gd`, `battle_command.gd` (Resource).

States: `INITIALIZE → PLAYER_TURN → SELECT_TARGET → EXECUTE → ENEMY_TURN → CHECK_RESULT → VICTORY | DEFEAT | ESCAPED`.

Commands are `BattleCommand` resources (Attack, Defend, Item, Skill, Run) so new commands are data, not code changes. Turn order by `speed`/`initiative`. All randomness goes through a seeded RNG from `GameState` (enables the smoke test and reproducible bug reports).

Encounter flow: contact/interaction → `EncounterData` (enemy group, entity_id, return map/position) → `SceneRouter.push_scene(battle)` → result → mark defeated, grant XP/gold/loot via `Events` → `pop_scene()` restores the map and position. Enemy sprites in battle reuse the same SpriteFrames as the overworld (scaled if needed).

---

## 32. ARPG Archetype

**Player:** states `IDLE, MOVE, ATTACK, HURT, DODGE, DEAD`. Components: Movement, CombatController, AnimationDriver, Hurtbox, AttackHitbox, Stats. Hitbox enabled only on active frames. Hurt state grants brief invulnerability. Attack input buffered for a few frames so combat feels responsive.

**Enemy:** states `IDLE, WANDER, ALERT, CHASE, ATTACK, HURT, STUNNED, DEAD`. Separate components for Detection (vision radius + line-of-sight raycast), Navigation, Movement, Combat, Health, Loot, AnimationDriver. Behavior parameters live in an `EnemyDefinition` resource so tuning is data.

**Damage:** a single `DamageInfo` object (amount, source, knockback vector, flags) passed hitbox → hurtbox. Knockback applied through Movement, not by setting position directly.

**Navigation:** direct pursuit with simple obstacle sliding by default. Optional `NavigationAgent2D` mode using a navigation region baked from the map's walkable area (TileSet navigation polygons or a baked `NavigationRegion2D`), enabled per-map. The navigation layer is generated in the TileSet so switching on later is a checkbox, not a rework.

---

## 33. UI

All UI is scene-based, themed through one generated `Theme` resource:

* If the pack has UI assets, the theme uses them (9-slice panels via `StyleBoxTexture`, pack fonts if licensed).
* Otherwise a clean, readable default theme.

Shared: TitleScreen, PauseMenu, DialogueBox, InventoryMenu, StatsMenu, Notifications, SaveLoadMenu, Settings (volume, fullscreen, controls).
ARPG: HUD (health, quick item, gold).
Turn-based: CommandPanel, BattleLog, PartyStatus, EnemyStatus.

Every menu is fully navigable by gamepad (focus neighbors set, initial focus defined) — this is validated automatically by a script that walks each menu's focus chain.

---

## 34. Audio

* Buses: Master, Music, SFX, UI (generated `default_bus_layout.tres`).
* `AudioService` (scene-owned, not autoload) plays music with crossfade and SFX by catalog ID.
* Pack audio is classified (§11) and wired into the demo where sensible (footsteps, hit, menu blip, overworld music).

---

## 35. Starter Content

A small demo that exercises every system and doubles as the smoke-test target:

```text
Title → New Game → starter_map
  Player spawns → talk to NPC (dialogue) → enter building (interior scene)
  → exit → chest (item + persistence) → enemy (combat for chosen archetype)
  → reward → save point → (reload) → state restored
```

Demo content lives in `game/demo/` and is user-owned: deleting the folder removes it cleanly, and a "Remove demo content" button in the dock does the same and updates the main scene.

---

## 36. Generated Project Structure

```text
MyRPG/
├── project.godot
├── README.md                     # how to paint maps, add NPCs, regenerate
├── GENERATION_REPORT.md
├── rpggen/                       # generator metadata (do not edit by hand)
│   ├── asset_catalog.json
│   ├── generator_config.json
│   └── ownership_ledger.json
│
├── addons/rpg_project_tools/     # generated-owned
│
├── assets/packs/<pack_id>/…      # verbatim source packs
│
├── generated/                    # OWNED BY GENERATOR — may be rewritten
│   ├── core/                     # autoloads, base classes
│   ├── archetype/                # turn_based OR arpg systems
│   ├── tilesets/                 # merged in place, never replaced
│   ├── terrain_atlases/
│   ├── sprite_frames/
│   ├── scenes/{bootstrap,actors,objects,ui,battle}/
│   ├── theme/
│   └── debug_placeholders/
│
└── game/                         # OWNED BY USER — created once, never overwritten
    ├── maps/
    ├── characters/               # inherited scenes customizing generated ones
    ├── data/{items,enemies,dialogue}/
    ├── scripts/
    └── demo/
```

---

## 37. Phase 9 — Godot-Native Build

The builder is a permanent part of the generated project (`generated/builder/`), not a temporary script — because the in-editor "Regenerate affected resources" button reuses it. It runs headless during generation:

1. **Import:** run Godot headless with the `--import` flag so all textures have import data before anything references them. Fallback if unavailable: a short headless editor launch that waits for the import scan to finish.
2. **Build:** `godot --headless --path <staging> --script res://generated/builder/build.gd -- --config res://rpggen/generator_config.json`
   * applies project settings and input map
   * builds/merges TileSets
   * builds SpriteFrames
   * instantiates templates into concrete generated scenes and saves them with `ResourceSaver`/`PackedScene.pack`
3. Writes `rpggen/build_results.json` (created/updated/skipped resources, warnings) for the Python side to read. Exit code signals success.

### Resource UIDs

The generator never fabricates `uid://` strings. Resources are saved by the engine, which assigns and manages UIDs. Template files in the repo already carry valid UIDs generated by the editor; copying them preserves references. Validation (§38) confirms every reference resolves.

---

## 38. Phase 10 — Validation

| Check | How |
|-------|-----|
| Script parse | Load every `.gd` via a validation script; additionally `--check-only` per script; collect errors from the log |
| Resource load | `ResourceLoader.load` every `.tres`/`.tscn` under `generated/` and `game/`; fail on null or errors |
| Dependency integrity | `ResourceLoader.get_dependencies` for each resource; every dependency must exist |
| Scene instancing | Instantiate every scene headless; free it; capture errors |
| TileSets | Each source has a valid texture; every tile region lies within the texture; every catalog `source_id` exists |
| SpriteFrames | Every animation has ≥1 frame with a valid texture |
| Project | Main scene exists; autoloads load; all input actions defined have ≥1 event |
| Entity IDs | No duplicates or empties across maps |
| UI focus | Every menu has initial focus and complete focus neighbors |
| Map round-trip | Write cells on each layer, save, reload, compare (§20) |

Errors and warnings are written to `validation_results.json`, each with a code from §44.

---

## 39. Smoke Test

Runs the actual game headless with `--` user args (`--smoke-test`), which activates a `SmokeTestRunner` autoload that exists only in that mode.

Design:
* Seeded RNG; fixed player stats from a test profile so combat outcome is deterministic.
* Drives the game through **service APIs** (e.g., `SceneRouter.go_to`, `player.interact()`, battle command selection) for reliability, plus a short **input-path check** that injects `move_right` via `Input.action_press` and verifies the player actually moved — proving input wiring without depending on input for every step.
* Each step has a timeout and records pass/fail with a reason.

Steps: boot → title → new game → spawn → move (input-path) → NPC dialogue → enter/exit building → open chest → encounter → combat completes with victory → rewards granted → save → quit-to-title → load → verify position, inventory, defeated enemy, opened chest.

Any validation or smoke-test failure **blocks delivery** (decision record §51, item 6). Nothing is promoted to the target folder. The failed staging folder is kept as `.rpggen_failed/<timestamp>/` so the user or a contributor can open it and see what broke. It is clearly labeled as not a deliverable and is pruned after 3 failures. The report names the failing step and its error code.

---

## 40. Transaction Model

```text
Target/
  .rpggen_staging/   ← full generation + validation happens here
```

1. Copy (or hard-link where safe) the existing target into staging for regeneration; empty for new projects.
2. Generate, build, validate, smoke-test in staging.
3. On success: back up files about to change to `Target/.rpggen_backups/<timestamp>/`, then promote changed files from staging into the target.
4. On failure: delete staging; target untouched; report explains why.

Keep the last 3 backups. "Restore previous generation" is a wizard button.

Note: `.godot/` (import cache) in staging is reused between runs to avoid reimporting everything each time.

---

## 41. Regeneration and Ownership

### The ownership ledger

`rpggen/ownership_ledger.json` records every file the generator wrote, with the hash it wrote.

On regeneration, for each generated file:

| On-disk state | Action |
|---------------|--------|
| Unchanged since generation (hash matches ledger) | Overwrite freely |
| Modified by user (hash differs) | Don't overwrite; write `<file>.rpggen-new` beside it and report a conflict with a diff summary |
| Deleted by user | Respect the deletion; don't recreate unless the user asks |
| TileSet | Always merge in place (§16), never overwrite |

Files in `game/` are created only if they don't exist and are never touched again.

### Customization pattern

The README teaches one rule: **to change a generated scene, create an inherited scene in `game/`**. To change generated script behavior, extend the class in `game/scripts/`. This is what makes regeneration safe in practice — the ledger is the safety net, not the plan.

### Pack updates

When a pack is updated (new version from the vendor), the generator diffs the inventories by path and hash:
* New files → added to audit as `NEEDS REVIEW`.
* Changed files with same dimensions → updated silently, IDs kept.
* Changed dimensions on a tile atlas → `CONFLICT`: tiles may have shifted; the user must review before maps are affected.
* Removed files → `MISSING`; resources kept until confirmed.

---

## 42. Configuration

`rpggen/generator_config.json` (schema-validated, versioned):

```json
{
  "config_version": 1,
  "godot_version": "4.7.2",
  "project_name": "My RPG",
  "archetype": "turn_based",
  "packs": [{ "pack_id": "forest_pack", "source": "C:/Packs/forest.zip" }],
  "base_tile_size": 16,
  "resolution": [640, 360],
  "window_size": [1280, 720],
  "map_layers": ["Ground", "GroundDetails", "Walls", "Props", "Overhead"],
  "features": {
    "tilesets": true, "collision": true, "terrain": true, "animations": true,
    "demo": true, "editor_tools": true, "save": true, "dialogue": true,
    "combat": true, "navigation": false
  },
  "validation": { "smoke_test": true, "strict": true }
}
```

The wizard loads it automatically on regeneration.

---

## 43. Wizard

1. **Project** — pack(s), output folder, Godot path, name. Inline validation per field (green/red, with fix text).
2. **Archetype** — two large cards. Disabled options explain why (e.g., "ARPG needs at least one attack animation or will use a placeholder swing effect").
3. **Audit** — grid, filters, bulk actions, grid/animation editors (§13).
4. **Mapping** — required-role checklist; assign player, starter NPC, starter enemy, ground tileset, building.
5. **Options** — features, resolution, layers, validation strictness. Sensible defaults; "Advanced" collapsed.
6. **Generate** — phase progress with live log; cancel is safe at any point (staging is discarded).
7. **Results** — counts, warnings, errors; Open in Godot / Open Folder / View Report / Restore Previous.

---

## 44. Errors and Reporting

Structured error codes by area:

```text
ENV-xxx      preflight
ARCH-xxx     archive/extraction
ASSET-xxx    analysis/classification
CAT-xxx      catalog/migration
TILE-xxx     TileSet/terrain/collision
ANIM-xxx     SpriteFrames
BUILD-xxx    Godot builder
VAL-xxx      validation
SMOKE-xxx    smoke test
REGEN-xxx    ownership/conflicts
```

Each: `code, severity (error|warning|info), file, problem, recommended fix, status`. Every code is documented in `docs/errors.md`, and the report links to it.

`GENERATION_REPORT.md` contains: versions, packs and licenses, asset counts by role and status, detected tile sizes, TileSets (with source IDs), scenes, animations, placeholders in use, conflicts, validation results, smoke-test results, and a **"What to review"** section listing every human decision still pending, ordered by importance.

Full logs go to `rpggen/logs/` (generator and each Godot invocation).

---

## 45. Performance Targets

| Scenario | Target |
|----------|--------|
| Inventory + analysis, 1,000-image pack, cold cache | < 60 s |
| Same, warm cache | < 5 s |
| Audit grid scroll with 2,000 assets | smooth (virtualized) |
| Full generation + validation + smoke test, medium pack | < 5 min |
| Regeneration with no asset changes | < 1 min |

Analysis is parallelized across processes; Godot import cache is reused across regenerations.

---

## 46. Testing the Generator

This was absent from v1 and is the main determinant of quality.

**Fixture corpus (`test_packs/`):**
* Synthetic packs generated by script: known grid sizes, margins, separations, strips, RPG Maker-like and LPC-like layouts, deliberately tricky cases (gutterless sheets, mixed sizes, case-colliding names, nested zips, Unicode names).
* A few permissively licensed (CC0/CC-BY) real packs.
* Each fixture has an `expected.json` (tile sizes, roles, animation sets).

**Test layers:**
* Unit: analyzer, classifier, catalog migrations, ledger logic, archive safety.
* Golden: generated catalog and file list compared to committed golden output (determinism check).
* Integration (CI, Windows): full generation for each fixture with Godot 4.7.2 headless — must pass validation and smoke test, for every archetype.
* Regeneration: generate → simulate user edits (paint tiles, modify a generated scene, add files to `game/`) → update pack → regenerate → assert painted cells identical, user files untouched, conflicts reported.
* Template project: `godot_templates/` has its own GDScript tests (e.g., GUT or a minimal in-house runner) for combat math, save migration, inventory.

**Classification accuracy** is tracked as a metric over the corpus, per role, so heuristic changes can't silently regress.

---

## 47. Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Heuristic classification is wrong on real packs | High — bad first impression | Adapters first; fast bulk-review UI; shared pack profiles; accuracy metric in CI |
| Regeneration corrupts painted maps | Critical | Stable source IDs, in-place TileSet merge, regeneration tests |
| Godot format/API differences | High | Engine writes all engine resources; pinned version; engine-assumption tests |
| Smoke test flaky | Medium — blocks generation | Seeded RNG, service-level drivers, per-step timeouts, permissive mode |
| Scope creep (two full archetypes + plugin + wizard) | High — never ships | Walking skeleton; one archetype to beta before the second |
| Pack licenses (e.g., RPG Maker RTP) | Medium — legal risk for users | License surfacing, RTP detection warning |
| Antivirus flags packaged exe | Medium | One-folder build, code signing certificate |
| Windows path/locking issues | Medium | Long-path checks, cloud-folder warning, retrying file ops |

---

## 48. MVP Scope

### MVP (v0.1 — "paint and walk")

* CLI + minimal wizard (project, audit with bulk edit, generate, results)
* ZIP and folder input, safe extraction, inventory, cache
* Generic grid + RPG Maker adapters
* Analyzer with margin/separation detection
* Catalog with override layer and stable IDs
* Godot builder: project settings, input, TileSets with collision, SpriteFrames
* Starter map with layers, player with 4-direction movement, camera, one NPC with dialogue, one building with interior transition
* Ownership ledger + staging + regeneration merge
* Validation (all §38 checks except UI focus)
* Report

### v0.2 — first archetype (recommend turn-based: simpler to make robust, and smoke-testing is deterministic by nature)

* Stats, inventory, items, save/load, encounters, battle, rewards, persistence, title/pause/menus, smoke test

### v0.3 — editor dock + terrain

* Asset Library dock, placement, catalog overrides in-editor, terrain support, LPC adapter

### v0.4 — ARPG archetype

### Deferred (unchanged from v1)

Procedural dungeons, skill trees, advanced equipment UI, multiplayer, complex AI planners, modding, localization editor.

Done since (M13, release 1.1.0): a planned world of connected areas with a lock and its key
(`world_plan.py`, `lockkey.py`), and the dock's Quests tab with its stage graph. The graph is a
picture of the stages, not a free-form graph editor.

### v1.2 — more archetypes (M14)

A third archetype, the **metroidvania**, shows what a new archetype costs and where it lives:

* its runtime in `addons/rpg_runtime/archetypes/metroidvania/`, its recipes in
  `builder/recipes/metroidvania/`, its smoke steps in `builder/smoke/`: the install filter
  (`staging.ARCHETYPES`) keeps each archetype's three folders out of the projects of the others;
* what two archetypes share moves **out** of an archetype folder into a shared one, with a shim
  at the old path for all of 1.x: the real-time combat set (hitbox, hurtbox, health, projectile,
  state machine, pickup, screen feedback) is `combat/realtime/`, used by the action RPG and the
  metroidvania;
* a shared recipe changes its output only for the archetype that needs it (the side-view
  TileSet layers, the room HUD), so a project of another archetype is byte for byte what it was;
* the world is planned in Python (`room_plan.py`, with the lock-and-key order of `lockkey.py`)
  and stored in `rpggen/world_plan.json`; the recipe only paints the stored plan, and a stored
  plan is never planned again (section 12 of the schemas);
* an archetype whose world is not the top-down starter map brings a whole smoke sequence of its
  own (`orchestrator.OWN_SMOKE_STEPS`) and its own sample pack, so the samples, goldens and
  screenshots of the others do not change;
* saves stay `save_version` 1: what the archetype adds are optional keys, written only when
  they hold something.

A fourth archetype follows the same list. Its integration suite gets a pytest marker and a CI
job of its own.

---

## 49. Development Order and Exit Criteria

| Milestone | Content | Exit criterion |
|-----------|---------|----------------|
| M1 Walking skeleton | CLI, one hard-coded fixture pack → project with one TileSet and a player that moves; headless validation; CI on Windows | CI green: generated project opens, validates, player moves in smoke test |
| M2 Asset intelligence | Archive hardening, analyzer, adapters, classifier, catalog, cache | ≥90% correct tile size and ≥80% correct primary role on the fixture corpus |
| M3 Wizard + audit | GUI pages 1, 3, 6, 7; bulk editing | A non-developer tester maps a 500-asset pack in < 15 min |
| M4 World & placement scenes | Layers, object/building templates, interior transition, Y-sort origins | Map round-trip test passes; objects sort correctly in screenshot test |
| M5 Regeneration safety | Ledger, staging promotion, TileSet merge, pack diffing | Regeneration test suite passes (painted cells identical) |
| M6 Shared RPG systems | Stats, items, inventory, dialogue, save/load, router | Save → load round-trip and migration tests pass |
| M7 Turn-based | Encounters, battle, rewards, persistence, battle UI | Full smoke test passes on all fixtures |
| M8 Editor dock + terrain | Dock, overrides, regenerate-in-editor, terrains | Place 10 assets via dock, regenerate, all remain intact |
| M9 ARPG | Player/enemy states, hitboxes, AI, HUD | ARPG smoke test passes on all fixtures |
| M10 Release hardening | Packaging, signing, docs, error docs, performance targets | Definition of Done met on 5 unseen packs |

Validation is not a milestone — it grows with every milestone from M1.

---

## 50. Definition of Done

Given a previously unseen, reasonably structured 2D RPG asset pack, a user can run the wizard and receive a Godot 4.7.2 project that:

* opens with zero errors and imports all supplied assets
* has TileSets with correct tile size, margins and separation, and collision where configured
* supports painting on editable TileMapLayers, including terrain painting where the pack supports it
* allows placing buildings, objects and characters via the Asset Library dock, with correct Y-sorting
* supports movement, NPC dialogue, scene transitions, save/load and the selected combat archetype
* passes headless validation and the smoke test
* reports every unresolved asset, placeholder, license note and conflict
* leaves source assets byte-identical
* can be regenerated after a pack update without changing a single painted tile or user-owned file

Measured against a held-out set of at least 5 commercial or free packs not used during development, with time-to-first-paint under 10 minutes for each.

---

## 51. Decision Record

| # | Decision | Resolution | Consequences |
|---|----------|-----------|--------------|
| 1 | First archetype | **Turn-based** | v0.2 ships turn-based; ARPG is v0.4. Both stay behind the `CombatMode` contract (§6) from day one. |
| 2 | GUI toolkit | **PySide6** | LGPL. Dynamic linking through the PyInstaller one-folder build is compatible with an open-source release. |
| 3 | Distribution | **Free / open source** | See §52 for licensing, contributions and community features. |
| 4 | Pack layout priority | **Metadata formats first, then layout standards, then vendor profiles** | §9 tiers. Rationale below. |
| 5 | Dialogue | **Built-in `DialogueResource`** behind a `DialogueSource` interface | A third-party addon can be swapped in later without touching NPC code. |
| 6 | Validation failure | **Block delivery** | §39. The failed staging folder is kept for diagnosis. There is no override flag in the GUI. The CLI's `--keep-failed` only keeps artifacts and never promotes them. |

### Rationale for decision 4

The goal is the most packs handled correctly for the least adapter work. Three observations drive the order:

1. **Many packs already ship machine-readable metadata.** These are Tiled `.tsx`/`.tmx` files, Aseprite JSON exports and sometimes LDtk projects. Reading that metadata is exact rather than heuristic. It covers packs from any vendor that included it, and Tiled Wang sets give terrain data that would otherwise be the hardest thing to infer. This is the highest-leverage work, so it comes first.
2. **Layout standards cover whole ecosystems.** "RPG Maker format" and LPC are each followed by many unrelated vendors. One adapter therefore handles hundreds of packs.
3. **Vendor-specific layouts are a long tail.** These are best handled as data (pack profiles) that the community contributes. Hard-coding them in the generator would turn it into a maintenance burden.

Validation step at the start of M2: sample about 30 popular top-down RPG packs (free and paid). For each, record which tier would handle it and estimate overall coverage. If one vendor family covers a large share of the uncovered packs, promote it to a built-in profile for v0.1.

---

## 52. Open-Source Specifics

### Licensing
* **Generator:** MIT. It matches Godot's license and is familiar to the Godot community.
* **Code copied into users' games** (runtime scripts, scenes, the editor plugin): **MIT No Attribution (MIT-0)**. Users ship this code inside their commercial games. They should never have to add a credits line or license notice for a starter template. This is easy to overlook and very hard to change later.
* **Bundled sample pack:** CC0 only (§55).

### Test corpus and commercial packs
Commercial packs can't be committed to a public repository. The corpus is split:
* **Public CI corpus:** synthetic packs plus CC0 packs, committed to the repo.
* **Private corpus:** commercial packs that maintainers own, run locally with `rpggen test --corpus <dir>`. Only the results (the `expected.json` files and accuracy metrics) are shared, never the assets.

### Contribution surfaces
Contributors can add these without touching core code:
* Pack profiles (JSON, §53)
* Adapters (Python plugins with a documented interface)
* Error-code documentation and translations of the wizard UI

`CONTRIBUTING.md` includes a step-by-step guide for adding a pack profile. This is the most likely first contribution for most people.

### Privacy
No telemetry. The generator never makes network requests except an optional, user-initiated check for updates.

---

## 53. Pack Profiles and a Community Profile Registry

A **pack profile** is a JSON file that maps a specific pack, identified by file hashes and paths, to its confirmed catalog decisions: roles, grids, animations, collision and terrains. It contains no images.

* After a user finishes the audit, they can choose "Export pack profile."
* Profiles live in a separate public repository (`rpggen-profiles`). The wizard can search it by pack fingerprint, and offline import works too.
* A matching profile pre-fills the audit with `CONFIRMED` entries. Mismatched files, such as those from a newer pack version, fall back to normal detection.
* The profile schema is versioned and validated in CI for that repository.

For an open-source project, this registry is the strongest long-term asset. Every pack mapped once by anyone becomes zero-effort for everyone after.

---

## 54. Multi-Tile Objects ("Object Cutter")

This was missing from v1 and v2, and it is a major real-world gap. Many packs don't ship buildings, trees and large furniture as separate images. Instead they are **regions inside a tilesheet**: a house might occupy 5×4 tiles of a larger atlas.

Additions:
* **Audit tool:** drag a rectangle (or lasso a set of cells) on a sheet to define an object. Give it a name and role, and mark which rows form the collision footprint.
* **Auto-suggest:** detect connected non-empty regions surrounded by empty cells and propose them as objects.
* **Two outputs per object, both generated:**
  1. A **TileSet pattern**, so the object can be stamped in the TileMap editor.
  2. A **scene** (§22) whose sprite uses an `AtlasTexture` region. This gives correct Y-sorting, interaction and persistence.
* Tiled `.tsx` "collection of images" tilesets and Tiled object templates are imported directly as objects.
* Optionally, each TileSet can get a **scene collection source**, so placed objects can also be painted with the TileMap tools.

The source image is never cropped or modified. Objects are only references to regions.

---

## 55. Bundled Sample Pack and "Try It" Mode

* Ship a small CC0 sample pack, either assembled from CC0 sources or commissioned and released as CC0.
* Add a wizard button, "Try with sample pack," that runs the whole flow in under two minutes.
* Benefits: new users see the tool working before they commit a purchased pack. It also gives documentation screenshots and a reproducible reference for bug reports.

---

## 56. Version Control Friendliness

Most users will (and should) put the generated project in git. The generator writes:
* A `.gitignore` covering `.godot/`, `*.tmp`, `.rpggen_staging/`, `.rpggen_failed/` and `.rpggen_backups/`.
* A `.gitattributes` with `* text=auto eol=lf` for Godot text files. It also includes an **optional** Git LFS section for images and audio, which the wizard offers but does not enable by default.
* Deterministic output (§2.4), so regenerating with no changes produces **zero git diff**. Add this as a CI assertion.
* A wizard checkbox to run `git init` and commit the first generation, if git is installed.

---

## 57. Runtime as a Versioned Addon

The shared runtime (core, archetypes, UI base scenes) is packaged as `addons/rpg_runtime/` with its own semantic version and changelog, instead of being loose files under `generated/core/`.

* A runtime bug fix in a new generator version updates existing projects on regeneration. The ownership ledger still protects any files the user edited.
* The runtime's public API (classes, signals, resource fields) follows semver. Breaking changes require a major version bump and come with a migration note in the report.
* The addon can also be published on its own to the Godot Asset Library. This brings in users who never run the generator, which helps an open-source project grow.

---

## 58. Developer Quality-of-Life Inside the Generated Game

These are cheap to generate and save users hours:
* **Debug overlay / console** (development builds only): teleport to a spawn, give an item, set a flag, start an encounter, toggle collision shapes, show the FPS.
* **Map quick-start:** run the current map directly from the editor with the player at a chosen spawn, without going through the title screen.
* **Content validator in the dock:** one button checks for duplicate entity IDs, unreachable spawns, doors to missing maps, dialogue that references missing flags and placeholders still in use.
* **Export preset:** generate a Windows export preset, and run a test export in CI when export templates are available. "Can I actually ship this?" should be answerable from day one.

---

## 59. Future-Proofing the Generated Game (Cheap Now, Expensive Later)

* **Translation-ready text:** all generated UI strings and dialogue go through `tr()` keys from day one, with a starter CSV translation file. The localization *editor* stays deferred, but retrofitting `tr()` into a finished game is painful.
* **Remappable controls:** the Settings menu includes rebinding for keyboard and gamepad, persisted to `user://settings.cfg`.
* **Accessibility basics:** text speed setting, "instant text" option, adjustable UI scale and no information conveyed by color alone in generated UI.
* **Steam Deck / handheld:** the default 16:9 resolution with integer scaling is verified at 1280×800. Gamepad-only navigation already exists (§33).

---

## 60. Diagnostic Bundles for Bug Reports

Open-source maintainers live and die by bug-report quality. Add "Export diagnostic bundle" to the results page and an error dialog. It produces a zip containing:
* Logs, the config, the catalog, validation results and the build results.
* Image **dimensions and hashes only**. Asset files are excluded, so users can attach the bundle publicly without redistributing paid art.
* System info (Windows version, Godot version, generator version).

The GitHub issue template asks for this bundle.

---

## 61. Cross-Platform Generator (Later)

Windows stays the primary target. Python, PySide6 and Godot are all cross-platform, though, and Godot's community has a large Linux and macOS share. Keep the platform-specific code (path handling, long-path checks, executable detection) isolated in one module from M1. That way, Linux and macOS builds become a packaging task in v1.x rather than a rewrite. Add a Linux CI job early. It also catches path-case bugs that Windows hides.

---

## 62. Updated Milestone Notes

The new sections slot into §49 as follows:
* **M1:** MIT/MIT-0 licensing in place; `.gitignore`/`.gitattributes`; the zero-diff regeneration assertion; platform module isolated.
* **M2:** Tier 1 adapters (Tiled, Aseprite) before RPG Maker; the pack-coverage sampling study (§51).
* **M3:** object cutter (§54); pack profile export/import (§53); sample pack and "Try It" mode (§55).
* **M6:** `tr()` keys; settings with remapping; runtime packaged as an addon (§57).
* **M8:** debug overlay; content validator; map quick-start (§58).
* **M10:** diagnostic bundles; code signing; community profile registry live; export preset test.

---

## 63. Final Architecture

```text
              PYTHON GENERATOR                    (analysis, decisions, safety)
     ┌──────────────┼───────────────┐
 Adapters +     Catalog +        Ownership ledger +
 Analyzer       Overrides        Staging transactions
     └──────────────┼───────────────┘
                    ▼  data only (catalog, config)
            GODOT 4.7.2 BUILDER                  (all engine resources)
     ┌──────────────┼───────────────┐
 TileSets       SpriteFrames     Scenes, settings, input
     └──────────────┼───────────────┘
                    ▼
     VALIDATION + SMOKE TEST (headless)
                    ▼
            GENERATED PROJECT
   generated/ (rebuildable) │ game/ (yours, forever)
                    ▼
            HUMAN GAME DESIGN
```

The generator decides what the assets are. Godot builds what Godot needs. The user owns everything they make — and regeneration is guaranteed never to take it away.
