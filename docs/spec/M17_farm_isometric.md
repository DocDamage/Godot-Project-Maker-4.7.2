# M17 — Farm and Life Sim, and Isometric Tiles (release 1.5.0)

**Goal:** the two things chosen on 2026-10-12 from the kinds sketched in Part F of M16: a
**farm and life sim** in the line of Stardew Valley and Harvest Moon, the seventh kind of game,
and **isometric tiles**, which are not a kind but a second way of seeing the top-down kinds and
the racing game (RC Pro-Am's own view). Part A is what both need from detection and the
runtime, Part B the farm, Part C the isometric view, Part D the wizard, the samples, the
documentation and the gate. Part E keeps the kinds that were not chosen, for a later milestone.

This file follows the format of M01–M16. It was written against `main` at `b610f90` (M16
merged, its gate open, no release tagged) on 2026-10-12. The farm's cards (T17.01 to T17.11)
and the isometric cards (T17.12 to T17.15) were implemented on the branch `m17` on that day
and the next, and Part D (the wizard, the samples, the tests, the documentation) on
2026-10-13. Every card but the gate is implemented and both flags are on; the gate (T17.20)
is open: nobody has played either, CI has not run on `m17`, and nothing is tagged. Where
what was built differs from a card below, the notes (`docs/dev/implementation_notes.md`) say
so and the index names it.
This milestone starts after `v1.4.0` is tagged and ends with `v1.5.0`. Nothing in it changes
an existing kind unless its project turns the isometric option on: a 1.0–1.4 project
regenerates with 1.5 without a prompt.

## What the two are

| What | Key | Seen from | In one line | Reuses most |
|------|-----|-----------|-------------|-------------|
| Farm and life sim | `farm` (an archetype) | the top, or isometric | You till, plant, water and harvest through days and seasons, keep animals, sell what you grow, and get to know the people of a village | the top-down player, maps, doors and interiors (M4), dialogue, inventory, equipment, shops (T12.46, T13.11), quests, the day and night light (T12.62), the second map, saving |
| Isometric tiles | `projection: isometric` (an option of `turn_based`, `arpg`, `farm` and `racing`) | at an angle: tiles are diamonds | The same game, on a pack whose tiles are drawn as diamonds | the TileSet recipe, the terrain and collision facts, the starter-map and track planners, Y-sort |

The farm is the kind RPG packs were most often drawn for (M16, Part F). Isometric is the view
of a large family of packs rpggen cannot use at all today: their sheets are read as pictures
or as a square grid that cuts every tile in four.

## What the real packs look like

One pack the user owns was listed for the farm on 2026-10-09 (file names and image sizes only;
the art was not opened): *Super Retro Ranch* premium, 1,040 files. What M16 recorded of it,
and what follows for this milestone:

| What the pack has | What it means here |
|-------------------|--------------------|
| A strict naming scheme `<thing>_<nn>_<colour>_<action>_<direction>_<W>x<H>_<N>frames.png` (`cow_01_brown_move_down_32x32_4frames.png`, `corn_16x32_8frames.png`) | The cell and the frame count are in the name (read since T16.21). A crop strip is `<crop>_<W>x<H>_<N>frames` with no action and no direction: T17.01 has to tell it from an animation. |
| Crops with 7 to 29 growth frames | A crop's stages are the frames of its strip, in order; the last is the ripe one. The number of days a crop takes is not in the pack: the plan gives it (T17.05). |
| Animals in 36 colour variants (288 files for one cow), with `move`, `sleep`, `dead`, `fly` | Colour variants are one card since T16.21. `move` is walk. An animal needs walk and, when it has one, sleep. |
| Tools: hoe, shovel, water, sickle | Tool icons and, on the farmer's sheet, a use animation per tool when the pack draws one. |
| Weather overlays, 9-slice UI themes | Rain and snow as full-screen overlays; the `_9split` pieces are UI since T16.21. |
| The same art in five engine layouts; Godot's 3x3 autotiles | Read from Godot's folder since T16.21; the 47-tile sheets are terrains since the reader of 2026-10-10. 9 of its 20 terrain sheets are not read yet (fences, plain grounds, templates): T17.01. |
| Not CC0: credit asked, no redistribution, no NFT or AI use | The pack is never part of the repository, a sample or a test. **Its pictures are not opened, read into a model, or generated from**: as in M16, only its file names and sizes are used to decide what the readers must understand. The *Done when* rows that name it are run by the owner on the owner's machine. |

**The isometric packs** were named on 2026-10-12: the folder `D:\kenney assets\2D assets`
(Kenney, CC0), which has 23 packs with *Isometric* or *Axonometric* in their names among 154.
They were listed by file name and image size, and their text files were read. They are not
what Part C first assumed (sheets of diamonds on a grid), and Part C is written from them:

| Pack (files) | What it taught |
|--------------|----------------|
| *Medieval Town* (268), *Modular Buildings* (404), *Modular Roads* (1,208), *Nature* (752), *Space Interior* (320), *Tower Defense* (472), *Minigolf* (192) | **One picture a tile, every picture of a pack the same size**, the tile standing at the bottom of it: 210 x 244, 224 x 206, 180 x 184, 220 x 379, 240 x 192, 124 x 123, 180 x 256. A text file says what the pictures cannot: `Tile information.txt` (*Image size : 210 x 244 px*, *Tile size : 180 x 115 px*) or `Tiled (settings).txt` (*Orientation: Isometric*, *Map tile size: 180 x 104 px*, *Tileset tile size: 180 x 256 px*). **The footprint is not twice as wide as high**: 180 x 115, 180 x 125, 120 x 98, 120 x 74, and 180 x 104 for the map, which is the true 30 degree angle. Names are `<pack>_<nnn>_<r>.png` or `<thing>_<nn>_<r>.png` with `r` from 0 to 3: **the same tile turned four ways**, not four frames of an animation (the numbered-frame reader of T16.21 would take them for one). |
| *Tiles Base* (128), *Tiles City* (128 and 11 details), *Tiles Buildings* (129) | Older: `landscapeTiles_000.png` to `_127`, **pictures of different sizes with one width** (132 or 133 wide; 83, 99, 101, 131 high): the tile is the bottom of the picture and what is above it is its height. No text file. A `Spritesheet/` folder with the same pictures packed and a `<TextureAtlas>` XML of `<SubTexture name x y width height>`: the pack ships its art twice. |
| *Vector Roads Base* (96), *Vector Roads Water* (42), *Vector Buildings* (658) | 100 x 65 and 50 x 55 pictures whose **names say which sides join**: `beachCornerES.png`, `beachE.png`, `bridgeHighEW.png`, `waterSW.png` (N, E, S, W and pairs of them). Four building materials in four folders with the same 155 names. |
| *Miniature Farm*, *Dungeon*, *Library*, *Overworld*, *Prototype* (each a zip beside a `Preview.png` and a `Sample.png` of 918 x 515) and *Miniature Bases* (unpacked: 320 pictures of 256 x 512) | **The pack is a zip inside its folder**, with previews beside it. Inside: the same 229 names twice, in a folder `Isometric/` and a folder `Angle/` (**two views of one model**), each name with `_N`, `_E`, `_S`, `_W` (`cornDouble_E.png`): the four turns by a letter. *Miniature Farm* has corn, a chimney and the rest of a farm: the one pack that is both halves of this milestone. `Information.png`, `Samples/`, three `.url` files. Only *Miniature Farm*'s zip was listed; the other four are taken to be alike. |
| *Tiles Vehicles* (553) | Cars as **one small picture a heading** (17 to 33 px): `taxi_N.png`, `_NE`, `_E`, … eight headings, and `_NEU`, `_NED` and the like for a car going up or down a slope; five colour folders (`Civilian/Black/Sedan 1/`), four service cars. The isometric racing car of T17.15. |
| *Watercraft* (232) | 512 x 512, `watercraftPack_001_0.png` to `_7`: eight turns by a number; a sheet and an XML for each boat. |
| *Isometric Blocks*, *Axonometric Blocks* (135 each) | One model set in two projections as two packs: 111 x 128 and 92 x 80. *Axonometric* is not the isometric angle. |

What follows from it, by card: a pack of one picture a tile with the tile at the bottom, its
footprint from the pack's text file or measured, never assumed 2:1; turns by `_0`–`_3`,
`_0`–`_7` and by compass letters, which are variants of a tile and headings of a vehicle,
never frames; sides in a name as how a tile joins; `Isometric/` chosen over `Angle/`; a zip
inside the pack folder opened; an atlas XML beside loose pictures as a duplicate; previews and
samples left out (T17.12). The TileSet is built from single pictures, not cut from a sheet
(T17.13). **None of the packs that were listed has a character** (the four unopened zips
were not looked into): an isometric game takes its people from another pack or has them
drawn (T17.14). No pack has autotiles: ground joins by whole tiles whose names say how.

## Ground rules for this milestone

* The M12–M16 ground rules apply: core logic stays out of the GUI, pages only edit
  `WizardState`, generated output is deterministic, `.tscn` / `.tres` / `project.godot` are
  never written by hand, every Godot API is verified in `docs/godot_api_verified.md` before
  use, recipe changes bump `RECIPE_VERSION`, new smoke steps are added to the lists the
  integration tests assert, the layout test stays green at the minimum window, and the
  post-release compatibility contract holds (`config_version` 1, `save_version` 1, nothing
  under `game/` rewritten, no generated script moved or renamed).
* **Additive only.** The farm lives in `archetypes/farm/` in the runtime and `recipes/farm/`
  in the builder; the install filter keeps both out of the projects of every other kind.
  What the farm shares with others (the calendar, NPC schedules) goes into shared folders
  (`world/`, `actors/`) and is inert in a project that does not use it. The older kinds'
  goldens, TileSets and sprite frames do not move; the corpus (T12.26) is unchanged on all four
  measures after every detection card.
* **Isometric is an option, off by default.** `projection` is `top_down` in every config that
  does not say otherwise, and a top-down project is byte for byte what it was. A project
  cannot change its projection once it has been generated (its maps are painted in one): the
  wizard says so and the config check refuses it, as it does a changed tile size.
* **Every pack makes a game.** What a pack lacks for the farm is drawn (`farm_kit.py`, beside
  `side_kit.py` and `arcade_kit.py`): a crop in five stages, tilled and watered soil, the
  four tools, a hen, a shipping bin. A drawn stand-in is the note `ASSET-031`. The isometric
  option draws no ground: it needs isometric ground tiles, and without them the option is not
  offered. It does draw a hero, a villager and an enemy for the view (`iso_kit.py`), because
  the isometric packs that were listed have none.
* **Feature flags.** `features.FARM_AVAILABLE` and `features.ISOMETRIC_AVAILABLE`, off until
  their gate rows pass; an off kind's card is disabled and its sample is not offered, and an
  off option is not shown.
* **New roles, usages, tags and sound slots** are added to `02_SCHEMAS.md` and the catalog
  schema first; the audit offers them for every kind; the kinds that do not use them ignore
  them.
* **New error codes** go into `03_ERROR_CODES.md` first, then `python tools/gen_error_codes.py`.
  Reserved: `ASSET-034` (a crop with one picture: it has no stages to grow through),
  `TILE-010` (an isometric sheet whose footprint could not be read), `TILE-011` (isometric and
  square ground in one project), `VAL-031` (a farm that cannot be worked: no soil to till, or
  the field, the bed or the bin cannot be reached), `SMOKE-013` (the farm's own sequence).
* **Samples.** `sample_pack_farm` (a farm, top-down) and `sample_pack_iso` (an isometric
  village), each CC0, under 200 KB, built by `tools/build_sample_pack.py` from drawn parts,
  with goldens. *Try the sample* lists seven.
* **Perf and CI.** The farm has its own integration job (`farm` marker) and perf ceiling (its
  sample under 120 s); the isometric runs are a job of their own (`isometric` marker) over
  the isometric sample as a turn-based game and as a racing game.
* **Controls.** Playable on keyboard and gamepad from the start with the bindings of
  `config.default_input("farm")`; the glyphs (T12.55) cover the new actions. The isometric
  option changes no binding.
* **Tests run before a push** include the slow GUI tests (`-m "slow and not integration"`),
  which CI's Ubuntu job runs and which the local runs of M16 left out until its first CI run.

## Order of work

| Step | Tasks | Why this order |
|------|-------|----------------|
| 1 | T17.01, T17.02, T17.03 | Detection, roles and stand-ins, and the calendar: the farm needs all three |
| 2 | T17.04 – T17.06 | The farmer, soil and crops, and the farm's plan: a field can be worked from seed to harvest |
| 3 | T17.07 – T17.11 | Animals, the economy, people, fishing and foraging, weather and the HUD: the life around the field |
| 4 | T17.12 – T17.14 | Isometric: reading the sheets, the TileSet, maps and actors, for the top-down kinds and the farm |
| 5 | T17.15 | Isometric racing, on the track plan of M16 |
| 6 | T17.16 – T17.18 | The wizard, the two samples, the smoke sequences and tests |
| 7 | T17.19, T17.20 | Documentation, the gate, then tag `v1.5.0` |

The farm can be released alone behind its flag if the isometric view is late, and the other
way round.

## Index

Sizes are rough: **S** under a day, **M** 1–3 days, **L** 3–7 days, **XL** more than a week.

| Card | Title | Size | Depends on | Status |
|------|-------|:----:|------------|--------|
| T17.01 | Detection for the farm | M | — | done on synthetic packs; the fence and the 2 x 2 readers were not run on the real pack, and the `multi_engine` golden moved on purpose (the notes) |
| T17.02 | Roles and drawn stand-ins | M | T17.01 | done; the `ranch` and `multi_engine` goldens moved on purpose (the notes) |
| T17.03 | The calendar: time, days and seasons | M | — | done; with a calendar the light follows it whatever the *Day and night* setting says (the notes) |
| T17.04 | The farmer, tools and energy | M | T17.02, T17.03 | done with T17.05 as one commit; the sickle and the axe are bought, *working at zero ends the day* is not done, and nothing was seen on a screen (the notes) |
| T17.05 | Soil and crops | L | T17.04 | done; a field has no edges (one tile of a pack's soil terrain) (the notes) |
| T17.06 | The farm plan and the farm recipe | L | T17.05 | done; `added_maps` are names only, and a project from before its second part has no door to its farm (the notes) |
| T17.07 | Animals | M | T17.06 | done; a coop on a pack with only cows stays empty, and the pail was dropped (the notes) |
| T17.08 | Money: the shipping bin, the shop, the end of a day | M | T17.06 | done; the counter pays what the bin pays and the bed asks nothing (the notes) |
| T17.09 | People: schedules, gifts and friendship | L | T17.03, T17.06 | done; all places are on the village, nobody is an angler (the village has no water) (the notes) |
| T17.10 | Fishing and foraging | M | T17.08 | done; the bar and the bite were looked at in a probe only (the notes) |
| T17.11 | Weather and the HUD | M | T17.05, T17.08 | done; natural weather and the season swap are covered by unit tests only (the notes) |
| T17.12 | Isometric packs: reading one picture a tile | L | — | done; of the 23 real packs, the civilian cars of *Tiles Vehicles*, *Tiles Buildings* and the characters of two *Miniature* packs are read wrongly or not at all (the notes) |
| T17.13 | The isometric TileSet | L | T17.12 | done; a raised ground block does not block, and no isometric terrain is read (the notes) |
| T17.14 | Isometric maps and actors | XL | T17.13 | done for the turn-based game, the action RPG and the farm; imported maps and the editor dock count squares, and real packs show faults whose causes were not found (the notes) |
| T17.15 | Isometric racing | M | T17.14 | done; a round corner piece on a square corner of the plan, and nobody has driven it (the notes) |
| T17.16 | Wizard: the Farm card, the projection, options and previews | L | T17.11, T17.14 | done; the box has no combat option (nothing of a farm reads it), the picture of an isometric race is drawn from above, and the *Pad* choice is shown for a race that does not use it (the notes) |
| T17.17 | Two sample packs and *Try the sample* | M | T17.16 | done; the buildings of *Green acre* are objects of one sheet, since that is what the farm's planner sees (the notes) |
| T17.18 | Smoke sequences and integration tests | M | T17.17 | done locally on Windows; the two CI jobs have not run, and a slime in a folder of characters is still an NPC without the sample's profile (the notes) |
| T17.19 | Documentation, screenshots and changelogs | M | T17.18 | done; all pictures were made again on Windows (the notes) |
| T17.20 | Gate (1.5.0) | M | T17.19 | open: the flags are on and the suites pass locally on Windows; CI, the frozen build, the upgrade test, the corpus and every manual row are not done, and `v1.5.0` is not tagged |
| T17.21 | Real packs: cars by their pictures, the buildings' diamond, wall pieces, characters in eight facings | L | T17.12 | open |
| T17.22 | Real packs in the builder: walls along an edge, a house of pieces, round road corners | L | T17.21 | open |
| T17.23 | Added maps are built | L | T17.06 | done for a forest and a beach; they are maps of the farm's own recipe and not areas of T13.20, the farm's door to one is a mark beside its edge in a scene that is written on every build, a farm from before the card keeps names, and no person goes there (the notes) |
| T17.24 | The cave: combat on a farm | L | T17.23 | done: *Combat* on adds a cave and a cave row needs *Combat*; the enemies are the action RPG's (its folder is installed only in a farm that fights), the farmer's health, hurtbox and blade are made at run time, and the rock is drawn flat; nobody fought by hand (the notes) |
| T17.25 | Festivals and birthdays | M | T17.09 | done; the eggs and the table are drawn shapes of the game and the table can be walked through, a farm from before the card has its calendar in the pause menu only, its eggs round the square and no festival lines in its dialogues, and nobody has played a festival by hand (the notes) |
| T17.26 | Marriage | L | T17.25 | done; the smoke run is given the hearts it courts with, the spouse is not seen at night and never walks onto the farm, a farmhouse from before the card keeps its one bed and its people's dialogues have no lines for courting, and nobody has courted anybody by hand (the notes) |
| T17.27 | The editor dock on diamonds | M | T17.14 | done locally on Windows: run by tests, one of them in an editor without a window, and looked at in a picture of the game; nobody dropped anything with a mouse, and drop-to-floor has no meaning on diamonds. Three old faults of the dock's placement, on any map, were found and left (the notes) |
| T17.28 | Imported maps in the isometric view | L | T17.14 | done locally on Windows: the Tiled sample of *Isometric Miniature Farm* is the starter map of a generated isometric turn-based game that passes its smoke sequence, looked at against Tiled's drawing of the map (the pack's `Sample.png` is a picture of another scene); a picture of a pack's samples joins the tile set for its map alone and stays unused, walls block by role or (unused) by name, a second floor is only drawn higher and flips are dropped; TILE-013 for a map of the other view (the notes) |
| T17.29 | Real farming packs: one tile set in several forms, crops, farm animals and layered characters | L | T17.21 | done locally on Windows: the three packs each give a farm with their own ground, crops that grow in their pictures and a player of the pack, played by the farm's smoke sequence and looked at in pictures; *Tiny Farm*'s player and hen are numbered tiles nothing names, chosen in the audit as a user would; the size choice is on the Audit page's *Packs* tab, not the Project page (the notes) |

---

# Part A — Shared foundations

## T17.01 — Detection for the farm

**Depends on:** nothing
**Files:** `rpggen/core/classifier.py`, `rpggen/core/adapters/naming.py`,
`rpggen/core/adapters/strips.py` (growth strips), `rpggen/core/terrain/blob.py` (the sheets
still unread), `rpggen/core/pack_sniff.py`, `tests/unit/test_classifier.py`,
`tests/unit/classifier_cases.json`, `tools/make_synthetic_packs.py` (a `ranch` pack)

**Spec**
* **Growth strips.** A strip whose name has a crop word or the `growth` tag (parsed since
  T16.21, unused) and no action word and no direction is a **growth strip**, not an animation:
  usage `growth_strip`, its frames are stages in order, the last the ripe one. The catalog
  records `stages: N`. A strip of crops by size alone (several frames, each taller than wide,
  in a folder named crops, plants, seeds or farming) is offered as one for review. A crop of
  one picture is `ASSET-034`, a note, and grows through drawn stages (T17.02).
* **Tags from folder and file words:** `crop` (crop, plant, vegetable, fruit, and the common
  names: corn, wheat, carrot, tomato, potato, pumpkin, turnip, strawberry, …; the list lives
  in `classifier.py` with the others), `seed` (seed, seeds, sapling), `soil` (soil, tilled,
  farmland, dirt_tilled, plowed), `watered` (watered, wet_soil), `tool` (hoe, shovel,
  watering_can, water, sickle, scythe, axe, pickaxe, rod), `animal` (cow, chicken, hen, sheep,
  pig, goat, duck, horse), `product` (egg, milk, wool), `coop`, `barn`, `fence`, `bin`
  (shipping_bin, crate), `weather` (rain, snow, storm: a full-screen overlay, never a tile),
  `fish`, `forage`, and `season:<name>` for a folder or word spring, summer, autumn, fall or
  winter (a seasonal variant of a tile sheet or a tree). Tags change nothing for the other
  kinds.
* **Seasonal variants.** Sheets that differ only by a season word are grouped like colour
  variants (T16.21): one asset with `season:` tags on its members, so the farm can swap the
  ground and the trees with the season. One card in the audit.
* **Pack view** (`classifier.pack_view`) gains `farm` (crop, soil and animal words; a growth
  strip). The pack card says *Looks like a farming pack* and the Archetype page's hint points
  at the card.
* **The terrain sheets the reader still leaves** (the notes of 2026-10-10): a **fence sheet**
  (22 tiles that join at their sides only, in the template's 12 x 4 shape) is read as a
  sides-only terrain; a 2 x 2 layout is read as a corner set in the order the pack ships it.
  Animated autotiles (four sheets side by side) stay unread and are listed in the notes.
* A synthetic pack `ranch`, in the naming scheme of the table above: a farmer with walk and
  tool strips, three crops with 5, 8 and 12 growth frames, one crop of a single picture, a
  cow and a hen in three colour folders with `move` and `sleep`, four tools, tilled and
  watered soil as 47-tile sheets, a fence sheet, a grass sheet in four season folders, a rain
  overlay, a house, a coop, a bin.

**Tests**
* The classifier cases for every tag and the pack view; a growth strip against an idle
  animation of the same size; the seasonal grouping; the fence sheet; the `ranch` golden; no
  other golden moves; the corpus is unchanged on all four measures.

**Done when**
* The `ranch` pack is catalogued with the right roles, usages and stages without an edit.

## T17.02 — Roles and drawn stand-ins

**Depends on:** T17.01
**Files:** `rpggen/core/farm_kit.py` (new), `rpggen/core/requirements.py`,
`rpggen/core/mapping.py`, `rpggen/core/sound_slots.py`, `rpggen/schema/catalog.schema.json`,
`docs/spec/02_SCHEMAS.md`, `docs/spec/03_ERROR_CODES.md`, `tests/unit/test_farm_kit.py` (new),
`tests/unit/test_requirements.py`

**Spec**
* **Roles** (labels in the audit and rows on the Mapping page, in every kind): `CROP` (a
  growth strip, or one picture), `ANIMAL` (a farm animal; `NPC` stays for people and `ENEMY`
  for what fights), `TOOL` (an icon). `PLAYER`, `GROUND`, `BUILDING`, `NPC`, `ITEM`,
  `DECORATION`, `UI` are reused. Required for `farm`: `PLAYER` and `GROUND`; everything else
  is optional with its wording in `REQUIRED_BY_ARCHETYPE` (`BUILDING` is *the house, the coop
  and the barn*, `ITEM` *seeds, produce and what the shop sells*).
* **Drawn stand-ins** (`farm_kit.py`, deterministic, in the pack's tile size, all `ASSET-031`
  notes): a crop in five stages (three crops in three colours), tilled soil and watered soil
  as tiles, four tool icons (hoe, watering can, sickle, axe), a seed bag, a hen with a walk,
  an egg, a shipping bin, a bed, a rain overlay. A pack's own asset always wins.
* **Sound slots** of the kind: `sfx_hoe`, `sfx_water`, `sfx_plant`, `sfx_harvest`, `sfx_sell`,
  `sfx_animal`, `sfx_rooster` (a new day), `music_spring`, `music_summer`, `music_autumn`,
  `music_winter` (a season without its own plays the first that is filled), `music_night`.
  Filled by file name as today; silent when empty.

**Tests**
* Every stand-in renders at 16 and 32 px with the expected size and frame count and is
  byte-identical across two runs; the requirement check with and without the required roles;
  the slots' defaults from the `ranch` pack.

**Done when**
* The top-down sample (a plain RPG pack) chosen as a farm passes the requirement check with
  notes only.

## T17.03 — The calendar: time, days and seasons

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/world/calendar.gd` (new),
`godot_templates/addons/rpg_runtime/world/day_night.gd` (follows the calendar when there is
one), `godot_templates/addons/rpg_runtime/core/save_system.gd` (a `calendar` key),
`rpggen/core/calendar_math.py` (new, the same arithmetic for the planner and the tests),
`godot_templates/tests/unit/test_calendar.gd` (new), `docs/spec/02_SCHEMAS.md`

The day and night light of T12.62 runs on a clock of its own that nothing else can ask. A farm
needs one time for everything: the light, what grows, when a shop is open, where a person is.

**Spec**
* `RpgCalendar` (an autoload-free node under the game state, as the arcade parts are): the
  minute of the day, the day of the season, the season (spring, summer, autumn, winter), the
  year. A day runs from 6:00 to 2:00; a game minute is `minute_s` real seconds (0.7 by
  default, so a day is about 14 minutes; an option). Time stands still in menus, dialogue and
  cutscenes, and indoors when the option says so.
* Signals: `minute_passed`, `hour_passed`, `day_ended(day)`, `day_began(day)`,
  `season_changed(season)`. `end_day()` is called by sleeping (T17.08) and by the clock at
  2:00; everything that happens overnight listens to `day_ended` in a fixed order (crops, then
  animals, then the shop's stock, then the weather of the new day), so a day is the same for
  the same seed.
* `days_per_season` (28 by default; 7 and 14 are options for a shorter game).
* `RpgDayNight` takes its time from the calendar when the game has one and keeps its own
  clock otherwise, so the light of an older game is what it was.
* Saved as `calendar: {minute, day, season, year}`, an optional key (`save_version` stays 1).
* `calendar_math.py` and the GDScript agree on a table of cases (the shared-arithmetic rule
  of M16): the date after N days, the season of a day, the minute after a time span.

**Tests**
* GDScript: a day ends at 2:00 and by `end_day`, with the listeners in their order; 28 days
  are a season and four seasons a year; time stands still in a menu; the light follows the
  calendar; the save round-trips; a game without a calendar has the light of T12.62.
* Python: `calendar_math` matches the GDScript over the table.

**Done when**
* A test scene shows the light going through a day and the date going through a year.

---

# Part B — Farm and life sim

## T17.04 — The farmer, tools and energy

**Depends on:** T17.02, T17.03
**Files:** `godot_templates/addons/rpg_runtime/archetypes/farm/` (new: `farm_mode.gd`,
`farmer.gd`, `tool.gd`, `tools/hoe.gd`, `tools/watering_can.gd`, `tools/sickle.gd`,
`tools/axe.gd`, `hotbar.gd`, `energy.gd`, `farm_strings.gd`, `ui/`),
`godot_templates/builder/recipes/farm/` (new: `farm_build.gd`, `farmer_recipe.gd`),
`rpggen/core/config.py` (`default_input("farm")`, `starter_map_defaults("farm")`),
`godot_templates/tests/unit/test_farmer.gd` (new)

**Spec**
* `RpgFarmer` extends the top-down player the turn-based and action kinds share (walk in four
  or eight directions, interaction, doors). It adds the **tile ahead**: the cell in front of
  the farmer, shown by a frame on the ground, which a tool acts on.
* **Tools** (`RpgFarmTool`: a name, an energy cost, what cells it acts on, a use time): the
  hoe tills grass or dirt into soil, the watering can waters soil (and is filled at water),
  the sickle cuts a ripe crop or grass, the axe clears a stump or a branch. The use animation
  is the sheet's own (`hoe`, `water`, `sickle`, `axe`, by name) when it has one, else the
  attack or the idle frame with the tool's icon over the farmer's hands.
* **The hotbar** (`RpgHotbar`): ten slots of the inventory that exists (T6), one of them held;
  `next_item`, `prev_item` and the number keys choose. Seeds, produce and tools are items;
  `use` uses what is held on the tile ahead (a tool works, a seed is planted, food is eaten).
* **Energy** (`RpgEnergy`): a maximum (100), spent by tools, restored by food and by sleep. At
  zero the farmer walks slowly and cannot use a tool; staying up to 2:00 or working at zero
  ends the day with less energy the next morning (T17.08).
* `default_input("farm")`: move, `use` (Space / J / A), `interact` (E / X), `next_item` and
  `prev_item` (Q and R / the shoulder buttons), the number keys, `menu`, pause.
* Combat is off by default for the kind (the T13.06 dependencies); it stays available: with
  it the farm has the action RPG's enemies in a cave map.

**Tests**
* GDScript: the tile ahead for four facings; each tool changes the cells it may and no other;
  a tool costs its energy and none without effect; the hotbar holds and cycles; at zero
  energy a tool does nothing.
* Python: the recipe writes the farmer for the `ranch` pack and for the top-down sample.

**Done when**
* The farmer walks a test field, tills it and waters it.

## T17.05 — Soil and crops

**Depends on:** T17.04
**Files:** `archetypes/farm/field.gd`, `archetypes/farm/crop.gd`, `archetypes/farm/crop_data.gd`,
`recipes/farm/crop_recipes.gd`, `recipes/farm/field_recipe.gd`, `rpggen/core/crop_plan.py`
(new, pure Python), `game/data/crops.json` (written once), `tests/unit/test_crop_plan.py` (new),
`godot_templates/tests/unit/test_field.gd` (new)

**Spec**
* **The field** (`RpgField`, a node of a farm map): the state of every cell that was worked
  (tilled, watered, what grows there and at which stage), kept as data and painted onto two
  layers of the map (`Soil` under the crops, the crops as scenes that Y-sort with the
  farmer). Tilled and watered soil are the pack's `soil` and `watered` terrains (so a field
  has proper edges), or the drawn tiles.
* **A crop** (`crops.json`, one entry a crop): its seed item, its produce item, the seasons it
  grows in, the days it takes, whether it grows again after a harvest (and after how many
  days), and its prices. The stages shown are the frames of its growth strip, spread evenly
  over its days.
* **A night** (`day_ended`): a watered crop grows a day, an unwatered one does not; soil dries;
  tilled soil with nothing on it may return to grass after some days; a crop out of its
  season withers when the season changes. Rain waters every cell (T17.11).
* **Harvest:** `use` or `interact` on a ripe crop puts its produce into the inventory; a full
  inventory leaves it standing.
* `crop_plan.plan(options, seed, facts)`: which crops the game has. Every `CROP` asset of the
  packs is a crop; its days come from its stage count and the difficulty, its seasons are
  shared out so that every season has at least two crops, its prices from its days. A pack
  with no crop gets the three drawn ones. The plan is stored (`rpggen/world_plan.json`,
  section `farm`) and reused; a crop added to the packs later is added to it, and
  `game/data/crops.json` is the user's once it exists.

**Tests**
* GDScript: a seed planted, watered every day, is ripe after its days and not before; a day
  without water does not count; a crop out of season withers; a crop that grows again does;
  the field round-trips through a save.
* Python: the plan is the same for the same seed; every season has two crops; the JSON fits
  its schema.

**Done when**
* A crop can be grown from seed to harvest in a test field over as many nights as its entry says.

## T17.06 — The farm plan and the farm recipe

**Depends on:** T17.05
**Files:** `rpggen/core/farm_plan.py` (new, pure Python), `rpggen/core/world_plan.py` (a `farm`
section), `recipes/farm/farm_map_recipe.gd`, `rpggen/core/map_preview.py` (a farm picture),
`tests/unit/test_farm_plan.py` (new)

**Spec**
* The world of a farm is **two maps or more**: the farm and the village. The village is the
  starter map of the top-down kinds (its planner and recipe, unchanged) with the shop and the
  houses of the people; the farm is planned here.
* `farm_plan.plan(options, seed, facts)`: on a field of `size` (small, medium, large): the
  farmhouse with its interior (the bed), a plot of tillable ground of a size the options
  give, a pond or a well to fill the can, the shipping bin beside the house, a coop and a
  barn when the options have animals (each a building with an interior and a fenced yard),
  scattered branches, stumps and grass to clear, trees and scenery at the edges, and the way
  to the village. What can be tilled is marked in the plan and written as the tile's custom
  data, not guessed from its art.
* **Workable** (`VAL-031`): the farmer can walk from the door of the house to the plot, the
  water, the bin, every yard and the way out; the plot has at least twelve cells. A plan that
  fails is planned again with the next seed, and the report says so.
* Stored and reused like every plan (the rule of T14.06); *Added maps* (a beach, a forest, a
  cave) grows the world through the areas of T13.20.
* The Options preview (T17.16) draws the farm from the plan.

**Tests**
* Deterministic plans; the check rejects a hand-made farm with a walled-in plot; the recipe
  paints the `ranch` and the top-down sample packs; the preview picture is drawn.

**Done when**
* A farm and its village are generated, and the farmer can walk from the bed to the plot, the
  bin and the shop.

## T17.07 — Animals

**Depends on:** T17.06
**Files:** `archetypes/farm/animal.gd`, `archetypes/farm/animal_house.gd`,
`recipes/farm/animal_recipes.gd`, `game/data/animals.json`

**Spec**
* `RpgFarmAnimal`: a kind (from its tags: a hen lives in the coop, a cow in the barn), a
  name, friendship, whether it was fed and petted today. It wanders its yard by day when the
  weather allows and is inside at night (the `sleep` animation when it has one).
* **Care:** feed in the trough of its house (an item, hay or grain, from the shop or from cut
  grass), `interact` to pet. A fed animal gives its product in the morning (an egg in the
  coop, milk by `interact` with a pail); friendship raises the product's quality and price;
  an animal that is not fed gives nothing and loses friendship. Animals do not die.
* Animals are bought at the shop (T17.08) while their house has room; `animals` (none, a
  coop, a coop and a barn) is an option.
* The `ANIMAL` assets of the packs are shared out by tag; colour variants of one animal are
  offered when it is bought. Without any, the drawn hen.

**Tests**
* GDScript: a fed hen lays an egg overnight and an unfed one does not; friendship rises with
  petting and falls with hunger; an animal is inside at night and in the rain; the state
  round-trips through a save.

**Done when**
* A hen can be bought, kept for a week and its eggs sold.

## T17.08 — Money: the shipping bin, the shop, the end of a day

**Depends on:** T17.06
**Files:** `archetypes/farm/shipping_bin.gd`, `archetypes/farm/day_end.gd`,
`archetypes/farm/ui/day_summary.gd`, `recipes/farm/shop_recipe.gd`

**Spec**
* **The shipping bin:** items put into it are sold overnight at their price; the morning
  begins with a summary (what was sold, what it earned, the total). Selling at the shop's
  counter pays at once (the shop of T12.46 with the quantities of T13.11).
* **The shop** sells the seeds of the season, feed, animals and the tools' upgrades, is open
  by the calendar (9:00 to 17:00, closed one day a week), and says so on its door.
* **Sleeping** (`interact` with the bed): the day ends, the game saves into the autosave slot
  and the slot the player chose, energy is full in the morning. **Staying up to 2:00** ends
  the day where the farmer stands: it wakes in bed with half its energy and a tenth of its
  money gone (an option turns the loss off).
* A new game starts with a little money, a hoe, a can and fifteen seeds of the first crop.

**Tests**
* GDScript: what is in the bin is paid for overnight and listed in the summary; the shop's
  stock changes with the season and it is closed outside its hours; sleeping saves and fills
  the energy; passing out costs what the option says.

**Done when**
* Seeds are bought, grown, shipped and paid for over a week.

## T17.09 — People: schedules, gifts and friendship

**Depends on:** T17.03, T17.06
**Files:** `godot_templates/addons/rpg_runtime/actors/schedule.gd` (new, shared),
`archetypes/farm/friendship.gd`, `archetypes/farm/ui/people_page.gd`,
`recipes/farm/people_recipes.gd`, `game/data/people.json`, `rpggen/core/people_plan.py` (new)

The runtime has no schedules: an NPC stands where its map put it. This card adds them as a
shared part, off in every project that has no calendar.

**Spec**
* `RpgSchedule`: a list of (from which hour, on which days or in which weather, the map, the
  place). An NPC walks to its place on the navigation of its map; one whose place is on
  another map leaves through the door and is there when the player comes. Schedules are
  resolved from the calendar when a map is entered, so nobody has to be simulated off screen.
* `people_plan.plan`: every `NPC` asset is a person with a house in the village, a job when
  the map has a shop, and a schedule built from a few patterns (at home, at work, the square,
  the pond, indoors when it rains). Stored and reused; `game/data/people.json` is the user's.
* **Friendship** (`RpgFriendship`): points a person, shown as hearts (ten of 250). Talking
  once a day gives a few; a **gift** (the held item, `interact`, twice a week) gives by taste:
  each person loves, likes or dislikes some items (in the plan, from the items the game has).
  Dialogue lines are chosen by hearts with the conditions the dialogue system has (a
  `friendship:<id>>=4` atom is added).
* A **People** page of the pause menu lists who was met, their hearts and what is known of
  their taste.
* Marriage, children, festivals and birthdays are **not** in 1.5.0 (Part E).

**Tests**
* GDScript: an NPC is at the place its schedule gives for 8:00, 12:00 and 20:00 and on a rainy
  day; one whose place is on another map is not on this one; a loved gift gives more than a
  liked one and a third gift in a week none; a line that needs four hearts is said at four.
* Python: the plan gives every person a house and a schedule that names places that exist.

**Done when**
* A villager is found at the shop by day and at home by night, and has a new line at two hearts.

## T17.10 — Fishing and foraging

**Depends on:** T17.08
**Files:** `archetypes/farm/fishing.gd`, `archetypes/farm/ui/fishing_bar.gd`,
`archetypes/farm/forage.gd`, `recipes/farm/forage_recipe.gd`

**Spec**
* **Foraging:** places in the plan (the edges of the farm, added maps) where an item of the
  season lies in the morning; picked up by `interact`.
* **Fishing** (a feature, on when the packs have water): the rod on a water cell casts; after
  a wait a bite; a bar that the `use` button holds over a moving mark until the fish is
  caught. Which fish by the season, the time and the water. `FISH` art is `ITEM` tagged
  `fish`, else a drawn one.
* Both are small on purpose: they are the two cheapest things that make a day more than
  watering.

**Tests**
* GDScript: the forage of a morning for a seed and a season; a cast, a bite and a catch with
  a scripted button; a miss.

**Done when**
* A fish is caught and a forage item found and both are sold.

## T17.11 — Weather and the HUD

**Depends on:** T17.05, T17.08
**Files:** `archetypes/farm/weather.gd`, `archetypes/farm/ui/farm_hud.gd`,
`recipes/farm/hud_recipe.gd`, `godot_templates/project_files/README.farm.md` (new)

**Spec**
* **Weather** is decided at `day_ended` for the next day from the seed and the season (sun,
  rain, a storm in summer, snow in winter): rain waters the field and keeps animals in, an
  overlay (`weather` art or the drawn rain) falls over outdoor maps, and the light is duller.
  Tomorrow's weather can be read on a sign by the house.
* **The HUD:** the time, the day and the season with the weather; the money; the energy as a
  bar; the hotbar with the held slot; a toast for a harvest and a sale.
* **Seasons** change the ground and the trees when the packs have seasonal variants (T17.01),
  and the music.
* The generated README has the kind's section: the controls, a day, crops and how to add one
  (`crops.json`), animals, people and their schedules (`people.json`), where the plan is.

**Tests**
* GDScript: the weather of thirty days is the same for the same seed; rain waters; the HUD
  shows the calendar, the money and the energy; the README is written.

**Done when**
* The farm is a whole game behind `FARM_AVAILABLE`: a season can be played from the first
  morning to the last night.

---

# Part C — Isometric tiles

## T17.12 — Isometric packs: reading one picture a tile

**Depends on:** nothing
**Files:** `rpggen/core/adapters/isometric.py` (new: the adapter of a pack of single tiles),
`rpggen/core/analyzer/isometric.py` (new: the footprint), `rpggen/core/adapters/kenney_atlas.py`
(new: the `<TextureAtlas>` XML), `rpggen/core/adapters/sequences.py` (turns are not frames),
`rpggen/core/adapters/naming.py`, `rpggen/core/classifier.py`, `rpggen/core/pack_sniff.py`,
`rpggen/core/inventory.py`, `rpggen/core/catalog.py`, `rpggen/schema/catalog.schema.json`,
`docs/spec/02_SCHEMAS.md`, `tests/unit/test_isometric.py` (new),
`tools/make_synthetic_packs.py` (an `iso_tiles` and an `iso_miniature` pack)

The packs are the table above. They are CC0, so their pictures may be opened to measure
them; they are still not copied into the repository: the synthetic packs are drawn by the
tool in their shapes and names.

**Spec**
* **A pack of single tiles.** A folder whose pictures are one size (or one width), each with
  see-through corners and its opaque part resting on the bottom, is a pack of isometric tiles
  when its words (`isometric`, `iso`) or its text file say so, or when the footprints that
  are measured agree. Every picture is one **tile asset**: `projection: isometric`,
  `canvas: [w, h]`, `footprint: [w, h]` (the diamond the tile stands on) and `rise` (how far
  the picture goes above its diamond: a flat tile, a block, a tree).
* **The footprint, in this order:** the pack's own words (`Tile information.txt`: *Tile size*;
  `Tiled (settings).txt`: *Map tile size*, which wins when both are there, since it is what a
  map is laid out by); else measured: the width is the opaque width of the ground tiles, and
  the height the one at which the flat tiles of the pack meet without a gap, found by laying
  two of them side by side at each candidate height and counting open and doubled pixels
  along the seam. **Never assumed to be half the width**: the listed packs have 180 x 104,
  180 x 115, 180 x 125, 120 x 98 and 120 x 74. Whether *Tile size* in those text files is the
  diamond or the diamond with the block's side under it is not known from the text alone:
  the card begins by laying two tiles of *Medieval Town* and of *Modular Roads* at the size
  their file gives and at the measured one, and the notes say which the words mean. A pack
  where no height fits is `TILE-010`, a warning, and its pictures stay pictures.
* **One width, several heights** (the older packs: 132 x 83, 132 x 99, 132 x 131): the
  footprint is the pack's, the picture's own height above it is its rise. A width that is
  one pixel off (133) is the same tile.
* **Turns.** A set of names that differ only in a last `_0`–`_3` or `_0`–`_7`, or in a last
  compass word (`_N`, `_E`, `_S`, `_W`, and `_NE` … for eight), all of one size, is **one
  thing turned**, not an animation: the sequence reader leaves it alone. For a tile the turns
  are `turn: 0..3` of one asset (one card in the audit with a *Turns (4)* row, as colour
  variants have); for a vehicle or a boat they are its headings (`headings: 4 | 8`,
  `heading_order` from the letters), which T16.02's rotation sheets already are, here as
  files. A last `U` or `D` on a heading (`_NEU`) is the same heading on a slope: kept as a
  tag, unused in 1.5.0.
* **Sides in a name.** `…CornerES`, `…EW`, `…NS`, a lone `…E` after a ground word
  (`beachE`, `waterSW`, `bridgeHighEW`) say which of the diamond's four sides the tile joins
  on: recorded as `joins: [..]`, which the planner uses to choose the piece of a road, a
  shore or a wall (T17.14). They are compass words only when the stem without them is shared
  by several files; `Blue`, `House` and `News` are not sides.
* **Two views of one model.** Sibling folders `Isometric` and `Angle` with the same names:
  `Isometric` is used and `Angle` is *unused* with the reason on its cards, like the engine
  layouts of T16.21. *Axonometric* in a pack's name is not isometric: its pictures are read
  as pictures.
* **The pack is a zip in its folder.** A folder that holds one archive and nothing but
  previews beside it (`Preview.png`, `Sample.png`, `Samples/`, `Information.png`, `.url`
  files) is opened as that archive; the previews are left out by the names the inventory
  already knows, to which `sample`, `samples` and `information` are added.
* **An atlas beside its pictures.** A `<TextureAtlas>` XML with `<SubTexture>` entries is
  read as the rectangles of its sheet. When the loose pictures of the same names are in the
  pack, they are used and the sheet is *unused* (the art is there twice); a pack with only
  the sheet is read through the XML.
* **Objects.** A tile with a rise is still a tile when it fills its diamond (a block, a
  wall); a picture whose base is narrower than the diamond (a tree, a sign, a lamp) is an
  object standing on one. How many diamonds a wide object stands on is guessed from its base
  and open to the audit's editor, which draws the diamond grid.
* **Characters.** None of the listed packs has one. Direction words `ne`, `nw`, `se`, `sw` on
  a character sheet are read as the diagonals of T12.50's eight, for packs that do.
* **Pack view** gains `isometric`; the pack card says *Isometric tiles, 180 x 104*. Isometric
  and square ground mapped in one project is `TILE-011`.
* Two synthetic packs: `iso_tiles` (in the manner of *Modular Roads* and *Nature*: 24 tiles
  turned four ways in one canvas with a `Tile information.txt`, a tree and a house as
  objects, an atlas of the same pictures, a preview) and `iso_miniature` (a zip in a folder
  beside a preview: `Isometric/` and `Angle/` with `_N` to `_W` names, a corn plant, and a car
  in eight headings by letters).

**Tests**
* The footprint from each text file, and measured for packs drawn at 2:1, at 30 degrees and
  at 180 x 125; a pack that fits none (`TILE-010`); one width with three heights; turns by
  number and by letter are one asset and no animation, while `walk_0` to `walk_3` still is
  one; sides in names, and three names that end in letters and are not sides; `Angle`
  unused; the zip in a folder; the atlas alone and beside its pictures; the two goldens; no
  other golden moves; the corpus is unchanged.

**Done when**
* The two synthetic packs are catalogued without an edit, and on the owner's machine the 23
  packs are: each of the seven one-size packs as its tiles with the footprint its text file
  gives and four turns a tile; the three older packs with one footprint and their rises; the
  road packs with their joins; the five zipped packs opened, `Isometric` used; the vehicles as
  cars in eight headings with their colours as variants; *Axonometric Blocks* as pictures.

## T17.13 — The isometric TileSet

**Depends on:** T17.12
**Files:** `godot_templates/builder/recipes/tileset_recipe.gd`,
`godot_templates/builder/lib/iso_tileset.gd` (new, as `side_tileset.gd` is),
`docs/godot_api_verified.md`, `rpggen/core/config.py` (`projection`),
`rpggen/schema/config.schema.json`, `godot_templates/tests/unit/test_iso_tileset.gd` (new)

**Spec**
* A project with `projection: isometric` gets a TileSet whose tiles are diamonds: Godot's
  isometric tile shape with the layout and the offset axis that fit how the planner counts
  cells, and the tile size the pack's footprint (which is whatever T17.12 found: 180 x 104,
  not a fixed 2:1). **Each of these properties and its values is verified in
  `docs/godot_api_verified.md` first.**
* **The tiles are single pictures**, so the recipe does not cut a sheet: rpggen packs the
  pictures of a pack into atlas pictures in the work folder (as it writes a terrain atlas),
  each in a cell of the pack's canvas, deterministically and in the order of their ids, so
  that an added tile gets a new cell and no painted cell moves on regeneration (the rule of
  the TileSet merge, M5). Every tile's texture origin puts its diamond on the grid: the tile
  rests on the bottom of its canvas, so the origin follows from the canvas, the footprint and
  nothing else. The three cases to verify: a flat tile, a block with a rise, and a tree three
  times as high as its diamond.
* **Turns** of a tile are alternative tiles of one source, so a map can turn a piece without
  another asset, and the planner asks for *this piece, turned to join east and south*.
* **Packs of different footprints** (180 x 104 and 120 x 74) cannot share a map: the project
  has the footprint of its ground, and tiles of another are objects or are left out with a
  note, as a pack of another tile size is today.
* **Collision** polygons are the diamond (full) or its halves and quarters, from the
  collision profiles that exist; **terrain** sets work on the diamond's four sides (the peering
  bits of an isometric tile set) when a pack has such a set; the listed packs have none, and
  their ground joins by whole tiles chosen from their `joins`.
* The top-down TileSet of every other project is byte for byte what it was (the recipe
  changes its output only for the option, as the side-view layers did in M14).

**Tests**
* GDScript: the TileSet of the `iso` pack has the shape, the size and the origins; a painted
  cell lies where the map says; the collision of a wall cell is its diamond; a terrain of two
  grounds joins.
* Python: the config refuses `projection: isometric` for a kind that does not have it and a
  change of projection in a generated project.

**Done when**
* A map painted by a test with the `iso` pack looks right in the editor: no seams, no tile
  off its diamond.

## T17.14 — Isometric maps and actors

**Depends on:** T17.13
**Files:** `rpggen/core/world_plan.py` (the plans are unchanged; a `projection` is carried),
`godot_templates/builder/recipes/starter_map_recipe.gd`, `interior_recipe.gd`,
`second_map_recipe.gd`, `object_scenes_recipe.gd`,
`godot_templates/addons/rpg_runtime/world/iso.gd` (new: cell to screen and back),
`godot_templates/addons/rpg_runtime/actors/` (movement), `rpggen/core/iso_math.py` (new, the same
arithmetic), `rpggen/core/map_preview.py`, `godot_templates/tests/unit/test_iso.gd` (new)

**Spec**
* **The plan does not change.** The starter map, the world of areas, interiors and the farm
  are planned on a grid of cells as today; only the painting and the positions differ. So
  every planner, its checks and its tests hold for both projections.
* **`RpgIso`** and `iso_math.py`: cell to screen position, screen to cell, the depth of a
  cell, one table of cases between the two languages.
* **Roads, shores and walls** are laid from the pieces' `joins` (T17.12): for every cell the
  planner knows which of its four neighbours are the same ground, and the recipe takes the
  piece and the turn that joins exactly those sides; a pack without the piece for a case gets
  the nearest and a note. This is what terrains do for a top-down pack.
* **People.** A character drawn from the front or for a top-down game stands on an isometric
  map as it is (the usual look of such games); the packs that were listed have no character,
  so the hero, a villager and an enemy of the drawn kit (`iso_kit.py`, `ASSET-031`) stand in
  when no other pack of the project has them.
* **Movement.** An actor moves in screen space; with an isometric map *up* on the pad is up
  on the screen (the genre's usual choice) and an option `iso_controls: screen | grid` makes
  the four directions follow the diamond's axes instead. The four or eight facing directions
  choose the sheet's diagonal animations when it has them, else the nearest of its four.
  Grid-bound movement (the turn-based kind's step by cells) steps along the diamond's axes.
* **Y-sort** follows the depth of the diamond: objects and actors sort by the screen y of
  their footprint's nearest corner; an object several diamonds wide (a house) is split for
  sorting where an actor can stand behind part of it, or blocks the cells behind it when it
  cannot be split (the plan knows its footprint).
* **Objects, doors, interiors, the minimap, lighting, navigation** take their positions from
  `RpgIso`; the navigation polygon of a map is built from the diamonds that can be walked. A
  door is on the side of a building that faces the camera.
* **The previews** of the wizard draw the planned map as diamonds for an isometric project.
* The option is offered for `turn_based`, `arpg` and `farm`. The metroidvania and the two
  side-view and scrolling arcade kinds have no isometric view.

**Tests**
* GDScript: the table of cases; an actor walks round a house and is drawn behind and in
  front of it at the right moments; a door leads in and out; grid movement steps on diamonds;
  navigation finds a way; both control options.
* Python: `iso_math` matches the GDScript; the preview picture is drawn.

**Done when**
* The `iso` pack makes a turn-based game and an action RPG whose shared smoke sequence passes
  unchanged (the steps ask the map for positions, not the screen).

## T17.15 — Isometric racing

**Depends on:** T17.14
**Files:** `godot_templates/builder/recipes/racing/track_recipe.gd`,
`archetypes/racing/heading_sprite.gd`, `archetypes/racing/race_camera.gd`,
`archetypes/racing/ui/race_minimap.gd`, `godot_templates/tests/unit/test_iso_racing.gd` (new)

RC Pro-Am is seen at an angle; M16 made the view from above and left this.

**Spec**
* The track plan (T16.13) is unchanged: a loop on a grid, its surfaces, checkpoints and
  waypoints. With `projection: isometric` the recipe paints it with isometric road tiles and
  every position (the grid, checkpoints, waypoints, pickups, barriers) goes through `RpgIso`.
* **The car drives on the plan's flat grid** and is drawn on the screen through `RpgIso`: the
  physics of `car_math` does not know the view, so the table of cases holds and a rival
  drives the same lap. What the player sees is squeezed in height, as the genre has it.
* **Headings:** a car in eight headings as eight files (*Tiles Vehicles*: `taxi_N.png` …
  `taxi_NW.png`, T17.12) is the picture of the isometric car, and its other colours and
  models the rivals; a rotation sheet drawn from straight above is used too and looks flat,
  which the Mapping page says. `HeadingSprite` picks the picture from the heading as it
  appears on the screen. Eight headings turn in steps of 45 degrees, which shows; the car
  still steers smoothly underneath.
* **The road** is laid from the road pieces' `joins` as T17.14 lays any road; the track
  plan's corners are the corner pieces.
* Relative steering is the default; with absolute steering the stick is a direction on the
  screen.
* The map of the track in the corner stays the plan from above.

**Tests**
* GDScript: a lap of the planned track by the smoke's driver in the isometric view, through
  every checkpoint; the frame of the picture for a heading on the screen; the camera leads
  the car on the screen.

**Done when**
* The racing sample's plan is driven lap after lap on isometric tiles.

---

# Part D — The wizard, the samples, the gate

## T17.16 — Wizard: the Farm card, the projection, options and previews

**Depends on:** T17.11, T17.14
**Files:** `rpggen/gui/pages/archetype_page.py`, `rpggen/gui/widgets/options_sections.py`
(a `FarmBox`), `rpggen/gui/widgets/options_summary.py`, `rpggen/core/options.py`,
`rpggen/gui/models/options_model.py`, `tests/gui/test_archetype_page.py`,
`tests/gui/test_options_page.py`, `tests/gui/test_layout_fit.py`

**Spec**
* **Seven cards** on the Archetype page. The grid of T16.16 (two rows of three) becomes rows
  of four at 1280 px and wider and stays three a row below that with a third row that
  scrolls; the one column of a narrow window is unchanged. The Farm card has its `MockScreen`
  drawing (a farmer by a row of crops, a house, the clock), its text, its controls line and
  its flow (`Till → Plant → Water → Harvest → Sell`).
* **The projection.** A pack that looks isometric shows *This pack is isometric* under the
  cards, and the kinds that have the view get a **View** choice (*From above*, *Isometric*)
  on their card's Options box; it is chosen for the pack by default, cannot be set to
  isometric without isometric ground, and is fixed once the project exists.
* **Options:** a `FarmBox`: the farm's size and the plot's, animals, days a season, the
  length of a day, fishing, the loss for passing out, the starting money, combat (with its
  cave), and *Added maps*. The preview is the planned farm with its plot, water, buildings,
  yards and the way to the village; the summary names the kind and its numbers (*Farm · 28
  days a season · a coop · 6 crops*).
* **Presets:** *Cosy* (long days, no loss for passing out, more starting money) and *Short
  year* (7 days a season).
* `rpggen generate --archetype farm` and `--projection isometric`; a dry run describes the
  plan (*a farm of 40 x 30 with a plot of 96 cells, 6 crops, 5 people*).

**Tests**
* The cards render at three sizes without clipping; the farm's box and roles; the view choice
  appears only with isometric ground and is fixed after a generation; the preview draws from
  a plan in both views; the presets; the CLI accepts the keys and rejects an unknown one
  with exit 2.

**Done when**
* The farm and the isometric view can be chosen, configured and previewed at 880 x 540.

## T17.17 — Two sample packs and *Try the sample*

**Depends on:** T17.16
**Files:** `tools/build_sample_pack.py`, `sample_pack_farm/`, `sample_pack_iso/` (new, CC0),
`rpggen/gui/models/project_model.py` (`SAMPLES`), `tests/golden/`, `tests/gui/test_sample_pack.py`

**Spec**
* *Green acre* (`--kind farm`): a farmer with walk and four tool strips, four crops with
  growth strips, soil and watered soil, grass in four seasons, a hen and a cow, tools, a
  house, a coop, a bin, a fence, three villagers, a rain overlay, four loops and eight sounds.
* *Stone isle* (`--kind iso`): one picture a tile in one canvas with its text file, as the
  real packs are: grass and stone ground, water with shore pieces named by their sides, road
  pieces, a block, walls, a house of four diamonds, trees, each turned four ways; a hero and
  two villagers, a slime, a chest. It sets the turn-based kind with the isometric view.
* Each under 200 KB with a licence file and its profile; goldens for both; no older golden
  moves. *Try the sample* lists seven.

**Tests**
* Each sample is catalogued as its golden says and, with its profile, has nothing missing;
  the welcome menu lists seven and each lands on its kind and its view.

**Done when**
* Each sample generates and plays with no note but `ASSET-031` where it is minimal on purpose.

## T17.18 — Smoke sequences and integration tests

**Depends on:** T17.17
**Files:** `godot_templates/builder/smoke/smoke_steps_farm.gd` (new),
`rpggen/core/orchestrator.py` (`OWN_SMOKE_STEPS`), `tests/integration/test_m17_farm.py`,
`tests/integration/test_m17_isometric.py` (new), `tests/perf/test_perf.py`,
`.github/workflows/ci.yml`, `pyproject.toml` (markers)

**Spec**
* **The farm's own sequence** (`SMOKE-013`): title → new game → wake in the house → till,
  plant and water a cell with the real actions → sleep → the crop is a stage further → the
  nights to ripeness (the calendar is advanced, each night run in full) → harvest → ship →
  the morning's summary and the money → buy seeds at the shop in its hours → find a villager
  where the schedule says at two times of day → give a gift → a rainy day waters the field →
  the season changes and a crop out of season withers → save, load, the field and the date are
  what they were. Each step asserts the cells, counts and dates it passes.
* **Isometric** has no sequence of its own: the shared one, the action RPG's and the racing
  one run over the isometric sample and must pass as they are. A step that fails only there
  is a step that asked the screen where it should have asked the map, and is mended.
* Integration tests of both (markers `farm` and `isometric`, a CI job each), regeneration
  (nothing moves on a repeat; a crop added to the pack is added to the plan; the projection
  cannot be changed), determinism, the JSON results against the schemas.
* Perf: the two samples under 120 s each; the GUI integration test of each wizard path.

**Tests**
* They are the card.

**Done when**
* The two jobs are green on Windows and Ubuntu.

## T17.19 — Documentation, screenshots and changelogs

**Depends on:** T17.18
**Files:** `docs/user_guide.md` (a section for the farm, one for the isometric view),
`README.md`, `CHANGELOG.md`, `godot_templates/addons/rpg_runtime/CHANGELOG.md`,
`docs/status.md`, `docs/spec/00_START_HERE.md`, `docs/architecture.md` and its copy,
`docs/images/`, `tools/make_doc_screenshots.py`

**Done when**
* A reader of the guide can make a farm from its sample and from a pack of their own, and an
  isometric game from an isometric pack.

## T17.20 — Gate (1.5.0)

**Depends on:** T17.19

* CI green on every job, both PySide6 legs, perf within the ceilings; the frozen smoke test
  on three systems (the two samples and the drawn kit are in the bundle).
* The upgrade test over a 1.0 to 1.4 project of each older kind: no prompt, nothing under
  `game/` changes, byte-identical TileSets and sprite frames.
* The corpus unchanged on all four measures.
* Manual rows, by the owner: play *Green acre* through a season with a gamepad (the feel of
  the tile ahead, the length of a day, whether the money and the energy are fair); play
  *Stone isle* as a turn-based game and as an action RPG with both control options; drive
  *Dirt cup* in the isometric view with the cars of *Tiles Vehicles*; generate a farm from
  *Super Retro Ranch* and from a plain RPG pack and compare the notes; generate an isometric
  game from *Medieval Town*, *Nature* and *Modular Roads* together, and an isometric farm
  from *Miniature Farm*; a 300-asset farming pack through the audit.
* Then flip the two flags on and tag `v1.5.0`.

---

# Part E — Not in this milestone

**Left out of the farm on purpose**, to keep 1.5.0 a release and not a year: children, a
museum or a community goal, mining floors beyond the one cave, cooking and crafting recipes,
tool upgrades beyond the shop's two, a greenhouse, multiplayer. (Marriage, festivals and
birthdays, and the cave were on this list and are cards of Part F since 2026-10-13.) Each is an
addition to data the farm already has (`people.json`, `crops.json`, the calendar's signals)
and can be a card of a later milestone.

**The other kinds sketched in M16, Part F**, with what each reuses, stay for a later milestone
in the order that was recommended there; nothing here builds toward them except where noted.

| Kind | Key | In the line of | Size | What M17 gives it |
|------|-----|----------------|:----:|-------------------|
| Tower defense | `tower_defense` | Kingdom Rush | M | the isometric view; the owner has *Isometric Tower Defense* (472 pictures) |
| Beat 'em up | `brawler` | Streets of Rage, River City Ransom | L | nothing |
| Dungeon run | `dungeon_run` | The Binding of Isaac, the dungeons of Zelda | L | the isometric view would be an option of it |
| Tactics | `tactics` | Fire Emblem, Advance Wars | XL | the isometric view (the genre's usual one) and `RpgIso`'s cell arithmetic |
| Twin-stick arena | `arena` | Smash TV | M (after `dungeon_run`) | nothing |

---

# Part F — What the owner asked for after the cards (2026-10-13)

When T17.01 to T17.20 were implemented, the status page listed what real packs still showed
and what Part E had left out on purpose. The owner's answer was that all of it is to be
addressed. These cards are that list. They are part of M17 and of release 1.5.0; the gate
(T17.20) is closed after them. The ground rules above apply to each, and so does what the
milestone learnt: a card is not done until its game was looked at in a rendered picture, the
full suites ran with nothing else using Godot, and the slow GUI tests were among them.

## T17.21 — Real packs: cars by their pictures, the buildings' diamond, wall pieces, characters in eight facings

**Depends on:** T17.12
**Files:** `rpggen/core/adapters/isometric.py`, `rpggen/core/analyzer/isometric.py`,
`rpggen/core/adapters/naming.py`, `rpggen/core/classifier.py`, `rpggen/core/catalog.py`,
`rpggen/core/mapping.py`, the catalog and profile schemas, `tests/unit/test_isometric.py`

**Spec**
* **A heading from the picture.** The 480 civilian cars of *Isometric Tiles Vehicles* are
  sixteen files a car numbered in no order. A set of views of one object is ordered round
  the compass by measuring the pictures; a set that cannot be ordered with confidence stays
  unread with the reason on its card. The colours of a model (its folder) are variants of one
  car, and slope views are set aside. No car of the pack is a decoration.
* **The diamond of *Isometric Tiles Buildings***, measured at 99 x 50 from its small pieces, is
  found from the evidence the pack has, and beside *Tiles Base* the project's diamond is its
  ground's.
* **Wall pieces.** A thin wall segment on the edge of a diamond (*Medieval Town* has sixty with
  the role and the map's edge got none) is catalogued so that the builder can lay it along an
  edge: which side of its diamond it stands on, by its turn.
* **The default ground** of an isometric project is a tile whose name or surface says grass,
  ground or dirt before a paving, as the race's field already chooses.
* **Characters in eight facings** by a number before the action (`Male_3_Run2.png`, the
  *Miniature* packs) are one character with its animations.
* The stray *looks like a racing pack* marks on isometric packs end.

**Done when**
* The table of the 23 packs is made again, and every row that the notes of T17.12 call wrong
  or partly read is right or has its reason.

## T17.22 — Real packs in the builder: walls along an edge, a house of pieces, round road corners

**Depends on:** T17.21
**Files:** `godot_templates/builder/lib/map_geo.gd`, `iso_tileset.gd`, the starter map, farm
and track recipes, `godot_templates/builder/recipes/racing/iso_track.gd`,
`rpggen/core/track_plan.py` (only if a corner's shape must be known to the check)

**Spec**
* **Walls from segments.** The edge of an isometric map is laid from the pack's wall segments
  by the side each stands on, with corners where two sides meet and the gap for the way out;
  a pack with whole wall tiles is laid as today.
* **A house from pieces.** A pack whose buildings are walls, doors, windows and roofs as
  separate pieces (*Medieval Town*, *Modular Buildings*) gets a house on the planned
  footprint: walls along its sides, a door at the plan's door, a roof over it; it blocks its
  footprint and sorts as one building. A pack with a whole house is placed as today.
* **Round corners.** A road corner piece that is round is known as round, and an isometric
  race drives it: the physics stays on the flat plan, so either the plan's corner is given
  the shape of the piece (surface cells, waypoints and the barrier follow it), or the square
  corner is drawn under a round piece so that no car is seen on the verge while it is on the
  road. The choice is made by looking at both.
* *Medieval Town* with *Nature*, and *Vector Roads Base* with *Tiles Vehicles*, are generated
  and looked at; the thin lines along diamond edges at a zoom that is no whole number are
  explained or mended.

**Done when**
* The two pairs of real packs make an isometric village with a house and walls and an
  isometric race whose cars stay on the road they are seen on, on the owner's machine, and a
  synthetic pack in each shape holds it in the tests.

## T17.23 — Added maps are built

**Depends on:** T17.06
**Files:** `rpggen/core/farm_plan.py` (`added_maps`), `rpggen/core/world_plan.py`, the areas of
T13.20, `godot_templates/builder/recipes/farm/`, `rpggen/core/forage_plan.py`

A farm's *Added maps* were names kept with the plan and nothing was built.

**Spec**
* A row of *Added maps* is a map of its own beside the farm, of a kind chosen from its name
  or a choice in the row: a **forest** (trees, forage places, things to clear), a **beach**
  (sand, water along one side, a place to fish, forage of its own), a **cave** (T17.24). Each
  is planned on a grid like the farm, stored once, built once, and joined to the farm or to
  the village by a door pair; the check of the farm's plan covers the way to it.
* Forage and fishing work on an added map as on the farm; the people's schedules may name a
  place on one.
* A farm that exists gets an added map by regenerating with a new row, as an added room or
  track does: nothing that exists is rebuilt.

**Done when**
* A farm with a forest and a beach is generated; the farmer walks to both and back, picks up
  what lies there and fishes from the beach, in the smoke run.

## T17.24 — The cave: combat on a farm

**Depends on:** T17.23
**Files:** `rpggen/core/options.py` (`combat` for a farm), the action RPG's enemies and combat
(`combat/realtime/`, `archetypes/arpg/`), `godot_templates/builder/recipes/farm/`

**Spec**
* The feature **Combat** is shown for a farm again and does something: with it on, the farm
  has a cave (an added map of its own kind) with the action RPG's enemies from the packs'
  `ENEMY` assets (or a drawn one), a weapon in the shop, hearts or health on the HUD, and
  things to find that the farm can use or sell. Being defeated is passing out: the farmer
  wakes at the bed as after 2:00.
* With it off there is no cave, no weapon and nothing to fight, as today.

**Done when**
* A farm with Combat on is generated; the farmer buys a weapon, enters the cave, defeats an
  enemy, brings back what it left, is defeated once and wakes at home, in the smoke run.

## T17.25 — Festivals and birthdays

**Depends on:** T17.09
**Files:** `rpggen/core/people_plan.py`, `archetypes/farm/` (a calendar of events),
`game/data/events.json` (written once), the HUD and the people's page

**Spec**
* Every person has a **birthday** (a season and a day, from the plan): a gift on that day
  counts several times, the People page and a calendar on the farmhouse wall show it, and
  the person says so.
* A **festival** a season, on a fixed day: the shop is closed, the people gather on the
  village square by their schedules, a line each, and one small thing to do (a contest judged
  on the best crop shipped that season, an egg hunt on the square, a fishing count, a feast)
  with a prize. The day before, the weather sign and the people say it is coming.
* The events are data (`events.json`), the user's once written, read by the calendar; the
  generated README says how to add one.

**Done when**
* A year is run in the smoke sequence by ending days: four festivals happen on their days with
  the people on the square, and a birthday gift counts as the plan says.

## T17.26 — Marriage

**Depends on:** T17.25
**Files:** `rpggen/core/people_plan.py` (who can be courted), `archetypes/farm/friendship.gd`,
the dialogue of the people, the farmhouse's room, `game/data/people.json`

**Spec**
* Some people of the plan can be courted (an option says how many; none turns it off). From
  eight hearts a **bouquet** from the shop begins courting and opens two more hearts; at ten
  a **pendant** proposes, and three days later the wedding is a day on the square.
* A spouse lives in the farmhouse (the bed is for two: the room is planned with it from the
  start, since a room that exists is never rebuilt), has a schedule of their own, speaks other
  lines, and helps on some mornings: waters part of the plot, feeds the animals, or leaves
  something on the table.
* Friendship that is neglected falls slowly; nothing worse happens. Children are not part of
  1.5.0.

**Done when**
* The smoke sequence courts and marries a villager by giving and by ending days, and finds
  the spouse at home in the morning with part of the plot watered.

## T17.27 — The editor dock on diamonds

**Depends on:** T17.14
**Files:** `godot_templates/addons/rpg_project_tools/dock/` (`placement.gd`, `asset_dock.gd`),
`godot_templates/addons/rpg_project_tools/tools/`

**Spec**
* In an isometric project the dock places an object on the diamond under the mouse, standing
  on its footprint, sorted with what is there, and drops it to the floor as it does on
  squares; the validator's Fix and the world repair count cells on diamonds (a door added by
  the repair has a diamond's shape).

**Done when**
* An object dropped from the dock into an isometric map in the editor stands where the game
  shows it, in a test that runs the dock's placement on an isometric scene.

## T17.28 — Imported maps in the isometric view

**Depends on:** T17.14
**Files:** `godot_templates/builder/recipes/imported_maps_recipe.gd`, `rpggen/core/adapters/tiled.py`
and the LDtk reader

**Spec**
* A Tiled map whose orientation is isometric (the *Miniature* packs ship one as a sample,
  which today is `TILE-009`, not imported) is imported into an isometric project: its layers
  onto the project's tile set by the tiles' pictures, its objects as objects on their
  diamonds. A staggered or hexagonal map is still refused with its reason. A map of squares is
  not imported into an isometric project, and the report says so.

**Done when**
* The sample map of *Isometric Miniature Farm* is a map of a generated project on the owner's
  machine, and a synthetic isometric Tiled map holds it in the tests.

## T17.29 — Real farming packs: one tile set in several forms, crops, farm animals and layered characters

**Depends on:** T17.21
**Files:** `rpggen/core/archive.py`, `rpggen/core/inventory.py`, `rpggen/core/classifier.py`,
`rpggen/core/adapters/` (a farm adapter or the generic ones), `rpggen/core/analyzer/`,
`rpggen/core/licenses.py` (or wherever licence files are found), `rpggen/core/catalog.py`,
`rpggen/core/mapping.py`, `rpggen/core/crop_plan.py` and `animal_plan.py` (only what they read),
the catalog and profile schemas, the wizard's pack and mapping pages, `tests/unit/`,
`test_packs/synthetic/`

The farm was built and tested on a drawn sample and on Kenney's isometric farm. On
2026-10-13 the analyzer was run on the first three real top-down farming packs on the owner's
drives (read where they lie; none is in the repository): Kenney's *Tiny Farm* (CC0, 136
pictures), EmanuelleDev's *Farm RPG - Tiny Asset Pack* (5,803 pictures, credit mandatory) and
LimeZu's *Modern Farm* (8,090 pictures, credit appreciated). None of them would give a farm
with its own crops, and nothing was confirmed without review but 15 RPG Maker autotiles.

**What they showed**
* **One tile set in several forms.** *Tiny Farm* ships the same 132 tiles as a spaced sheet, a
  packed sheet and 132 single files: the packed sheet is one 192 x 176 decoration and the
  single files are ground a second time. *Modern Farm* ships one pack at 16, 32 and 48 px in
  folders named so; the three are taken together, and the main tile set is 12 px with 1,728
  sources, a size the pack does not have. *Farm RPG* (16 px) gets tile sets of 8, 24, 32 and
  64 px from pictures that are not tiles.
* **Crops.** *Tiny Farm*'s tiles are numbered, with no name to go by. *Farm RPG*: 2 of the
  crop folders' files are read as growth strips; the other 18 "crops" are food icons, a
  butterfly called *Cabbage White*, a sea cucumber and a horse eating a carrot; 31 files of
  the season folders (`Crops/Spring`, ...) are decorations. *Modern Farm*: no crop at all;
  `Crops_Growth_*` folders are ground or decoration.
* **Farm animals** are decorations (*Farm RPG*'s 23 chickens, 64 x 112 sheets) or ground
  (*Modern Farm*'s chickens).
* **Characters of layered pieces.** *Farm RPG*'s player is a body, eyes, hair and clothes a
  file each for every animation: 3,998 files read as as many NPCs. *Modern Farm*'s farmer
  generator's bodies and outfits are ground.
* **Previews.** *Modern Farm*'s 243 GIFs beside the sheets they preview are read as art.
* **Licences.** *Farm RPG*'s is in `Documentation.txt` and *Modern Farm*'s is `LICENSE.txt` at
  the root of its zip; neither is found (`ASSET-021`), so a mandatory credit is lost.
* **Archives.** A `.rar` is not opened.

**Spec**
* **One tile set, several forms.** Pictures that are the same tiles (a sheet with spacing, a
  packed sheet, single files; or one folder a size) are found by their content, not their
  names, and are one tile set: one form is used and the others are set aside with the reason
  on their cards. A pack in several sizes offers its sizes, and the project's tile size is the
  user's choice, by default the one the other packs use, else the smallest. No tile set is made
  in a size the pack does not draw.
* **Crops** are found by the evidence a farming pack has: a folder of crops or of a season, a
  strip or a grid whose frames grow (each frame covers more of its cell than the one before,
  from the bottom), and the name of the produce beside it. An icon of a food is an item, not a
  crop. A crop that cannot be read with confidence stays unread with the reason on its card.
* **Farm animals** (chicken, cow, sheep, goat, pig, duck, horse by folder or name) are
  characters with their animations, of the role the farm's animals ask for.
* **Layered characters**: a folder of pieces of one character (body, eyes, hair, clothes, a
  file each for an action) is one character whose layers are put together in a stated order
  (the pack's own order when it gives one, else body, clothes, hair, accessories); the
  wizard shows it as one character with its choices.
* **Previews**: a GIF or a picture called preview or sample beside the sheets it shows is unused.
* **Licences**: a licence is also read from `Documentation.txt`, `Readme`, `Terms` and the like
  when the text says *licence*, *credit* or *commercial*, at the pack's root or one folder down,
  and inside an archive. A credit the licence asks for is written into the generated README.
* **Archives**: `.rar` is opened when the system can (Windows' own `tar` reads it), else
  refused with its reason, as `.7z` is.

**Done when**
* The three packs give a farm each, generated on the owner's machine, with the packs' own
  ground, crops that grow in the packs' pictures (where a pack draws growth), a chicken of the
  pack where it has one, and a player of the pack; each is played through the farm's smoke sequence and looked at in a picture.
* A synthetic pack in each shape (one set in three forms, a pack in two sizes, a crop folder
  of growth strips beside food icons, a layered character, a licence in a documentation file)
  holds it in the tests, and the accuracy corpus has an expected file for each.

---

## Appendix — The request of 2026-10-12, item by item

| Asked for | Card |
|-----------|------|
| A farm and life sim | T17.01 – T17.11 (`farm`), with its wizard, sample and tests in T17.16 – T17.18 |
| Isometric | T17.12 – T17.15 (`projection: isometric` for `turn_based`, `arpg`, `farm` and `racing`) |
| The others stay as future | Part E |
| 2026-10-13: the faults real packs still show, added maps, the dock and imported maps on diamonds, a cave, marriage and festivals are all to be addressed | Part F (T17.21 – T17.28) |
