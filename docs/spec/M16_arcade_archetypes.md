# M16 — More Kinds of Game (release 1.4.0)

**Goal:** three new archetypes asked for on 2026-10-09, built on what the three existing ones
share: a **shoot 'em up** (vertical or horizontal), a **run and gun** in the line of Contra with
the grapple of Bionic Commando as an option, and a **racing game** in the line of RC Pro-Am.
Part A is the arcade framework they share (stages, lives, score, scrolling, spawners, bosses,
a continue screen and high scores), Parts B–D are the archetypes, Part E the wizard, the
samples, the documentation and the gate. Part F sketches the kinds that were considered and
should follow in M17, with what each reuses, so the order can be chosen later.

This file follows the format of M01–M15. It was written against the branch `m14` on 2026-10-09,
before M15 (the look and feel, release 1.3.0). **This milestone starts after `v1.3.0` is
tagged** and ends with `v1.4.0`. Nothing in it changes an existing archetype: a 1.0–1.3 project
regenerates with 1.4 without a prompt.

## What the three kinds are

| Kind | Key | Seen from | The game, in one line | Reuses most |
|------|-----|-----------|------------------------|-------------|
| Shoot 'em up | `shmup` | the top (vertical) or the side (horizontal); an option | A ship flies over a scrolling background, shoots waves of enemies, collects power-ups and beats a boss at the end of each stage | real-time projectiles (T12.67), parallax backgrounds (T14.02), the HUD and save framework |
| Run and gun | `run_and_gun` | the side | A soldier runs right through a stage, jumps, aims in eight directions, picks up weapons, and fights a boss at the end; with the grapple option the arm swings and hoists instead of (or as well as) jumping | the platform actor, side camera, side tiles and enemies of the metroidvania (M14), projectiles |
| Racing | `racing` | the top | A car races AI rivals around a track of tiles, over laps with checkpoints and pickups, through a championship of tracks | tilesets and collision (M1–M4), the starter-map planner's style of pure-Python plan, the HUD, saving |

## What the real packs look like

Six packs the user will use were listed on 2026-10-09 (file names and image sizes only; the
art was not opened). They decide the word lists and the adapter work of T16.02 and T16.21.

| Pack | Kind | What it taught |
|------|------|----------------|
| *Wheels in Pixels* (CC0, 226 files) | racing | Every vehicle is a **16-heading rotation sheet**: `Classic_Bug.png` is 736 × 54 (16 frames of 46 × 54, as its `README_Grid_Sizes.txt` says), the small ones 512 × 32 (16 of 32 × 32). Colour variants are separate files (`Classic_Bug_red.png`). Folders `Cars`, `Bikes`, `Tilesets`, `Enviroment` (misspelt), `VFX/Nitro`, `VFX/Smoke`. The track tiles are 192 × 64 sheets (`race_track_1.png`, `grass_dirt_mix.png`): the 47-tile blob layout rpggen already reads, with `_mix` for a transition between two surfaces. `barrier_red.png` 144 × 16, `tire.png` 16 × 16, a `Grid Slots.png` guide picture to ignore. |
| Eight *Side-Scroller Tileset* packs (10 files each) | run and gun, metroidvania | Tiles only, no characters: every pack is ten 256 × 256 sheets named by content with a number prefix, spaces and ampersands: `1. Ground & Terrain Tiles.png`, `2. Platform Tiles.png`, `3. Walls & Cliffs.png`, `4. Background Decorations.png`, `8. Hazards Pack.png`, `9. Collectibles & Props.png`, `10. Doors, Windows & Architectural Pieces.png`; themed packs vary the words (`Haunted Platforms & Suspended Walkways`, `Bridges & Traversal Structures`, `Lava Chambers`, `Traps, Hazards & Dungeon Gameplay Objects`). One zip name and one file name carry an emoji. Props and tiles share a sheet: the object cutter is the tool. |
| *Dark Cursed Village* (rar, 287 entries) | run and gun, metroidvania | A **numbered-frame export with no action words**: `CHARACTER/CHARACTER1.png` … `CHARACTER168.png`, every frame 142 × 142, with 29 blank 123-byte frames as separators between animations; the same for `PROPS/BOX/BOX1..16` (96 × 96), `FLAME1..16` (32 × 128), `PORTAL1..31` (960 × 512), `POST`. Beside each set the **`.aseprite` source** (`CHARACTER.aseprite`), whose tags name the animations. `BACKGROUD/BACKGROUND (1) .png` … `(4)` (480 × 480 parallax layers; a typo and a space before the extension), `TERRAIN/TERRAIN.png`, `SCENE/HOUSE (1).png` (480 × 270), a `PREVIEW` folder of GIFs and a `test.png` to ignore. |
| *Super Retro Ranch* premium (1,040 files; not CC0: credit asked, no redistribution, no NFT or AI use) | farm (M17), top-down | A strict naming scheme `<thing>_<nn>_<colour>_<action>_<direction>_<W>x<H>_<N>frames.png` (`cow_01_brown_move_down_32x32_4frames.png`, `corn_16x32_8frames.png`, `default_01_16x16_9split.png`): the cell size and frame count are **in the name**. 36 colour variants of one cow (288 files), `move` for walk, `sleep`, `dead`, `fly`. The same art ships in **five engine layouts** under `engines/Godot/autotiles/2x2`, `3x3`, `engines/RPG_Maker_MV_MZ/autotiles/A2` (768 × 576), `RPG_Maker_VX_VXace`, `RPG_Maker_XP`, `Unity`, plus the raw 16 × 96 templates in `assets/autotiles`. A zero-content `In development` file in every folder, `__MACOSX/._` files, `.html` links. Crops with 7–29 growth frames, tools (hoe, shovel, water, sickle), weather overlays, 9-slice UI themes. |
| *CuteSCKR* (one zip of 724 MB: 78 packs, 1,071 PNG files; the licence is not in the archive) | top-down (the three older kinds, and the top-down kinds of Part F) | **A bundle of packs, and sheets with no words in their names.** The zip has one folder per pack, named by theme (`Abandoned Hospital Tileset`, `Medieval Fantasy Town Pixel Art Tileset Pack`, `Modern Gym Fitness Center Pixel Art Tileset Pack`, …; ampersands, hyphens, one misspelt `Monder Interiors`), and inside it 4 to 25 sheets called only `1.png`, `2.png`, … (537 of the files; the numbering has gaps: `1`–`6`, `8`). What a sheet holds can only be read from the picture and from the **folder's** words. 560 sheets are 768 × 768 (a 16 × 16 grid of 48 px tiles, RPG Maker MV's B–E sheet), 47 are 2048 × 2048 and 21 are 1024 × 1024, all tiles and props on one sheet with no characters: the object cutter is the tool. A few names are RPG Maker's own (`prison_MV_A4.png` 768 × 720, `Tile-A2-11.png`, `Tile-B-12.png`, `Tile-C-12.png`), which the A-sheet reader knows. Some packs put their sheets one folder down (`Alien Jungle Tileset/Alien jungle/`, `tileset-1/`, `ww1/`). One pack carries the output of a sprite-cutting tool beside its sheets: `_organized_sprites/sprites/<category>/sheet_01_<category>_001.png` (431 cut props in nine categories such as `baskets_crates_and_bins` and `tall_shelves_and_racks`), `_organized_sprites/previews/sheet_01_boxes.png` and `_contact.png`, and a `manifest/sprites.csv` and `sprites.json` with each prop's source sheet and rectangle (and an absolute path of the artist's own disk). Two `.jpg` files with a non-ASCII suffix (`B-10_副本.jpg`, *copy*). 675 KB per sheet on average: the pack is large by bytes, not by file count. |
What follows from it, by card: rotation sheets of 46 × 54 as well as square cells, `_mix`
terrains and the `bikes`, `nitro`, `smoke`, `barrier`, `tire` words (T16.02); numbered frames
without action words split at blank frames, a reader for binary `.aseprite` files, the
`WxH_Nframes` suffix, engine-layout duplicates, preview and guide files, number prefixes,
ampersands, emoji and typos in names (T16.21); a zip that is a bundle of packs, sheets named
by a number only whose content comes from their folder's words and from the picture, the
`MV_A4` / `Tile-A2` names, and the cut sprites and manifest another tool left in a pack
(T16.21), with the choice of which packs of a bundle to add as a card of its own (T16.22);
the farm kind of Part F has a real pack to be designed against.

## Ground rules for this milestone

* The M12–M15 ground rules apply: core logic stays out of the GUI, pages only edit
  `WizardState`, generated output is deterministic, `.tscn` / `.tres` / `project.godot` are
  never written by hand, every Godot API is verified in `docs/godot_api_verified.md` before
  use, recipe changes bump `RECIPE_VERSION`, new smoke steps are added to the lists the
  integration tests assert, the layout test stays green at the minimum window, and the
  post-release compatibility contract holds (`config_version` 1, `save_version` 1, nothing
  under `game/` rewritten, no generated script moved or renamed).
* **Additive only.** A new archetype lives in `archetypes/<key>/` in the runtime and
  `recipes/<key>/` in the builder, plus the shared `archetypes/arcade/` folder of Part A, which
  the install filter keeps out of the projects of the three older kinds. The older kinds'
  goldens, TileSets and sprite frames do not move; the corpus (T12.26) is unchanged on all four
  measures after every detection card.
* **Every kind plays from a pack that has nothing made for it.** What a pack lacks is drawn,
  as the side kit does (`side_kit.py`): a bullet, a laser, an explosion, a power-up capsule, a
  car in sixteen headings, a road, a grapple hook. A drawn stand-in is a note (`ASSET-031`),
  never an error, so the sample of each kind and a plain RPG pack both make a game.
* **Feature flags.** `features.SHMUP_AVAILABLE`, `RUN_AND_GUN_AVAILABLE`, `RACING_AVAILABLE`,
  off until the kind's gate row passes; an off kind's card is disabled with *coming in a later
  release* and its sample is not offered, as `METROIDVANIA_AVAILABLE` does.
* **New roles, usages, collision values, tags and sound slots** are added to
  `02_SCHEMAS.md` and the catalog schema first; the audit offers them for every kind (a role is
  a label, the kinds decide what they do with it); the older kinds ignore them.
* **New error codes** go into `03_ERROR_CODES.md` first, then `python tools/gen_error_codes.py`.
  Reserved: `ASSET-031` (a drawn stand-in), `ASSET-032` (a vehicle sprite without headings),
  `VAL-029` (a stage, wave or track that cannot be finished), `VAL-030` (a grapple stage with
  jumping off and no ceiling to swing from), `SMOKE-010`–`SMOKE-012` (one per kind's own
  sequence).
* **Samples.** One small CC0 sample pack per kind (`sample_pack_shmup`, `sample_pack_gun`,
  `sample_pack_race`, each under 200 KB), built by `tools/build_sample_pack.py` from drawn
  parts like the two existing ones, with goldens. *Try the sample* lists five samples.
* **Perf and CI.** Each kind has its own integration job (`arcade:<key>` marker) and its own
  perf ceiling in `tests/perf/test_perf.py` (the sample of the kind as that kind, under 120 s),
  following the metroidvania's split (T14.11).
* **Controls.** Every kind is playable on keyboard and gamepad from the start with the bindings
  of `config.default_input(archetype)`; the glyphs (T12.55) cover the new actions.

## Order of work

| Step | Tasks | Why this order |
|------|-------|----------------|
| 1 | T16.01, T16.02, T16.03, T16.21 | The arcade framework, detection, the drawn stand-ins and the adapter work the real packs need: everything else needs them |
| 2 | T16.04 – T16.07 | The shoot 'em up: the simplest kind, it proves the framework |
| 3 | T16.08 – T16.11 | The run and gun, on the platform actor; the grapple last |
| 4 | T16.12 – T16.15 | Racing: the one kind with a new actor and a new planner |
| 5 | T16.16, T16.17, T16.22 | The wizard (cards, roles, options, previews), the samples and the bundle's checklist |
| 6 | T16.18, T16.19, T16.20 | Smoke tests, documentation, the gate, then tag `v1.4.0` |

Each kind can be released alone behind its flag if the others are late.

## Index

Sizes are rough: **S** under a day, **M** 1–3 days, **L** 3–7 days, **XL** more than a week.

| Card | Title | Size | Depends on | Status |
|------|-------|:----:|------------|--------|
| T16.01 | The arcade framework | L | — | done as a framework with its tests; played from the title to the credits only once a kind can be generated (T16.04), see the notes |
| T16.02 | Detection for the three kinds | M | — | done, but for the grid editor's ring and the pack card's words (the wizard, T16.16); the notes have the deviations |
| T16.03 | Drawn stand-ins and new roles | M | T16.02 | done; the kinds are not in the config's enum until they can be built, and the notes have the other deviations |
| T16.04 | Shoot 'em up: ship, bullets, scrolling | M | T16.01, T16.03 | done; no auto-fire switch in the settings menu yet, and the stage has nothing to shoot at until T16.05 (the notes) |
| T16.05 | Shoot 'em up: waves, enemies, power-ups | M | T16.04 | done; an enemy without a picture is a drawn shape with no note, and the waves are a fixed set until the stage planner (the notes) |
| T16.06 | Shoot 'em up: stages and bosses, the wave plan | L | T16.05 | done; the options are in `starter_map`, an added stage is read from rpggen's own list, and the run to the credits is a smoke step, not a game played by hand (the notes) |
| T16.07 | Shoot 'em up: HUD, continue, high scores | S | T16.06 | open |
| T16.08 | Run and gun: the soldier on the platform actor | M | T16.01, T16.03 | open |
| T16.09 | Run and gun: weapons, enemies, spawners | M | T16.08 | open |
| T16.10 | Run and gun: stages and bosses, the stage plan | L | T16.09 | open |
| T16.11 | Run and gun: the grapple | M | T16.10 | open |
| T16.12 | Racing: the car and the camera | M | T16.01, T16.03 | open |
| T16.13 | Racing: the track plan and the track recipe | L | T16.12 | open |
| T16.14 | Racing: rivals, laps, checkpoints, pickups | M | T16.13 | open |
| T16.15 | Racing: championship, results and the HUD | S | T16.14 | open |
| T16.16 | Wizard: cards, roles, options and previews | L | T16.07, T16.11, T16.15 | open |
| T16.17 | Three sample packs and *Try the sample* | M | T16.16 | open |
| T16.18 | Smoke sequences and integration tests | M | T16.17 | open |
| T16.19 | Documentation, screenshots and changelogs | M | T16.18 | open |
| T16.20 | Gate (1.4.0) | M | T16.19 | open |
| T16.21 | What the real packs need: numbered frames, `.aseprite` sources, names with sizes, engine duplicates | M | — | open: the core of every point and the three synthetic packs are done; the rest of the wizard's side of it (variants as one card, the pack card's words), `.aseprite` pixels and the *Done when* on the real packs are not (the notes have the table) |
| T16.22 | A bundle of packs: choosing which to add | M | T16.21 | open |

---

# Part A — Shared foundations

## T16.01 — The arcade framework

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/archetypes/arcade/` (new: `stage.gd`,
`stage_sequence.gd`, `scroller.gd`, `spawner.gd`, `wave.gd`, `lives.gd`, `score.gd`,
`boss_base.gd`, `boss_phase.gd`, `stage_clear.gd`, `continue_screen.gd`, `high_scores.gd`,
`arcade_mode.gd`, `arcade_strings.gd`, `ui/arcade_hud.gd`, `ui/high_score_table.gd`),
`godot_templates/addons/rpg_runtime/core/save_system.gd` (a `meta` section),
`godot_templates/builder/recipes/arcade/` (new: `arcade_build.gd`, `hud_recipe.gd`,
`stage_recipes.gd`), `godot_templates/tests/unit/test_arcade_runtime.gd` (new),
`rpggen/core/staging.py` (the install filter), `docs/spec/02_SCHEMAS.md` (§ save meta)

The three kinds are arcade games: a run through stages with lives and a score, not an open
world with a party. What they share is written once.

**Spec**
* **Stages.** `StageSequence` holds the ordered stages of a run (`game/data/stages.json`,
  written by the kind's recipe from its plan); `Stage` is a scene with an entry, an exit
  condition (reach the end, clear every wave, finish the laps) and a boss slot. Clearing a
  stage shows `StageClear` (score tally, bonus for time and lives), then the next stage; the
  last one ends the game with the credits (T12.51) and the high-score entry.
* **Scrolling.** `Scroller` moves the camera at a set speed along one axis (up, right, or none)
  and **stops** at a spawner that asks it to (a wave that must be cleared, a boss), then goes
  on; the kinds set the axis. The parallax layers of T14.02 follow it.
* **Spawners and waves.** `Spawner` places an enemy scene at a trigger: a camera position
  (the stage's progress), a time, or the death of a previous wave. `Wave` is a list of
  spawns with a formation (`line`, `column`, `v`, `circle`, `sine`), a count and a gap. A
  stage's waves come from the plan (T16.06, T16.10): the runtime reads them, never invents
  them, so a run is the same for the same seed.
* **Lives and score.** `Lives` (a count, an extra life every N points, game over at zero),
  `Score` (points per kill and pickup, a multiplier that grows with kills without being hit
  and resets on a hit). Both are autoload-free nodes under `ArcadeMode`, which the kind's
  `*_mode.gd` extends, as `MetroidvaniaMode` does `CombatMode`.
* **Bosses.** `BossBase` has health, phases (`BossPhase`: a pattern of movement and attacks
  that changes at a health fraction), a telegraph before each attack, an intro (the scroller
  stops, the name appears) and a defeat (explosions, the stage's exit opens). The kinds give
  it its patterns.
* **Continue and high scores.** `ContinueScreen` after a game over (a countdown, *Continue*
  keeps the stage and resets the score multiplier, *Quit* goes to the title); `HighScores`
  keeps the ten best (name, score, stage) in the save system's new `meta` section, which is
  shared by the three slots and the autosave and loads in every older game as an empty
  table (`save_version` stays 1: the key is optional).
* **The HUD.** `ArcadeHUD`: lives, score, the multiplier, the stage name, a boss health bar
  when a boss is on; the kinds add their rows (bombs, weapon, lap).
* **Saving.** An arcade game saves between stages only (stage number, lives, score, the
  weapon) into the slot system that exists; *Continue game* on the title resumes at the start
  of the stage.
* **Options the arcade kinds switch off by default**, through the option dependencies of
  T13.06: dialogue, inventory, equipment, shops, quests, party, interiors, the second map,
  the minimap, lighting; they stay available (a run and gun may want a shop between stages).
* **Install filter.** `archetypes/arcade/` and `recipes/arcade/` are installed for the three
  new kinds only; the older kinds' projects do not change (their ledgers see nothing new).

**Tests**
* GDScript: a sequence of two stages with one wave each is cleared by killing the spawns;
  the scroller stops at a blocking wave and resumes; lives reach zero → the continue screen
  → *Continue* resumes the stage; the high-score table keeps ten sorted entries and
  round-trips through the save meta; a boss changes phase at the fraction and dies.
* Python: the install filter leaves the arcade folder out of a turn-based, an ARPG and a
  metroidvania project (byte-identical goldens).

**Done when**
* A test stage with drawn placeholders can be played from the title to the credits.

## T16.02 — Detection for the three kinds

**Depends on:** nothing
**Files:** `rpggen/core/classifier.py`, `rpggen/core/adapters/naming.py`,
`rpggen/core/pack_sniff.py`, `rpggen/core/analyzer/frames.py` (heading rings),
`tests/unit/test_classifier.py`, `tests/unit/classifier_cases.json`,
`tools/make_synthetic_packs.py` (three packs: `shooter`, `gunner`, `racer`)

**Spec**
* **Tags from folder and file words:** `ship` (ship, spaceship, fighter, jet, plane, starship),
  `bullet` (bullet, shot, laser, beam, missile, rocket, plasma), `explosion` (explosion,
  blast, boom, burst), `asteroid` (asteroid, meteor, rock), `powerup` (powerup, power_up,
  capsule, upgrade, weapon_pickup), `soldier` (soldier, commando, trooper, marine, gunner),
  `gun` (gun, rifle, machinegun, spread, flame, laser_gun), `grenade`, `turret` (turret,
  cannon, emplacement), `grapple` (grapple, hook, claw, arm), `car` (car, kart, buggy,
  truck, racer, vehicle), `road` (road, track, asphalt, tarmac, dirt_track), `finish`
  (finish, start_line, checkpoint), `tyre` (tyre, tire, barrier, cone), `oil`, `boost`
  (boost, nitro, speed_up), `vfx` (vfx, smoke, nitro, dust: effects, never a tile), `bike`
  (bike, bikes, scooter, chopper, motorcycle: a vehicle like a car), `mix` (a terrain sheet
  that joins two surfaces, `grass_dirt_mix`: a transition terrain). Tags change nothing for
  the older kinds.
* **Headings.** `analyzer.frames.heading_ring(sheet)`: a sheet whose frames are N views of one
  object turned step by step (N in 8, 12, 16, 24, 32; the frames' silhouettes rotate by
  360/N with an error under a threshold) is a **rotation sheet**; the cell need not be
  square (*Wheels in Pixels* uses 46 × 54 and 32 × 32, one row of 16); the catalog records
  `headings: N` and the order's start (up or right, clockwise or not). A sprite with 4 or 8
  directional walks (T12.50) is not a ring.
* **Pack view** (`classifier.pack_view`) gains `shmup` (ship, bullet, asteroid words; a
  vertical background taller than wide), `racing` (car, road, tyre words; a rotation sheet)
  and keeps `side` and `top`. The pack card says *Looks like a shooter pack* and the
  Archetype page's hint points at the kind.
* **Usage** gains `rotation_sheet` beside `sprite_sheet`; the grid editor shows the headings
  as a ring.
* Synthetic packs: `shooter` (a 24-px ship with a 3-frame bank, five enemy ships, a bullet,
  an explosion strip, two vertical background layers, a boss, three capsules), `gunner` (a
  soldier with run, jump, crouch, aim-up, aim-diagonal and shoot strips, three enemies, a
  turret, a boss, a 16-px side tile sheet, two parallax layers, four weapon pickups, a
  hook), `racer` (a car in 16 headings, three rival cars, a 16-px road sheet with straights,
  curves, a start line and grass, tyres, cones, oil, a boost arrow, four pickups).

**Tests**
* The classifier cases for every tag and the three pack views; `heading_ring` over the racer
  car (16), a 4-direction walk sheet (none) and a 32-heading ring; the three goldens; no
  other golden moves; the corpus is unchanged on all four measures.

**Done when**
* The three synthetic packs are catalogued with the right roles and usages without an edit.

## T16.03 — Drawn stand-ins and new roles

**Depends on:** T16.02
**Files:** `rpggen/core/arcade_kit.py` (new, beside `side_kit.py`), `rpggen/core/requirements.py`,
`rpggen/core/mapping.py`, `rpggen/core/sound_slots.py`, `rpggen/schema/catalog.schema.json`,
`docs/spec/02_SCHEMAS.md`, `docs/spec/03_ERROR_CODES.md`, `tests/unit/test_arcade_kit.py` (new),
`tests/unit/test_requirements.py`

**Spec**
* **Roles** (labels in the audit and rows on the Mapping page, in every kind):
  `PROJECTILE` (bullets, lasers, missiles), `VEHICLE` (the player's car), `EXPLOSION`,
  `POWERUP` (what the player picks up to get stronger; `ITEM` stays for chests and coins),
  `HAZARD` (asteroids, tyres, oil, spikes). `BOSS`, `BACKGROUND`, `ENEMY`, `UI`, `PLAYER`
  are reused. Required per kind: `shmup` → `PLAYER` (the ship); `run_and_gun` → `PLAYER`,
  `GROUND`; `racing` → `VEHICLE`, `GROUND` (the road tiles). Optional and the
  `REQUIRED_BY_ARCHETYPE` wording per kind, e.g. racing's `ENEMY` is *the rival cars* and
  `DECORATION` is *trackside scenery*.
* **Drawn stand-ins** (`arcade_kit.py`, deterministic, in the pack's tile size, all `ASSET-031`
  notes): a bullet, a laser, a missile, an explosion strip (6 frames), a capsule, a ship
  (for a pack with no `PLAYER` in a shmup: the game still plays), a car in 16 headings, a road
  sheet (straight, curve, start line, grass, barrier), a hook and a chain segment, a weapon
  icon per weapon kind. A pack's own asset always wins.
* **A vehicle without headings** (`ASSET-032`, a note): one picture is rotated by the runtime
  (`Sprite2D.rotation`, nearest-neighbour) and the card says a 16-heading sheet looks better.
* **Sound slots** per kind (`sound_slots.py`, like the metroidvania's four): shmup → `sfx_shoot`,
  `sfx_explosion`, `sfx_powerup`, `sfx_bomb`, `music_stage`, `music_boss`; run and gun →
  `sfx_shoot`, `sfx_explosion`, `sfx_grenade`, `sfx_weapon_pickup`, `sfx_grapple`, `music_stage`,
  `music_boss`; racing → `sfx_engine` (looped, pitch follows speed), `sfx_skid`, `sfx_bump`,
  `sfx_pickup`, `sfx_lap`, `sfx_countdown`, `music_race`, `music_results`. Filled by file
  name as today; silent when empty.

**Tests**
* Every stand-in renders at 16 and 32 px with the expected size and frame count and is
  byte-identical across two runs; the requirement check of each kind with and without its
  required roles (ASSET-010 wording names the kind's use); the slots' defaults from the
  synthetic packs.

**Done when**
* A plain RPG pack chosen as a shoot 'em up passes the requirement check with notes only.

## T16.21 — What the real packs need: numbered frames, `.aseprite` sources, names with sizes, engine duplicates

**Depends on:** nothing
**Files:** `rpggen/core/adapters/sequences.py`, `rpggen/core/adapters/aseprite.py` (a binary
reader), `rpggen/core/adapters/naming.py`, `rpggen/core/pack_sniff.py`, `rpggen/core/inventory.py`
(ignored files), `rpggen/core/catalog.py` (engine-layout duplicates), `docs/spec/03_ERROR_CODES.md`
(`ADAPT-005`, `ADAPT-006`, `ADAPT-007`), `tests/unit/test_sequences.py`, `tests/unit/test_aseprite.py`,
`tests/unit/test_naming.py`, `tools/make_synthetic_packs.py` (a `frames_export`, a
`multi_engine` and a `bundle` pack), `rpggen/core/adapters/rpgmaker.py`

Every finding here comes from the six packs listed above; each benefits every kind, not only
the three new ones, so the card runs first and the corpus must be unchanged after it.

**Spec**
* **Numbered frames without an action word.** A folder whose files are `<STEM><n>.png` with one
  stem, consecutive numbers and one image size (`CHARACTER1.png` … `CHARACTER168.png`) is a
  frame export even without walk, attack or idle in the name. The frames are split into
  animations at **blank frames** (fully transparent images, which this exporter writes as
  separators) and, when there are none, at gaps in the numbering; the animations are named
  `anim_1` … `anim_n` and the asset is *needs review* with `ADAPT-005` (*n animations found,
  not named: name them in Animations…*). The Animations dialog lets a name be typed and offers
  the action words; a `.aseprite` source beside the frames names them instead (next point).
* **Binary `.aseprite` files.** The Aseprite adapter reads the `.aseprite` format itself
  (header, frames, cel chunks with zlib, the tags chunk `0x2018`, the palette; the format is
  public and stable), not only the JSON export: the tags give the animation names and ranges,
  the frames give the pictures. A `.aseprite` next to its exported frames or strip is the
  **source of truth** for names and ranges and the PNGs are used for the pixels (they are
  what the artist shipped); a `.aseprite` with no export beside it is rendered to a strip in
  the work folder (as GIFs are, T12.50). A file the reader cannot parse is `ADAPT-006`, a
  note, and the PNGs are used alone.
* **Sizes and counts in the name.** `naming.py` parses `_<W>x<H>` (the cell size),
  `_<N>frames` (the frame count), `_<N>split` (a 9-slice UI piece) and `_<N>dir` /
  `_<N>directions` and feeds them to the grid detection as facts with a higher confidence than
  a measured guess; `move` becomes a synonym of `walk`, `sleep`, `dead` and `fly` are action
  words, `growth` marks a crop's growth strip (a tag, for M17).
* **Engine layouts of the same art.** A pack whose folders are `engines/<Engine>/…` (Godot,
  RPG_Maker_MV_MZ, RPG_Maker_VX_VXace, RPG_Maker_XP, Unity, GameMaker, Construct) ships one
  picture several times. `pack_sniff` recognises the layout; the catalog keeps the **Godot**
  folder's files first, then an RPG Maker folder's (the A2 reader knows them), and marks the
  others `duplicate_of` and *unused*, with the pack card saying *art for 5 engines: Godot's
  is used*. The raw templates in `assets/autotiles` (16 × 96) are read as 6-tile templates
  when the 47-tile Godot sheet exists, else used.
* **Files that are not assets.** The inventory skips `__MACOSX/`, `._*`, `Thumbs.db`,
  `.DS_Store`, `*.html`, `*.url`, zero-byte and text files named `In development` or
  `readme`, and a `PREVIEW`/`previews`/`screenshots` folder; a picture named `preview`,
  `test`, `grid`, `guide`, `slots`, `template`, `mockup` or `showcase` at the pack root is
  *unused* by default with the reason on its card (not excluded: one click brings it back).
* **Names as artists write them.** The tokeniser strips a leading `<n>.` or `<n>_`, splits on
  `&`, `,`, `+`, `(`, `)` and emoji, folds a space before the extension (`BACKGROUND (1) .png`)
  and reads `(1)` as a number; common typos are folded by an edit-distance of one against the
  word lists for words of six letters or more (`BACKGROUD`, `Enviroment`), with the *Why*
  line saying so.
* **A bundle of packs in one archive.** An archive (or folder) whose top level is one folder
  holding many folders that each look like a pack (ten or more, each with images and no
  images beside them; *CuteSCKR* has 78) is a **bundle**. `pack_sniff` reports it with its
  pack folders (name, image count, bytes) from the archive's listing alone: no file is
  unpacked. A folder of a bundle added on its own is a pack like any other, with the folder's
  name. Choosing among the folders in the wizard and on the command line is T16.22.
* **Sheets named by a number only.** A sheet whose name has no word (`1.png`, `12.png`) takes
  its words from its **folders**, nearest first (`Medieval Fantasy Town Pixel Art Tileset
  Pack/3.png` → medieval, fantasy, town, tileset), with the words every pack of the bundle
  shares (`pixel`, `art`, `tileset`, `pack`) counted as usage hints, not as tags; the *Why*
  line says the name came from the folder. Such a sheet is a tile sheet by its folder and its
  grid, and what stands on it (ground, walls, props) is decided by the picture analysis as
  today; a sheet that mixes tiles and props is offered to the object cutter. Gaps in the
  numbering are not an error and not a sequence break (these are sheets, not frames: a set of
  numbered files of 256 px and more with different content is never a frame export).
* **RPG Maker names inside other packs.** `<name>_MV_A4.png`, `Tile-A2-11.png`, `Tile-B-12.png`
  are read by the RPG Maker adapter's sheet kinds (A1–A5, B–E) wherever they lie, and a
  768 × 768 sheet with a 48 px grid is offered as a B–E sheet (16 × 16 tiles) when nothing
  else names its grid.
* **What another cutting tool left behind.** A folder `_organized_sprites` (or one that holds a
  `manifest/sprites.csv` or `sprites.json` with `source_sheet, x, y, width, height` columns) is
  the output of a sprite cutter. Its manifest is read as **object rectangles on the source
  sheets** (`sheet_01` → the pack's first sheet; the categories become tags), so the props
  appear as cut objects of the sheets they came from; the cut PNG copies and the `previews`
  folder are *unused* with the reason on their cards (the pixels are on the sheets already),
  and an absolute path in the manifest is ignored. A manifest that does not match its sheets
  (a rectangle outside the picture) is `ADAPT-007`, a note, and the cut PNGs are used as sprites.
* **Other pictures.** `.jpg` files are catalogued as backgrounds or previews, never as tiles
  (no transparency); a name with a non-ASCII suffix (`_副本`, *copy*) is a copy of a file and
  is *unused* when its sibling exists.
* **Colour variants in the pack.** Files whose names differ only by a colour word
  (`Classic_Bug_red.png`, `cow_01_brown_…`) or a trailing colour folder are grouped as one
  asset with **palette variants** through the variant pipeline (T13.18): one card in the audit
  with a variant badge and a *Variants (8)* row, each variant selectable on the Mapping page
  and in the editor dock. The colour words: black, white, red, green, blue, yellow, pink,
  purple, orange, brown, grey, gray, cyan, lime, beige, and the `<colour>_<colour>` pairs the
  ranch pack uses.

**Tests**
* The `frames_export` synthetic pack (numbered frames with blank separators and a
  `.aseprite` beside them) gives named animations; without the `.aseprite`, `anim_1..n` and
  `ADAPT-005`; the binary reader over a fixture made by Aseprite 1.3 (tags, a looped tag, a
  palette) and over a truncated file (`ADAPT-006`).
* The naming cases for every suffix and synonym; a `(1) .png` name; a leading `10. `; an
  ampersand; a typo within distance one and one beyond it (not folded).
* The `multi_engine` pack catalogues the Godot files once and marks the four other copies.
* The ignore list; a root `test.png` is *unused* with its reason and can be restored.
* A `bundle` synthetic archive (twelve small pack folders under one top folder, sheets named
  `1.png` … with a gap, one pack with an `_organized_sprites` folder and its manifest): the
  sniff reports a bundle and its twelve folders from the listing alone (nothing is unpacked:
  the test counts the reads), a folder added on its own is a pack, a numbered
  sheet has its folder's words and its *Why* line, the manifest's rectangles are cut objects
  on their sheets and the copies are *unused*; a manifest with a rectangle outside its sheet
  gives `ADAPT-007`. Five numbered 768 × 768 sheets are five tile sheets, not one animation.
* The colour-variant grouping over the racer's eight cars and the ranch's 36 cows; the
  corpus (T12.26) is unchanged on all four measures.

**Done when**
* The six real packs catalogue with these results: the racing pack's 32 vehicles as 32
  assets with their colour variants and 16 headings; each side-scroller pack as ten tile
  sheets with the right tags; the village pack's character as one sprite with named
  animations; the ranch pack with one copy of each picture and *needs credit* on its card;
  *CuteSCKR* reported as a bundle of 78 packs, and three of its folders added on their own
  (a town, an interior and the supermarket with its manifest) catalogued as tile sheets with
  their folders' words and, for the supermarket, 431 cut objects.

## T16.22 — A bundle of packs: choosing which to add

**Depends on:** T16.21 (the sniff reports the bundle and its folders)
**Files:** `rpggen/gui/pages/project_page.py`, `rpggen/gui/dialogs/bundle_dialog.py`,
`rpggen/core/pack_sniff.py` (unpacking the chosen folders only), `rpggen/cli.py`
(`--pack-folder`), `rpggen/schema/cli.schema.json`, `tests/gui/test_bundle_dialog.py`,
`tests/unit/test_cli.py`

T16.21 recognises a bundle; this card lets the user take part of one. Without it a bundle
could only be added whole (1,071 sheets as one pack, for *CuteSCKR*) or unpacked by hand.

**Spec**
* **The checklist.** Adding a bundle on the Project page opens *Choose packs* instead of
  adding it: one row per pack folder with its name, image count and size, a search field,
  *Select all* and *Select none*, and the total of what is ticked (packs, images, MB) beside
  the *Add* button. Every row is ticked for a bundle of 20 folders or fewer, none above that.
  *Add* with nothing ticked is disabled; *Cancel* adds nothing.
* **Each ticked folder is a pack of its own**, named by its folder, so the audit's pack
  filter, the licence card and the profile work per pack. Only the ticked folders are
  unpacked, with the progress and the *Cancel* of any pack import.
* **Coming back.** The Project page shows the bundle's packs grouped under the archive's
  name with *Choose packs…* on the group, which reopens the checklist with the present
  choice ticked: ticking adds a pack, clearing one removes it after the confirmation any
  pack removal asks for. The choice is stored in the project's configuration as the archive
  and its folders, so a regeneration finds the same packs.
* **One licence for the bundle.** A licence file at the bundle's top level applies to every
  pack taken from it; with none (*CuteSCKR* has none in its archive) each pack's licence card
  says *not found in the bundle* once, on the group, not 78 times.
* **The command line.** `--pack <archive> --pack-folder <name>` (repeatable) takes those
  folders; a bundle given without `--pack-folder` stops with the list of its folders and the
  option's name, and a folder that is not in the bundle is an error naming the nearest match.
  The configuration file's pack entry takes the same list as `folders`.
* The dialog follows the dialog rules of M15 (size, keyboard, the search field's focus) and
  its strings are translatable.

**Tests**
* The `bundle` synthetic archive of T16.21 opens the checklist with twelve rows, all ticked;
  one of 25 folders opens with none ticked. Search narrows the rows and keeps the ticks of
  hidden rows; the total follows the ticks; *Add* is disabled with none.
* Three ticked folders become three packs with their folders' names, and only their files
  are unpacked. Reopening shows the three ticked; clearing one removes that pack after the
  confirmation; the choice survives save and load of the project.
* The licence note appears once on the group.
* The CLI: the folders given, none given (the message lists them), an unknown folder; the
  schema accepts `folders` and rejects it on a pack that is not a bundle.
* The dialog at the smallest window size and by keyboard alone (the layout-fit and
  accessibility suites cover it).

**Done when**
* *CuteSCKR* is offered as 78 rows without a file being unpacked, and a town, an interior
  and the supermarket are added from it in one step and catalogue as T16.21 says.

---

# Part B — Shoot 'em up

## T16.04 — Ship, bullets, scrolling

**Depends on:** T16.01, T16.03
**Files:** `godot_templates/addons/rpg_runtime/archetypes/shmup/` (new: `shmup_mode.gd`,
`ship.gd`, `ship_input.gd`, `weapon.gd`, `bullet_pool.gd`, `enemy_bullet.gd`, `bomb.gd`,
`shmup_strings.gd`, `ui/`), `godot_templates/builder/recipes/shmup/` (new: `shmup_build.gd`,
`ship_recipe.gd`, `stage_recipe.gd`), `rpggen/core/config.py` (`default_input("shmup")`,
`starter_map_defaults("shmup")`), `godot_templates/tests/unit/test_shmup.gd` (new)

**Spec**
* **Orientation** is a config option `shmup.orientation: vertical | horizontal`. Vertical: the
  ship at the bottom, the camera scrolls up, the play area is the viewport's width (a 4:3 area
  centred with side panels for the HUD when the window is wider, as arcade boards do).
  Horizontal: the ship at the left, the camera scrolls right. One `Ship` script; the axis
  comes from the mode.
* **The ship** (`CharacterBody2D`): eight-way movement at a speed, a `focus` button that
  halves it (precise dodging), a one-pixel hurtbox at the centre (the picture is bigger than
  the hit, as the genre does), a bank animation when the sheet has one (left, centre, right
  frames; T12.50's directions give it), three seconds of blinking invulnerability after a
  hit, and a death explosion.
* **Weapons.** `Weapon` has a kind (`straight`, `spread`, `laser`, `homing`), a level 1–3
  (more bullets, wider spread, a thicker laser), a rate and a bullet scene; `shoot` fires
  while held (auto-fire is the default, a setting turns it off). Bullets come from a pool
  (`BulletPool`, 400 player and 1,000 enemy bullets pre-made) and leave the screen to return
  to it. **Bombs**: a count, a screen-clearing blast that erases enemy bullets and damages
  everything, with `sfx_bomb`.
* **Enemy bullets** are the pool's too, with a speed, an angle and an optional aim at the
  ship; patterns (`aimed`, `ring`, `fan`, `spiral`) are small functions on `EnemyBullet`
  that T16.05's enemies and T16.06's bosses call.
* **The recipe** writes the ship scene from the `PLAYER` sprite frames (or the drawn ship),
  the bullet scenes from `PROJECTILE` (or drawn), the explosion from `EXPLOSION` (or drawn),
  and a first stage scene with the background layers of `BACKGROUND` in a `ParallaxBackground`
  that loops along the scroll axis.
* `default_input("shmup")`: move (arrows / WASD / left stick), `shoot` (Z / J / A), `bomb`
  (X / K / B), `focus` (Shift / LT), pause.

**Tests**
* GDScript: the ship moves and clamps to the play area in both orientations; a hit takes a
  life and starts invulnerability; a bomb clears the enemy bullets on screen; the pool
  recycles; the weapon's bullet count per level.
* Python: the recipe writes the scenes for the `shooter` pack and for the top-down sample
  (drawn stand-ins, `ASSET-031` notes).

**Done when**
* The ship flies, shoots and dies over a scrolling background in both orientations.

## T16.05 — Waves, enemies, power-ups

**Depends on:** T16.04
**Files:** `archetypes/shmup/enemies/` (`enemy_ship.gd`, `popcorn.gd`, `turret.gd`,
`asteroid.gd`, `carrier.gd`), `archetypes/shmup/powerup.gd`, `recipes/shmup/enemy_recipes.gd`

**Spec**
* Four enemy behaviours over `EnemyShip` (health, points, a death explosion, a drop chance):
  `popcorn` (flies a path: straight, sine, swoop, and shoots nothing or one aimed shot),
  `turret` (sits on the background, fires a fan at the ship), `asteroid` (drifts, blocks
  bullets, splits once), `carrier` (slow, tough, releases popcorn). The `ENEMY` assets are
  shared out over the behaviours by size (small → popcorn, big → carrier) and by tag.
* **Formations** of `Wave` (T16.01) move as one: a line that sweeps, a V that dives, a circle
  that closes; a formation cleared whole gives a bonus.
* **Power-ups** (`POWERUP` or drawn capsules): weapon level up, weapon kind change, a bomb, a
  life, a shield that takes one hit, points. They drift towards the ship's side of the screen
  and are picked up by touch; a carrier and every fifth popcorn formation drop one.

**Tests**
* GDScript: each behaviour's movement and shooting over a fixed time; a formation bonus; a
  power-up raises the level to 3 and no further; the shield takes one hit.

**Done when**
* Three waves of mixed enemies can be fought with the drawn stand-ins and the `shooter` pack.

## T16.06 — Stages and bosses, the wave plan

**Depends on:** T16.05
**Files:** `rpggen/core/wave_plan.py` (new, pure Python), `rpggen/core/options.py`,
`rpggen/core/world_plan.py` (a `stages` section of the project's plan file),
`archetypes/shmup/boss.gd` (over `BossBase`), `recipes/shmup/stage_recipe.gd`,
`tests/unit/test_wave_plan.py` (new)

**Spec**
* `wave_plan.plan(options, seed, catalog_facts) -> StagePlan`: for `stages` (default 3) and a
  `length` per stage (short, medium, long), a list of waves with their trigger position,
  formation, enemy behaviour, count and bullet pattern, a difficulty that rises within the
  stage and from stage to stage (more bullets, faster, tougher), a mid-stage carrier, and a
  boss with its phases (two to four patterns from `ring`, `fan`, `spiral`, `aimed bursts`,
  `sweep`). The plan is deterministic from the seed and stored in the project
  (`rpggen/world_plan.json`, `stages`), never planned again on regeneration (the rule of
  T14.06); *Added stages* grows it.
* **Finishability** (`VAL-029`): a plan is checked by a pure-Python budget: the bullets on
  screen at the hardest moment stay under a ceiling and every wave is reachable before the
  stage ends; a plan that fails is re-rolled with the next seed and the report says so.
* The boss: a `BOSS` asset (or the biggest `ENEMY`, or a drawn one) with health scaled to the
  stage, an intro, phases that change the pattern, a telegraph and a defeat sequence; the
  stage ends on its death.
* Options (`shmup` section, Options page in T16.16): orientation, stages (1–8), length,
  lives, bombs, auto-fire, difficulty (easy, normal, hard: bullet speed and count), and
  *Added stages*.

**Tests**
* The plan is the same for the same seed and differs by one stage for *Added stages*; the
  budget check rejects a hand-made impossible plan; difficulty rises monotonically; the
  recipe writes one scene per stage and the boss scene; the JSON fits the schema.

**Done when**
* A three-stage run with three bosses can be played from the title to the credits.

## T16.07 — HUD, continue, high scores

**Depends on:** T16.06
**Files:** `archetypes/shmup/ui/shmup_hud.gd`, `recipes/shmup/hud_recipe.gd`,
`godot_templates/project_files/README.shmup.md` (new)

**Spec**
* The arcade HUD plus the weapon kind and level, the bomb count and, in vertical mode, the
  side panels (score and lives on the right, the high score on the left). The title screen
  gets *High scores*. The generated README explains the genre's folders (`game/data/stages.json`,
  the enemy and boss scenes) and how to add a wave by editing the plan.

**Tests**
* The HUD shows the values from `Lives`, `Score` and `Weapon`; the README is written.

**Done when**
* The shoot 'em up is a whole game behind `SHMUP_AVAILABLE`.

---

# Part C — Run and gun

## T16.08 — The soldier on the platform actor

**Depends on:** T16.01, T16.03
**Files:** `archetypes/run_and_gun/` (new: `run_and_gun_mode.gd`, `soldier.gd` (over
`PlatformActor`, T14.03), `aim.gd`, `gun.gd`, `grenade.gd`, `run_and_gun_strings.gd`, `ui/`),
`recipes/run_and_gun/` (new: `run_and_gun_build.gd`, `soldier_recipe.gd`), `rpggen/core/config.py`,
`godot_templates/tests/unit/test_run_and_gun.gd` (new)

**Spec**
* `Soldier` extends the metroidvania's `PlatformActor` (run, jump with variable height,
  coyote time, one-way platforms, ladders) and adds **eight-way aiming**: the stick or the
  arrows set the aim (up, diagonals, forward, down while in the air), `shoot` fires the
  current `Gun` along it; `crouch` on down lowers the hurtbox and aims forward; a prone
  shot while crouched. The sheets' `aim_up`, `aim_diagonal`, `shoot`, `crouch` animations are
  used when present (T12.50's action words gain them); a sheet without them uses `idle` and
  `run` and the gun's muzzle flash says where the shot goes.
* **Lives, not health**: one hit is a death (the genre), with a respawn drop from the top of
  the screen and invulnerability; an option `health: 1–5` makes it forgiving.
* **The grenade**: an arc, a blast radius, a count refilled by pickups.
* `default_input("run_and_gun")`: move, jump (Space / A), shoot (J / X), grenade (K / Y),
  aim lock (Shift / LT: aim without moving), pause. The metroidvania's bindings are the
  starting point.
* The recipe writes the soldier scene from `PLAYER` (or the side kit's drawn hero), the
  bullets from `PROJECTILE` (or drawn), the explosion, and the first stage with the parallax
  layers and a side camera (`SideCamera`, T14.04) in **auto-scroll with a leash**: the camera
  follows the soldier rightwards and never back (the left edge kills: the genre's rule, an
  option turns it off).

**Tests**
* GDScript: eight aims give eight bullet angles; crouch lowers the hurtbox; a hit with one
  health is a death and a respawn; the camera never moves left; a grenade's blast hits what
  is in its radius.

**Done when**
* The soldier runs, jumps, aims and shoots through a flat test stage.

## T16.09 — Weapons, enemies, spawners

**Depends on:** T16.08
**Files:** `archetypes/run_and_gun/weapons/` (`machine_gun.gd`, `spread.gd`, `laser.gd`,
`flame.gd`), `archetypes/run_and_gun/enemies/` (`runner.gd`, `sniper.gd`, `turret.gd`,
`jumper.gd`, `wall_cannon.gd`), `archetypes/run_and_gun/weapon_pickup.gd`,
`recipes/run_and_gun/enemy_recipes.gd`

**Spec**
* Four guns over `Gun` (rate, bullets per shot, spread, range, a muzzle flash): machine gun
  (default), spread (five bullets in a fan), laser (a beam that pierces), flame (short,
  continuous). A weapon pickup (`POWERUP` or a drawn icon) flies in on a carrier that
  crosses the screen; a death loses the weapon (an option keeps it).
* Enemies reuse the metroidvania's `enemies/` where they fit (the patroller, the flyer, the
  shooter of T14.07) and add: `runner` (charges and jumps at the soldier), `sniper` (stands,
  aims, fires one shot with a telegraph), `turret` (fixed, fans), `jumper` (hops between
  platforms), `wall_cannon` (part of the scenery, opens to fire). `ENEMY` assets are shared
  out by tag and size.
* **Spawners** (T16.01) in a side-scrolling stage trigger on camera progress: a group of
  runners from the right edge, a sniper on a ledge, a trap of turrets that stops the
  scroller until destroyed.

**Tests**
* GDScript: each gun's bullets per shot and reach; the pickup swaps the gun; each enemy's
  behaviour over a fixed time; a blocking spawner stops and releases the camera.

**Done when**
* A stage with mixed enemies and all four guns plays with the `gunner` pack and the drawn
  stand-ins.

## T16.10 — Stages and bosses, the stage plan

**Depends on:** T16.09
**Files:** `rpggen/core/stage_plan.py` (new, pure Python), `rpggen/core/room_plan.py` (the
tile alphabet and the chunk helpers reused), `rpggen/core/world_plan.py` (a `stages` section),
`recipes/run_and_gun/stage_recipe.gd`, `archetypes/run_and_gun/boss.gd`,
`tests/unit/test_stage_plan.py` (new)

**Spec**
* `stage_plan.plan(options, seed, facts)`: a stage is a row of **chunks** (each a grid of
  `room_size` height and a chunk width, in the room-plan alphabet: ground, gaps, platforms,
  ladders, hazards, breakable blocks) joined so that the floor is continuous or bridged by a
  jumpable gap (the platform actor's jump arc from `platform_math`, already shared), with
  spawner placements per chunk from a difficulty curve, a weapon carrier every N chunks, and
  a boss arena at the end (a flat chunk with the boss, the scroller stops). `stages` (default
  3) and `length` (chunks per stage) come from the options; the plan is stored and reused
  (the T14.06 rule); *Added stages* grows it.
* **Finishability** (`VAL-029`): every chunk edge is reachable from the previous one by the
  actor's jump (and by the grapple in T16.11), checked in pure Python with the same
  arithmetic the runtime uses.
* The boss (over `BossBase`): a wall boss (the genre's gate with cannons), a walker and a
  helicopter-style flyer, chosen per stage; `BOSS` art or the biggest `ENEMY` or drawn.
* Options (`run_and_gun` section): stages, length, lives, health, keep weapon on death,
  the left edge kills, difficulty, *Added stages*.

**Tests**
* The plan is deterministic; the reachability check rejects a chunk pair with a gap wider
  than the jump; difficulty rises; the recipe writes one scene per stage; the JSON fits the
  schema.

**Done when**
* A three-stage run with three bosses can be played from the title to the credits.

## T16.11 — The grapple

**Depends on:** T16.10
**Files:** `archetypes/run_and_gun/grapple.gd`, `archetypes/run_and_gun/soldier.gd`,
`rpggen/core/stage_plan.py` (grapple reachability), `rpggen/core/config.py`,
`godot_templates/tests/unit/test_grapple.gd` (new)

Bionic Commando's hero cannot jump: the arm does the climbing.

**Spec**
* `Grapple`: fired along the aim (up, the two upper diagonals, forward), a hook that flies
  until it hits a `grapple` surface (any solid tile by default; an option limits it to tiles
  tagged `grapple`) or its reach ends; on a hit the soldier **swings** on a fixed-length
  rope (a pendulum in `platform_math`, verified against the same arithmetic in Python),
  releases with momentum, and **hoists** when the hook is straight above (climbs to the
  ledge). The rope is drawn from the pack's `grapple` asset (a hook and a chain segment) or
  the drawn one. `sfx_grapple` on fire and hit.
* Options: `grapple: off | on`, `jump: on | off`; *jump off* needs *grapple on* (the T13.06
  dependency), and the preset **Bionic** sets both. With jumping off, the stage plan uses
  grapple reachability only: every gap has a ceiling or an overhang in reach, else `VAL-030`
  and a re-roll; the runner enemy's jump is kept (enemies jump; the soldier does not).
* The soldier's `grapple` animation when the sheet has one, else `aim_up`.

**Tests**
* GDScript: the hook attaches to a ceiling, the swing's period matches the Python pendulum
  within 1 %, release carries the velocity, a hoist lands on the ledge; with jumping off the
  jump button does nothing.
* Python: a plan with jumping off has a swing point over every gap; `VAL-030` for a stage
  with none.

**Done when**
* The `gunner` sample plays as Bionic (no jump) from start to the last boss.

---

# Part D — Racing

## T16.12 — The car and the camera

**Depends on:** T16.01, T16.03
**Files:** `archetypes/racing/` (new: `racing_mode.gd`, `car.gd`, `car_physics.gd`,
`car_input.gd`, `heading_sprite.gd`, `race_camera.gd`, `racing_strings.gd`, `ui/`),
`recipes/racing/` (new: `racing_build.gd`, `car_recipe.gd`), `rpggen/core/config.py`,
`godot_templates/tests/unit/test_racing.gd` (new)

**Spec**
* `Car` (`CharacterBody2D`) with an arcade model in `car_physics.gd` (pure functions, mirrored
  in `rpggen/core/car_math.py` for the planner and the tests): acceleration, top speed, brake,
  a turn rate that falls with speed, grip per surface (road, dirt, grass, oil: the tile's
  `surface` from the terrain facts, as footsteps use it), a drift when turning hard at speed,
  a bump off barriers and other cars that costs speed, and a **boost** (a pickup, or the
  track's boost arrows). Top-down, orthographic; the view is RC Pro-Am's from above, not its
  isometric angle (isometric tiles are an M17 card).
* `HeadingSprite`: shows the frame of the `VEHICLE` rotation sheet nearest the car's heading
  (16 headings → 22.5° steps; T16.02's `headings`), or rotates one frame (`ASSET-032`).
* `RaceCamera`: follows the car, looks ahead along its velocity, zooms out slightly with
  speed; an option fixes the camera on the track (the whole track on screen for small ones).
* `default_input("racing")`: accelerate (Up / A), brake and reverse (Down / B), steer (Left /
  Right / stick), boost (Shift / X), pause. An option `steering: relative | absolute`
  (absolute: the stick's direction is the car's heading, which newcomers find easier).

**Tests**
* GDScript: the car reaches top speed, turns more slowly at speed, slows on grass, bumps off
  a barrier, drifts; the sprite's frame for 16 headings; the camera leads the velocity.
* Python: `car_math` matches the GDScript over a table of cases (the shared-arithmetic rule).

**Done when**
* One car drives round a flat test track from the `racer` pack and from the drawn kit.

## T16.13 — The track plan and the track recipe

**Depends on:** T16.12
**Files:** `rpggen/core/track_plan.py` (new, pure Python), `rpggen/core/world_plan.py` (a
`tracks` section), `recipes/racing/track_recipe.gd`, `rpggen/core/map_preview.py` (a track
picture), `tests/unit/test_track_plan.py` (new)

**Spec**
* `track_plan.plan(options, seed, facts) -> list[Track]`: a track is a **closed loop** on a
  grid of road cells (a random walk on a coarse grid of `cells` × `cells`, smoothed into
  straights, 90° curves and S-bends; a loop must not cross itself), with a start line, N
  **checkpoints** in order (so cutting is impossible), **waypoints** along the centre line
  for the rivals (position, ideal speed), the surface of every cell (road, dirt, a patch of
  oil, a boost arrow), barriers along the outside, and decoration (`DECORATION` sprites)
  outside the road. `tracks` (default 4) with a rising difficulty: longer, more curves, more
  hazards; `laps` per track. The plan is stored and reused; *Added tracks* grows it.
* The recipe paints the track with the `GROUND` road tiles (the `road`, `finish`, `tyre`
  tags choose the tiles; a pack without road tiles gets the drawn road sheet) through the
  TileSet and terrain of M1–M8, places the barriers, the pickups and the decoration, and
  writes `game/data/tracks.json`.
* The Options page preview (T16.16) draws the loop from the plan, as the world preview does.
* **Finishability** (`VAL-029`): the loop is closed, every checkpoint is reachable in order,
  the width is at least two cars; else a re-roll.

**Tests**
* Deterministic plans; a loop never crosses; checkpoints in order along the loop; the
  recipe paints the `racer` and the top-down sample packs; the preview picture is drawn.

**Done when**
* Four tracks are generated and one can be driven lap after lap.

## T16.14 — Rivals, laps, checkpoints, pickups

**Depends on:** T16.13
**Files:** `archetypes/racing/rival.gd`, `archetypes/racing/race.gd`, `archetypes/racing/checkpoint.gd`,
`archetypes/racing/pickup.gd`, `recipes/racing/rival_recipes.gd`

**Spec**
* `Rival` drives the waypoints with the same `car_physics` (no cheating physics), a skill per
  rival (how early it brakes, how well it holds the line), rubber-banding kept small and
  optional, and bumps into the player like any car. The `ENEMY` assets (or the car recoloured
  by the variant pipeline of T13.18, automatically, when the pack has one car) are the
  rivals; `rivals` (default 3) is an option.
* `Race`: a countdown (`sfx_countdown`), the start, positions from checkpoint progress and
  distance to the next waypoint, laps counted at the start line only after every checkpoint,
  a wrong-way warning, the finish and the standings.
* Pickups from the plan (RC Pro-Am's set): a missile (fires forward, spins the car it hits),
  a bomb (drops behind), a boost, a shield (one hit), and the parts that stick across the
  championship (`speed`, `tyres`, `acceleration` upgrades), with `POWERUP` art or the drawn
  icons.

**Tests**
* GDScript: a rival completes a lap on each generated track; positions update when the
  player overtakes; a lap is not counted when a checkpoint was skipped; each pickup's effect.

**Done when**
* A race against three rivals with pickups can be won and lost.

## T16.15 — Championship, results and the HUD

**Depends on:** T16.14
**Files:** `archetypes/racing/championship.gd`, `archetypes/racing/ui/race_hud.gd`,
`archetypes/racing/ui/results.gd`, `recipes/racing/hud_recipe.gd`,
`godot_templates/project_files/README.racing.md` (new)

**Spec**
* The championship: the tracks in order, points per finish position, a results screen after
  each race (positions, points, the parts won), a championship table, elimination when the
  player finishes last twice (an option), the credits at the end; saving between races.
* The HUD: lap, position, speed, the pickup held, a mini-map of the track with the cars (the
  minimap of T12.64 reused), the countdown and the wrong-way sign.

**Tests**
* Points and the table over a scripted championship; the HUD's values.

**Done when**
* Racing is a whole game behind `RACING_AVAILABLE`.

---

# Part E — The wizard, the samples, the gate

## T16.16 — Wizard: cards, roles, options and previews

**Depends on:** T16.07, T16.11, T16.15
**Files:** `rpggen/gui/pages/archetype_page.py`, `rpggen/gui/widgets/options_sections.py`
(three boxes), `rpggen/gui/widgets/options_summary.py`, `rpggen/gui/widgets/map_preview.py`,
`rpggen/core/options.py`, `rpggen/gui/models/options_model.py`, `rpggen/core/profiles.py`
(presets), `tests/gui/test_archetype_page.py`, `tests/gui/test_options_page.py`,
`tests/gui/test_layout_fit.py`

**Spec**
* **Six cards** on the Archetype page: at 1000 px and wider, two rows of three (the drawing
  shrinks to 160 px high so two rows fit at 720 px); below that, one scrolling column of
  cards with the drawing at the left. Each new kind has its `MockScreen` drawing (a ship over
  stars, a soldier on a ledge aiming up, a car on a curve), its three-line text, its controls
  line and its flow (`Fly → Shoot → Power up → Boss`, `Run → Aim → Shoot → Boss`,
  `Drive → Overtake → Lap → Podium`). The pack view's hint (T16.02) points at a card.
* **The Mapping page** shows the kind's roles and sound slots (T16.03) with the kind's
  wording; the racing rows show the heading count beside the `VEHICLE` thumbnail.
* **Options**: a `ShmupBox`, a `RunAndGunBox` and a `RacingBox` in place of the starter map
  box for the kind, with the options of T16.06, T16.10–T16.11 and T16.13–T16.15, each with
  a **preview** from the plan: the shoot 'em up's wave chart (stages as columns, waves as
  marks with the boss at the top), the run and gun's stage strip (chunks, spawners, the
  boss arena, the grapple points when jumping is off), the racing loop with checkpoints
  and pickups. The summary names the kind and its numbers (*Shoot 'em up · vertical · 3
  stages · 3 lives*), and the estimate (T13.07) learns per kind.
* **Presets** that ship: *Arcade classic* (3 lives, no continues, hard), *Bionic* (run and
  gun, no jump, grapple), *Sunday drive* (racing, absolute steering, 2 rivals, rubber-banding).
* `rpggen generate --archetype shmup | run_and_gun | racing`; a dry run describes the plan
  (*3 stages, 24 waves, 3 bosses*; *4 tracks of 3 laps, 3 rivals*).

**Tests**
* The cards render at both sizes without clipping; choosing each kind shows its box and
  roles; the previews draw from a plan; the presets fill the options; the CLI accepts the
  keys and rejects an unknown one with exit 2.

**Done when**
* Each kind can be chosen, configured and previewed in the wizard at 880 × 540.

## T16.17 — Three sample packs and *Try the sample*

**Depends on:** T16.16
**Files:** `tools/build_sample_pack.py`, `sample_pack_shmup/`, `sample_pack_gun/`,
`sample_pack_race/` (new, CC0), `rpggen/gui/pages/welcome_page.py`, `rpggen/gui/pages/project_page.py`,
`tests/golden/`, `tests/gui/test_sample_pack.py`

**Spec**
* The three packs, drawn by the tool from primitives like the two existing ones: *Star lane*
  (a ship, six enemies, a boss, bullets, capsules, two star layers, three short loops of
  music, five sounds), *Jungle line* (a soldier with every animation of T16.08, five enemies,
  a wall boss, a tile sheet with grapple ceilings, two layers, four weapons, a hook), *Dirt
  cup* (a car in 16 headings, three rivals, a road sheet, cones, tyres, oil, boost arrows,
  pickups). Each under 200 KB, with a licence file.
* *Try the sample* lists five: the two existing and *Star lane*, *Jungle line*, *Dirt cup*;
  the Project page's sample button offers the same list. Each sets the kind.
* Goldens for the three packs; the top-down and side-view goldens do not move.

**Tests**
* Each sample is catalogued without an edit and its goldens hold; the welcome menu lists
  five and each lands on the right kind.

**Done when**
* Each sample generates and plays with no note but `ASSET-031` where the pack is minimal on
  purpose.

## T16.18 — Smoke sequences and integration tests

**Depends on:** T16.17
**Files:** `godot_templates/builder/smoke/smoke_steps_shmup.gd`, `smoke_steps_run_and_gun.gd`,
`smoke_steps_racing.gd` (new), `rpggen/core/orchestrator.py` (`OWN_SMOKE_STEPS`),
`tests/integration/test_shmup.py`, `test_run_and_gun.py`, `test_racing.py` (new),
`tests/perf/test_perf.py`, `.github/workflows/ci.yml`, `pyproject.toml` (markers)

**Spec**
* Each kind has its **own sequence** (the world is not the village): title → new game →
  the first stage: shoot 'em up: survive the first two waves with the debug invulnerability
  of the smoke harness, kill the mid-stage carrier, collect a power-up, kill the boss with a
  debug damage multiplier, see *Stage clear*, save, load, reach the credits of a one-stage
  run; run and gun: run to the first spawner, kill it, pick up the spread gun, cross a gap
  (jump, and in a second run, grapple with jumping off), kill the boss, the credits; racing:
  the countdown, one lap with every checkpoint, a pickup used, overtake a rival with the
  debug speed, finish, the results, the next race, the championship table. Each sequence
  asserts the positions and counts it passes, as the metroidvania's does.
* Integration tests per kind (its marker and CI job), the regeneration test extended with a
  project of each kind (nothing moves on a repeat; *Added stages* / *Added tracks* grows the
  plan and leaves the old ones), the determinism test, the JSON result against the schema.
* Perf: the three samples under 120 s each; the GUI integration test of each wizard path.

**Tests**
* They are the card.

**Done when**
* The three jobs are green on Windows and Ubuntu.

## T16.19 — Documentation, screenshots and changelogs

**Depends on:** T16.18
**Files:** `docs/user_guide.md` (three sections, like *3a. Metroidvania*), `README.md`,
`CHANGELOG.md`, `godot_templates/addons/rpg_runtime/CHANGELOG.md`, `docs/status.md`,
`docs/spec/00_START_HERE.md`, `docs/architecture.md`, `docs/images/` (the six cards, the
three option previews, one in-game picture per kind), `tools/make_doc_screenshots.py`,
`docs/errors.md` (the new codes)

**Done when**
* A reader of the guide can make each kind from its sample and from a pack of their own.

## T16.20 — Gate (1.4.0)

**Depends on:** T16.19

* CI green on every job, both PySide6 legs, perf within the ceilings; the frozen smoke test
  on three systems (the samples and the drawn kit are in the bundle).
* The upgrade test over a 1.0, 1.1, 1.2 and 1.3 project of each older kind: no prompt,
  nothing under `game/` changes, byte-identical TileSets and sprite frames.
* The corpus unchanged on all four measures.
* Manual rows, with a gamepad: play *Star lane* in both orientations to the credits (the
  feel of the focus button and the bombs); play *Jungle line* with jumping and as Bionic;
  win *Dirt cup* with relative and absolute steering; generate each kind from a real pack
  you own that was made for it (a shooter pack, a platformer pack, a top-down vehicle pack)
  and from a plain RPG pack (every stand-in drawn), and compare the notes; a 300-asset
  shooter pack through the audit.
* Then flip the three flags on and tag `v1.4.0`.

---

# Part F — Kinds considered for M17

Each of these fits the packs rpggen is made for and reuses most of what exists. They are
sketched here so the next milestone can pick; none is part of 1.4.0. Sizes are for the whole
kind, wizard and samples included.

| Kind | Key | In the line of | Seen from | Reuses | New | Size |
|------|-----|----------------|-----------|--------|-----|:----:|
| **Beat 'em up** | `brawler` | Streets of Rage, River City Ransom | the side, with depth (the hero walks up and down the street) | the real-time combat primitives, the ARPG's enemies, the arcade framework (stages, waves that stop the scroll, bosses, continues), equipment and shops between stages | a lane actor (a ground plane with a Y-sort and a jump), combos, grabs and throws, throwable objects, two-player co-op on one keyboard or two pads | L |
| **Dungeon run** | `dungeon_run` | The Binding of Isaac, the dungeons of Zelda | the top | the ARPG combat, the room graph and the lock-and-key planner (M14 rooms turned top-down), items, chests, the minimap, saving as a meta-progress file | a run that is planned from a fresh seed each time, items that stack their effects, a boss room per floor, permadeath with unlocks, a floor map | L |
| **Tactics** | `tactics` | Fire Emblem, Advance Wars | the top | the turn-based battle actors, skills, statuses and AI (M7, T12.71), the party, the TileSet and terrain (cover, movement cost per surface), dialogue between maps | a grid battle on the map itself (move range, attack range, terrain bonuses, facing), a unit roster that persists, map objectives (rout, seize, survive), a campaign of maps | XL |
| **Tower defense** | `tower_defense` | Kingdom Rush | the top | the TileSet, the pathfinding layer (navigation), the enemy sprites and the projectiles, the arcade waves and the HUD, saving | a path on the starter map, towers built from `BUILDING` and `DECORATION` sprites with a range and a rate, money per kill, wave countdown, a tower-upgrade tree | M |
| **Farm and life sim** | `farm` | Stardew Valley, Harvest Moon (the *Super Retro Ranch* pack above is made for exactly this: crops with growth strips, tools, animals, weather, 9-slice UI) | the top | nearly everything of the RPG kinds: dialogue, NPC schedules, inventory, equipment (tools), shops, quests, the day and night cycle (T12.62), saving, interiors, the second map | crops with growth stages (a `CROP` role, drawn when missing), tilled soil as a terrain, energy and seasons, a calendar, relationships, fishing, animals | XL |
| **Twin-stick arena** | `arena` | Smash TV, Enter the Gungeon's rooms | the top | the ARPG actor with the shoot 'em up's guns and bullet pool, the arcade waves and bosses, the dungeon run's rooms | an aim stick independent of movement, arena rooms that lock until cleared, a dash with invulnerability | M (after `shmup` and `dungeon_run`) |
| **Isometric tiles** | option of `racing` and the top-down kinds | RC Pro-Am's own view, Diablo | isometric | the TileSet recipe (Godot's isometric tile layout), the collision and terrain facts | detection of isometric tile sheets (the diamond footprint), an isometric starter-map and track planner, a Y-sort that follows the diamond | L |

**A recommended order for M17:** `tower_defense` (small, proves the top-down arcade path),
`brawler` (the most asked-for arcade kind after the three of M16; the combat is there), then
`dungeon_run` (the planners are there), and `tactics` as its own milestone. `farm` is a
milestone on its own, and the most valuable for RPG packs, which were drawn for exactly that
kind of game.

---

## Appendix — The request of 2026-10-09, item by item

| Asked for | Card |
|-----------|------|
| A space shooter, vertical and horizontal | T16.04 – T16.07 (`shmup`, with `orientation`) |
| Games like Contra | T16.08 – T16.10 (`run_and_gun`) |
| Games like Bionic Commando | T16.11 (the grapple, and the *Bionic* preset with jumping off) |
| Racing games like RC Pro-Am | T16.12 – T16.15 (`racing`; its isometric view is an M17 option) |
| Others | Part F: beat 'em up, dungeon run, tactics, tower defense, farm and life sim, twin-stick arena |
