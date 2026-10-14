# 02 — Data Schemas

Every JSON file is written with `jsonio.write` (sorted keys, 2-space indent, UTF-8, LF). JSON Schema files live in `rpggen/schema/` (draft 2020-12). Card T1.02 creates the schema files from this document, and every load validates against them.

Conventions used below:
* `posix_rel` — a POSIX relative path string, with no leading `/` and no `..`.
* `res_path` — a `res://` path string.
* `vec2i` — a JSON array of 2 integers, `[x, y]`.
* `rect` — a JSON array of 4 integers, `[x, y, w, h]`, in pixels.
* `?` after a field name — the field is optional; omit it rather than writing `null`.

---

## 1. `generator_config.json` (config_version 1)

Location: `<project>/rpggen/generator_config.json`. Written by Python and read by both sides.

| Field | Type | Default | Rules |
|-------|------|---------|-------|
| `config_version` | int | 1 | Must be 1. |
| `generator_version` | string | package version | |
| `godot_version` | string | `"4.7.2"` | The version validated during preflight. |
| `project_name` | string | — | 1–64 chars; written to `application/config/name`. |
| `archetype` | enum `turn_based`/`arpg`/`metroidvania` | `turn_based` | `metroidvania` since release 1.2 (M14). |
| `packs` | array of PackRef | — | At least 1 item. |
| `base_tile_size` | int | detected | 8 to 256. The wizard and `rpggen generate --pack` set it from the packs (`catalog.dominant_tile_size`); 16 when they have no tile set. |
| `resolution` | vec2i | `[640, 360]` | Both values between 160 and 3840. |
| `window_size` | vec2i | `[1280, 720]` | |
| `map_layers` | array of string | see below | Must contain `Ground`. Unique entries. |
| `features` | object of bools | all true except `navigation` | Keys: `tilesets, collision, terrain, animations, demo, editor_tools, save, dialogue, combat, navigation, debug_tools`. |
| `validation` | object | `{"smoke_test": true}` | Strict mode is always on (failures block delivery). |
| `seed` | int | 12345 | Used for every RNG in generation and smoke tests. |
| `input` | object | see §1.1 | Action → bindings. |
| `sounds` | object | `{}` | Optional (T11.20). Sound slot → audio asset id. Slots: `music_map`, `music_battle`, `music_title`, `sfx_ui_move`, `sfx_ui_confirm`, `sfx_ui_cancel`, `sfx_hit`, `sfx_attack`, `sfx_pickup`, `sfx_chest`, `sfx_door`, `sfx_step`, `sfx_save`, `sfx_levelup`. A slot that is absent is silent. Omitted from the JSON when empty. Beyond the fixed list any key matching `^(music|sfx)_[a-z][a-z0-9_]{1,30}$` is a **custom slot** (T13.16): `sfx_step_<surface>` is the footstep on ground tagged `surface:<surface>`, any other is played by name. A key that does not match is `CAT-006`. |
| `starter_map` | object | defaults | Optional (T11.25). `size` [w, h] tiles (24..96 each), `buildings` 0..4, `npcs` 0..6, `enemies` 0..8, `chests` 0..4, `decorations` 0..40, `ground_patches` 0..20, `ground` asset id or "". Omitted from the JSON when equal to the defaults. `areas` (T13.20, optional): a list of 1 to 12 `{ "name", "biome", "size"?, "enemies"?, "chests"?, "join"?, "reroll"? }` rows that make a **world of connected maps** (§12): `biome` is `village`, `field`, `forest`, `cave` or `shore`; `size` [w, h] is 16..96 tiles (default [32, 20]); `enemies` and `chests` are 0..12 (default 2 and 1); `join` names the area a row added to an existing world hangs on; `reroll` (0 or more) gives another arrangement of that area only. The first `village` row (else the first row) is the starter map, whose size and counts are the options above. Without `areas` the project gets the starter map and the field of 1.0. |
| `repair_world` | bool | `true` | Optional (T13.24). After a build, mend the doors that lead nowhere and the unreachable maps among the maps rpggen made and nobody changed (`rpggen/world_repair.json` lists what was done). Omitted from the JSON when true. |
| `projection` | enum `top_down`/`isometric` | `top_down` | Optional (T17.13, release 1.5). How the maps of the project are seen: from above on squares, or at an angle on the diamonds of an isometric pack. `isometric` is allowed for `turn_based`, `arpg`, `farm` and `racing` (`CAT-002` for another kind) and needs a pack with an isometric ground tile (`CAT-002` without one: no ground is drawn for this view). **A generated project cannot change its projection** (its maps are painted in one): a run over a project whose saved config has the other one is refused with `CAT-002`. Omitted from the JSON when it is `top_down`, so every config before 1.5 is what it was. The isometric maps of `turn_based`, `arpg` and `farm` are made (T17.14) and the tracks of `racing` (T17.15): every kind that has the view is made, and `config.ISOMETRIC_NOT_YET` is empty. (A kind on that list would be refused with `CAT-002`, *the isometric view of a ... game is not made yet*, on reading a config and on running one that was made in memory, before anything is built.) |
| `iso_controls` | enum `screen`/`grid` | `screen` | Optional (T17.14, release 1.5). How the pad moves the player on an isometric map. `screen`: up is up on the screen, as on a map of squares. `grid`: the four directions follow the diamond's axes (up to the north neighbour, the upper right; right to the east, the lower right; down to the south, the lower left; left to the west, the upper left), so one direction held walks along a row of cells. It says nothing in a top-down project, and nothing to a `racing` project in either view (a race is steered: `starter_map.steering`): for that kind the key is accepted, read as `screen` and not written back (`config.ISO_CONTROLS_KINDS` are `turn_based`, `arpg` and `farm`). The builder writes it as the project setting `rpg/iso_controls` of an isometric project (`RpgIso.controls()` reads it); no other project has the setting. Omitted from the JSON when it is `screen`. It changes no binding (`input`). |
| `imported_maps` | object | `{}` | Optional (T12.49). `include`: ids of the catalog's `maps` to build into `game/maps/imported/<pack>/`; `starter`: the id of the map that becomes `game/maps/starter_map.tscn` (the layout planner is then skipped, and the map has none of the demo's villager, chest or enemy). The starter is built even when it is not in `include`. Omitted when empty. |
| `git` | object | `{}` | Optional (T12.12). `pack_art`: `"commit"` (default), `"lfs"` (the pack art goes through Git LFS; falls back to `commit` with ENV-013 when git-lfs is missing) or `"ignore"` (`assets/packs/` is added to the generated `.gitignore`). Omitted when it holds the default. |
| `export_targets` | array of strings | `["windows"]` | Optional (T12.52). The platforms that get a preset in `export_presets.cfg` and a test export: `windows`, `web`, `linux`, `macos` (at least one, no repeats; written in that order). Omitted when it is `["windows"]`. |
| `starter` | object | `{}` | Optional (T3.11). Starter selections of the demo recipes: `player`, `npc`, `enemy`, `ground`, `building`, `chest`, `portrait` → an asset id or an object id. Omitted when empty. |

Default `map_layers`: `["Ground", "GroundDetails", "Walls", "Props", "Overhead"]`.

**A metroidvania (release 1.2, M14)** uses the same file with these differences:

* `starter_map` holds the *starter world* instead (T14.06): `rooms` 5..12 (default 6), `room_size`
  `[w, h]` tiles (32..80 by 23..45, default `[40, 23]`), `abilities` (a list from `double_jump`,
  `dash`, `wall_jump`, `high_jump`, `break_blocks`, stored in that order, default the first two),
  `enemies` 0..4 per room (default 2), `pickups` 0..12 in the world (default 4) and `added_rooms`
  (at most 12 rows `{ "name", "join" }`, each a room built beside the room `join` names). `rooms`
  must be at least `len(abilities) + 3`. As for a starter map, only the keys that differ from the
  defaults are written.
* `starter` may have `boss` (the guardian's sprite, role `BOSS`); `building` is not used.
* For the arcade kinds (M16) `starter` may have `vehicle` (the car of a racing game, role
  `VEHICLE`), `projectile` and `explosion`: the keys the Mapping page writes for those roles
  since T16.03 (the schema takes them since T16.17).
* `sounds` has four more fixed slots: `sfx_jump`, `sfx_land`, `sfx_dash`, `sfx_ability`. In the
  other archetypes a slot of such a name is a custom slot.

The arcade kinds (M16) have fixed slots of their own in the same way: `shmup` has `sfx_shoot`, `sfx_explosion`, `sfx_powerup`, `sfx_bomb`, `music_stage`, `music_boss`; `run_and_gun` has `sfx_shoot`, `sfx_explosion`, `sfx_grenade`, `sfx_weapon_pickup`, `sfx_grapple`, `music_stage`, `music_boss`; `racing` has `sfx_engine`, `sfx_skid`, `sfx_bump`, `sfx_pickup`, `sfx_lap`, `sfx_countdown`, `music_race`, `music_results`. The `archetype` enum lists a kind once it can be built: `shmup` since T16.04, `run_and_gun` since T16.08; `racing` not yet. A `run_and_gun` has in `starter_map` (T16.10): `stages` (1 to 8, default 3), `length` (`short`, `medium`, `long`: 6, 9 or 13 chunks of half a screen between the start and the boss's arena), `lives` (1 to 9, default 3), `health` (1 to 5, default 1: one hit is a death), `keep_weapon` (default false: a death costs the weapon), `left_edge_kills` (default true; false makes the left edge of the screen a wall), `difficulty` (`easy`, `normal`, `hard`) and `added_stages` (at most 8 rows `{ "name" }`). Its stages are planned once by `rpggen/core/stage_plan.py` and stored in the section `stages` of `rpggen/world_plan.json` like a shoot-em-up's, with `kind: "run_and_gun"`, `chunk_cols` and `rows`; a Stage there also has `chunks` (the kind of each: `flat`, `gap`, `step`, `planks`, `spikes`, `wall`, `trap`, `arena`), `tiles` (its rows in the room plan's alphabet: `#` ground, `.` air, `=` a one-way plank, `^` spikes), `start` ([x, y] px, the soldier's feet) and a `boss` with a `kind` (`wall`, `walker`, `flyer`). The tiles are painted into the stage's scene and are not in `stages.json`. The grapple (T16.11) is two more keys of `starter_map`: `grapple` (default false: the soldier has the arm; its input action is `grapple`, L / V / pad B) and `jump` (default true; false needs `grapple` true, and the soldier does not jump). The stored plan has both; a plan made with `jump` false has a block of ground in the air over every gap and every bed of spikes (which is sunk into the ground) to swing from, and planks that reach out from every step and wall to be hoisted on to. `VAL-030` (a warning) names what a soldier that does not jump cannot pass. A `racing` game (T16.12) has in `starter_map`: `steering` (`relative`, the default: left and right turn the car; `absolute`: the stick or the arrows are the heading of the car) and `camera` (`follow`, the default; `fixed`: the whole track on the screen). Its input actions are `accelerate` (Up / W / pad A / the right trigger), `brake` (Down / S / pad B / the left trigger; it reverses a car that stands), `boost` (Shift / Space / pad X), and `move_left` / `move_right` to steer. Its tracks are stages (`game/data/stages.json`, with `axis: "none"` and `exit: "custom"`). The tracks (T16.13) are four more keys of `starter_map`: `tracks` (1 to 8, default 4), `laps` (1 to 9, default 3), `track_size` (`small`, `medium`, `large`: a field of 4 by 3, 5 by 4 or 6 by 4 cells of nine tiles), `difficulty` (`easy`, `normal`, `hard`) and `added_tracks` (at most 8 rows `{ "name" }`). They are planned once by `rpggen/core/track_plan.py` and stored in the section `stages` of `rpggen/world_plan.json` with `kind: "racing"`, `track_size`, `laps`, `block` (9) and `road` (5). A track there is a Stage with: `laps`; `cells` ([columns, rows] of its field); `loop` (its cells in the order they are driven, clockwise); `rows` (what every tile is: `g` grass, `r` road, `s` the start line, `d` dirt, `o` oil, `b` a boost arrow); `start` (`position` [x, y] px of the car, `heading` in rad, `line` [x, y] px); `checkpoints` (`id`, `cell`, `position`, `heading`, `width` px, in the order they are passed); `waypoints` (one a cell: `cell`, `position`, `speed` in tiles a second); `barriers` ([x, y, w, h] in tiles: the four edges of the field, then the cells the loop does not use); `tyres` and `decoration` ([x, y] px); `pickups` (`position`, `kind`: `boost`, `missile`, `bomb`, `shield`). `stages.json` has a track without what is painted into its scene (`rows`, `barriers`, `tyres`, `decoration`, `loop`, `cells`). The race (T16.14) is two more keys of `starter_map`: `rivals` (0 to 5, default 3) and `rubber_band` (default true: a rival far ahead of the player eases off a little), and one more input action, `fire` (X / K / pad Y: the weapon the car has picked up). A checkpoint's `position` is the middle of the edge where the road comes into its cell. A pickup's `kind` is `boost`, `missile`, `bomb`, `shield`, or a part: `speed`, `tyres`, `acceleration` (one part lies on every track, a different one on each of three). The championship (T16.15) is one more key of `starter_map`: `elimination` (default false; true puts a player who comes in last twice out of the championship). It is not part of the plan of the tracks: it is a property of the game's combat mode. The saved game of a racing game has the championship in its arcade run (`flags.arcade.extra`: `races`, `last` (how often the player was last) and `points`, rows of `[driver, points, place in the last race]` with the drivers `player`, `rival_1`, ...). A wave of a run and gun names its `enemy` (`runner`, `sniper`, `turret`, `jumper`, `wall_cannon`, or `pickup` with a `weapon`: `machine_gun`, `spread`, `laser`, `flame`); it is placed in the stage (`anchor: stage`) and may be `blocking`. Its input actions are `jump`, `shoot`, `grenade` and `aim_lock` beside the four directions and `down`. It is seen from the side like a metroidvania: its tile sets get the one-way platforms, ladders and hazards, its packs the side-view kit, and its project the metroidvania's runtime folder and recipes beside its own. A `shmup` keeps its options in `starter_map` (T16.06): `orientation` (`vertical`, the default: seen from the top, scrolling up; or `horizontal`: seen from the side, scrolling right), `stages` (1 to 8, default 3), `length` (`short`, `medium`, `long`: 4, 6 or 9 screens a stage), `lives` (1 to 9, default 3), `bombs` (0 to 9, default 3), `auto_fire` (default true), `difficulty` (`easy`, `normal`, `hard`: the speed and the number of the enemies' bullets and the health of the bosses) and `added_stages` (at most 8 rows `{ "name" }`, each a stage after the last). As for a starter map the section is written only when it differs from the defaults, and then whole. Its input actions are `shoot`, `bomb` and `focus` beside the four directions. A `farm` (M17) has `sfx_hoe`, `sfx_water`, `sfx_plant`, `sfx_harvest`, `sfx_sell`, `sfx_animal`, `sfx_rooster` (a new day), `music_spring`, `music_summer`, `music_autumn`, `music_winter` (a season without its own plays the first that is filled) and `music_night`, filled by file name like the others and silent when empty. The slots are for the work, not one a tool: the axe plays `sfx_hoe`, the sickle `sfx_harvest` whatever it cuts, the rod `sfx_water` for its cast and `sfx_harvest` for a fish landed (and `sfx_bite`, a custom slot, when the project has one), a thing foraged `sfx_harvest`.

The stages of a shoot-em-up are planned once (`rpggen/core/wave_plan.py`) and stored in `rpggen/world_plan.json` as the section `stages`: `{ "plan_version": 1, "seed", "orientation", "difficulty", "length", "view": [w, h], "tile", "list": [ Stage ], "added": [names], "notes": [..] }`. A Stage there is the Stage of `stages.json` below with `id`, `level` (0 for the first) and, per wave, `threat` (how hard it is; it never falls), `fast`, `tough`, `fan` and `look` (which of the small-enemy scenes), without the scenes of its enemies. A project that has `game/data/stages.json` keeps its stored plan: it is never planned again, and a row of `added_stages` appends a stage to it. The builder writes the plan with its scenes to `generated/data/stages.json` on every build and to `game/data/stages.json` once; the game reads the second (the user's) and takes from the first the stages the second does not list. Their `features` start with `dialogue` and `navigation` off (T16.01); both can be switched on.

The stages of an arcade game are `game/data/stages.json` (T16.01), written by the recipe of the kind from its plan: `{ "stages": [ Stage, ... ] }`. A Stage is `{ "scene", "title", "axis": "up" | "right" | "none", "speed" (px/s), "length" (px; 0 has no end), "exit": "reach_end" | "clear_waves" | "custom", "par_time_s", "music", "waves": [ Wave ], "boss"? }`. A Wave is `{ "id", "enemy", "scene", "formation": "line" | "column" | "v" | "circle" | "sine", "count", "gap" (px), "interval" (s), "position": [x, y], "anchor": "screen" | "stage", "trigger": "start" | "progress" | "time" | "after", "at", "after": "<wave id>", "blocking", "points" }`. A boss is `{ "scene", "name", "health", "points", "position": [x, y], "phases": [ { "until" (the fraction of health the phase lasts down to), "movement", "attacks": [..], "interval", "telegraph_s", "speed" } ] }`. A Wave may also have `bonus` (points for a formation of which every enemy was shot). The whole entry of a wave is handed to its enemies, so a kind may add keys of its own: a shoot-em-up reads `path` (`straight`, `sine`, `swoop`, `sweep`, `dive`, `close`), `shoots`, `drop` (a power-up: `weapon_up`, `weapon:<kind>`, `bomb`, `life`, `shield`, `points`) and, for a rock, `drift` ([x, y] px a second). The runtime reads the file and adds nothing to it.

**An isometric race** (`archetype: racing` with `projection: isometric`, T17.15, release 1.5) has the plan, the options and the `stages.json` of a race seen from above, key for key: `start`, `checkpoints`, `waypoints` and `pickups` are positions **in the px of the flat plan** (x east, y south, a tile `base_tile_size` px), not of the screen, and the race is driven there. What differs is in the scene of a track: `Ground` is a layer of the isometric tile set (`iso.tres`), and a node `View` (`RpgRaceView`) says how the plan is seen: `footprint` (the diamond a cell of the map is drawn as: the project's, or a whole multiple of it when the layer `Ground` is enlarged), `cell_px` (how many px of the plan one diamond is wide) and `origin` (the point of the plan that is the top corner of the cell (0, 0): one tile in, behind the wall round the field). A point of the plan `p` is drawn at `RpgIso.cell_to_screen((0, 0)) + ((p - origin) / cell_px - (0.5, 0.5))` laid along the two axes of the diamond. The scale is chosen by the builder for the picture of the car (`RaceBuild.scale_for`): with road pieces of the packs (tiles of the role `ROAD` whose `joins` say their sides) a cell of the loop is one diamond (`cell_px` is nine tiles) and the diamonds are enlarged one to four times; without them the road is drawn and a diamond is two to nine tiles wide. An isometric race has no drawn people (`rpggen_iso_kit` is not added to its catalog) and no drawn road (`rpggen_arcade_kit.road` is square ground); a pack without a car gets `rpggen_arcade_kit.car`, the sheet of sixteen headings drawn from above, which is shown by the heading on the screen.
* `input` has `jump`, `dash`, `attack` and `down`, and `interact` is E / Up (Space jumps).
* `map_layers` is not used (a room has the layers `Background`, `Ground`, `Platforms`, `Hazards`,
  `Decoration`, `Foreground`), `imported_maps` is not used, and `features.navigation` is off.

**A `farm` (M17).** The `archetype` enum has `farm` since T17.04. It is a top-down game: `starter_map`, `starter`, `map_layers` and `imported_maps` are what they are for `turn_based`, and that starter map is its **village**; the farm itself is a map of its own, planned once and stored (§12.3), with the farmhouse a new game starts in. Its `features` start with `combat` and `navigation` off. Its crops are planned once and stored in `rpggen/world_plan.json` (§12.2). Its money (T17.08) is two more keys of `starter_map`, which only a farm has: `starting_money` (0 to 99999, default 100: the gold of `game/data/new_game.tres`, which is written once) and `pass_out_loss` (default true: a farmer who stays up to 2:00 loses a tenth of the money as well as half the energy; false keeps the money). A new game also starts with a hoe, a watering can and fifteen seeds of the first crop; the sickle and the axe are bought. The village shop of a farm (`game/data/shops/village_shop.tres`, written once) is an `RpgFarmShop`: the shop of every top-down kind with `opens` (9), `closes` (17) and `closed_weekday` (6, the day `people_plan.SHOP_CLOSED_DAY` gives the shopkeeper off; -1 for none), `seasonal` (default true: the seeds of the season are on offer, from `crops.json`) and `sell_ratio` 1. The farm's own map (T17.06) is five more keys of `starter_map`, read by `rpggen/core/farm_plan.py`: `farm_size` (`small`, `medium`, `large`: a field of 32 by 24, 40 by 30 or 48 by 36 cells; default `medium`), `plot` (`small`, `medium`, `large`: 6 by 4, 12 by 8 or 16 by 10 cells of tillable ground; default `medium`), `animals` (`none`, `coop`, `coop_and_barn`; default `none`), `difficulty` (`easy`, `normal`, `hard`: how much there is to clear, and the days of the crops) and `added_maps` (at most 8 rows `{ "name", "kind" }`, T17.23: each is a map of its own beside the farm; `kind` is `forest` or `beach`, and a row without one takes it from its name: a beach when the name has the word *beach*, *shore*, *coast*, *seaside*, *sea*, *bay* or *strand*, else a forest. `cave` is a kind the planner knows and does not build yet (T17.24): a row of it is refused with a sentence that says so). The planner takes the footprint of the farmhouse from the starter building of the catalog, of a coop and a barn from a `BUILDING` object tagged so, and plans a pond when the packs have a `WATER` tile and a well when they have none. `VAL-031` (a warning, a line a problem) says what keeps the stored farm from being worked. The builder makes `game/maps/farm.tscn` and a room for every building of the plan (`game/maps/farm_house.tscn`, `farm_coop.tscn`, `farm_barn.tscn`) once; `game/data/new_game.tres` of a farm starts in `farm_house.tscn` at the spawn `start`. The door pair between the two maps: the farm's door `to_village` leads to the village's spawn `from_farm`, the village's door `to_farm` (in the wall opposite the farm's way out) to the farm's spawn `from_village`. The people (T17.09) have no key of their own in the config; the builder writes `generated/data/people.json` on every build and `game/data/people.json` and `game/data/dialogue/person_<id>.tres` once, and puts the places their schedules name on the village as markers under `Places`: `home_<n>` (and `home_<n>_2` to `_4`), `home`, `square` (and `square_2` to `_6`) and `work`; the people take the spots of a place in turn. Fishing and foraging (T17.10) have one key of `starter_map`, which only a farm has: `fishing` (default true; false keeps the fishing rod out of the shop). The rod is sold only where the farm's plan has a pond (`farm.map.water.kind`); what is planned of the fish, the things to forage and the places they lie at is `farm.forage` (§12.6). The builder writes `generated/data/forage.json` on every build, and `game/data/forage.json` and an item for every fish and every thing to forage (`game/data/items/<item>.tres`) and for the rod (`fishing_rod.tres`) once; the places are the markers `Forage/Spot<n>` of `game/maps/farm.tscn`. The calendar (T17.03) has two keys of `starter_map` since T17.16, which only a farm has: `days_per_season` (`7`, `14` or `28`, default 28: the property of that name of the farm's mode, which gives it to `RpgCalendar`) and `day_length` (`short`, `normal`, `long`; default `normal`: a game minute is 0.5, 0.7 or 1.0 real seconds, the mode's `minute_s`, so a day of 1200 minutes lasts 10, 14 or 20 minutes). Both are read on every generation, so a project that exists can change them; a saved game keeps its date, and a day beyond a shorter season is the season's last. Festivals and birthdays (T17.25) have one key of `starter_map`, which only a farm has: `festivals` (default true; false plans no festival and no birthday, and the farm is what it was before the card but for code that does nothing). With it on the festivals are planned once and stored as `farm.events` (§12.7), every person of `farm.people` has a `birthday`, the builder writes `generated/data/events.json` on every build and `game/data/events.json` once, the village that is built gets the markers `festival_table` and `festival_egg_1` to `_5` under `Places`, the farmhouse room that is built gets the node `WallCalendar`, the dialogue of a person that is written gets three more lines (`festival`, `festival_tomorrow`, `birthday:<id>`), and the mode's property `festivals` is true. It is read on every generation: switched on for a farm that exists, the plan gains its events and the people their birthdays, and neither the village nor the room nor `game/data/people.json` is written again (the game finds the calendar in the pause menu, the birthdays in `generated/data/people.json` and puts the eggs round the square); switched off, the stored plan stays and the mode is built without the property.

**PackRef:** `{ "pack_id": str, "source": str (absolute path as the user gave it; informational only), "source_sha256": str, "kind": "zip"|"7z"|"rar"|"folder", "folders"?: [str] }`. `folders` (T16.22, optional) is for a `source` that is a bundle of packs, a folder each: it names the pack folders to take, by their names, and each is a pack of its own. An entry with one folder is the pack `pack_id`; an entry with several is read as one entry per folder, in the order given, with ids made from the folders' names, and is written back that way, so the ids stay. The wizard and `--pack-folder` write one entry per folder. `folders` is not allowed on a `rar` (a rar is not listed, so it is never a bundle); on any other source that is not a bundle, and for a folder the bundle does not have, opening the pack stops with `ARCH-001`, which names the nearest folder. Only the named folders are unpacked, with the licence files of the bundle's top level beside each.

### 1.1 `input`

```json
{
  "move_up":    { "keys": ["W", "Up"],     "joy_buttons": [11], "joy_axes": [[1, -1.0]] },
  "move_down":  { "keys": ["S", "Down"],   "joy_buttons": [12], "joy_axes": [[1, 1.0]] },
  "move_left":  { "keys": ["A", "Left"],   "joy_buttons": [13], "joy_axes": [[0, -1.0]] },
  "move_right": { "keys": ["D", "Right"],  "joy_buttons": [14], "joy_axes": [[0, 1.0]] },
  "interact":   { "keys": ["E", "Space"],  "joy_buttons": [0] },
  "confirm":    { "keys": ["Enter", "Space"], "joy_buttons": [0] },
  "cancel":     { "keys": ["Escape", "Backspace"], "joy_buttons": [1] },
  "menu":       { "keys": ["Escape", "Tab"], "joy_buttons": [6] }
}
```

The ARPG archetype adds `attack` (J, mouse button 1, joy 2), `secondary_attack` (K, mouse button 2, joy 3), `dodge` (Shift, joy 1) and `quick_item` (Q, joy 9). Mouse buttons use the key `"mouse_buttons": [1]`.

A `farm` (T17.04) has `interact` on E and pad X (joy 2) only, because Space is `use`: `use` (Space, J, mouse button 1, joy 0: what is held is used on the tile ahead), `next_item` (R, joy 10) and `prev_item` (Q, joy 9), and `hotbar_1` to `hotbar_10` (the keys 1 to 9 and 0: the ten slots of the hotbar).

* Key names are Godot key names as accepted by `OS.find_keycode_from_string`. ⚠ VERIFY.
* Joy button indices are Godot `JoyButton` enum values. Axis entries are `[axis_index, direction]`.
* The project-settings recipe sets **physical** keycodes (`InputEventKey.physical_keycode`).

---

## 2. `inventory.json` (cache, per pack)

Location: `%LOCALAPPDATA%/rpggen/cache/inventories/<source_sha256>.json`. It is immutable.

```json
{
  "inventory_version": 1,
  "pack_id": "forest_pack",
  "source_sha256": "…",
  "files": [
    {
      "path": "Tilesets/grass.png",
      "sha256": "…",
      "size": 4210,
      "ext": ".png",
      "kind": "image",
      "image": { "w": 256, "h": 128, "mode": "RGBA", "has_alpha": true, "frames": 1 }
    },
    { "path": "LICENSE.txt", "sha256": "…", "size": 812, "ext": ".txt", "kind": "license" }
  ],
  "skipped": [ { "path": "__MACOSX/._grass.png", "reason": "os_junk" },
               { "path": "Get more packs.html", "reason": "not_an_asset" } ]
}
```

`kind` is one of `image`, `audio`, `font`, `license`, `doc`, `metadata`, `other`. It is decided by extension (T2.02) plus filename rules:
* `license` — the stem, lowercased, starts with `license`, `licence`, `credits`, `readme`, `copying` or `attribution`.
* `metadata` — the extension is `.tsx`, `.tmx`, `.tsj`, `.tmj`, `.json`, `.ldtk`, `.aseprite`, `.ase`, `.xml` or `.rpgproject`.

Files are sorted by path (01_CONVENTIONS §5).

---

## 3. `analysis` cache entry

Location: `%LOCALAPPDATA%/rpggen/cache/analysis/<sha256[0:2]>/<sha256>.json`. The key is the image file hash plus `ANALYZER_VERSION`. Increasing `ANALYZER_VERSION` invalidates the cache.

```json
{
  "analyzer_version": 1,
  "sha256": "…",
  "w": 256, "h": 128,
  "has_alpha": true,
  "opaque_bbox": [0, 0, 256, 128],
  "grid_candidates": [
    { "cell": [16, 16], "margin": [0, 0], "separation": [0, 0], "score": 0.97,
      "nonempty_cells": 96, "total_cells": 128 }
  ],
  "regions": [ [0, 64, 80, 64] ],
  "strip": { "axis": "x", "frames": 6, "frame": [32, 32] },
  "baseline_y": 31,
  "dominant_colors": ["#3a7d2c", "#5aa142", "#2f5e22"],
  "nine_slice": null
}
```

---

## 4. `asset_catalog.json` (catalog_version 2)

Location: `<project>/rpggen/asset_catalog.json`.

### 4.1 Top level

| Field | Type | Notes |
|-------|------|-------|
| `catalog_version` | int | 2 |
| `generator_version` | string | |
| `packs` | array of CatalogPack | Sorted by `pack_id`. |
| `assets` | array of Asset | Sorted by `id`. |
| `objects` | array of SheetObject | Regions cut from sheets (§4.5), sorted by `id`. |
| `tilesets` | array of TileSetDef | §4.6, sorted by `name`. |
| `id_allocations` | object | §4.7 |
| `folder_rules` | array of FolderRule | §4.8, kept in insertion order (order matters). |
| `maps` | array of Map | Optional (T12.49), §4.9, sorted by `id`. Omitted when the packs have no Tiled or LDtk maps. |
| `variants` | array of Variant | Optional (T13.18), in the order they were made. A Variant is `{ "id", "source", "name", "op", "params", "stats"? }`: `id` is the id of the variant's effective asset (`<pack>.variants.<slug>`), `source` the asset it recolours, `op` is `hue` (`params`: `shift` 0–359 degrees, `saturation` and `value` multipliers 0–4) or `palette` (`params.map`: a list of `[[r, g, b], [r, g, b]]` pairs, from → to), and `stats` (enemies and bosses only) holds multipliers 0.1–20 for `hp`, `attack`, `xp`, `gold` (1 is not stored). The effective asset is in `assets` like any other: path `generated/variants/<id with _ for .>.png`, the source's effective facets, and `derived_from`. A variant whose source is gone keeps its definition and has no asset (`ASSET-029`). Omitted when empty. |
| `characters` | array of LpcCharacter | Optional (M16, release 1.4). An LpcCharacter is `{ "id", "name", "body", "layers", "auto"?, "removed"? }`: `body` and `layers` are asset ids of LPC parts of one pack; the layers are drawn over the body in the order of their parts, whatever their order here. The sheet is rendered on every analysis into `generated/lpc_characters/<id with __ for .>.png` and is an asset with `detected_by: "lpc_compose"` and `derived_from` its body. `auto` marks a character the packs left no choice about (made again from the packs as long as nobody has made or removed one); `removed` keeps a character somebody took away from being made again. |

### 4.2 CatalogPack

```json
{ "pack_id": "forest_pack", "source_sha256": "…", "root": "assets/packs/forest_pack",
  "license_files": ["assets/packs/forest_pack/LICENSE.txt"],
  "adapters_matched": ["tiled", "generic_grid"], "profile_id": null,
  "warnings": ["rpgmaker_rtp_detected"],
  "license": { "license_id": "CC-BY-4.0", "author": "", "url": "https://example.itch.io/forest",
               "attribution_required": true },
  "license_overrides": { "author": "Jane Doe" } }
```

`license` (T12.51) is what `rpggen/core/licenses.py` read from the licence, credits and readme
files: `license_id` is `CC0-1.0`, a Creative Commons BY id (`CC-BY-4.0`, `CC-BY-SA-3.0`,
`CC-BY-NC-4.0`, …), `OGA-BY-3.0`, `MIT`, `commercial` (a vendor's licence that allows commercial
use), `rpgmaker` (the RPG Maker terms) or `""` (unknown). `license_overrides` (optional, omitted
when empty) holds the Audit page's corrections of the same keys and survives a new analysis; the
effective licence is `license` with the overrides on top, and a `license_id` chosen there without
`attribution_required` brings that licence's own rule. A catalog without `license` reads an
unknown licence.

### 4.3 Asset

```json
{
  "id": "forest_pack.tilesets.grass",
  "pack_id": "forest_pack",
  "path": "assets/packs/forest_pack/Tilesets/grass.png",
  "sha256": "…",
  "kind": "image",
  "status": "AUTO_DETECTED",
  "detected": { …Facets… },
  "overrides": { …partial Facets… },
  "detected_by": "generic_grid",
  "confidence": 0.94
}
```

* `status` is one of `CONFIRMED`, `AUTO_DETECTED`, `NEEDS_REVIEW`, `MISSING`, `UNUSED` or `CONFLICT`.
* Status rules, applied by `catalog.recompute_status`:
  * Any override present, or `confidence >= 0.999` from a metadata adapter or profile → `CONFIRMED`, unless conflicted.
  * `confidence >= 0.75` → `AUTO_DETECTED`.
  * Otherwise → `NEEDS_REVIEW`.
  * The file is missing on disk → `MISSING`.
  * The role is `NONE` (the user excluded it) → `UNUSED`.
  * A pack update changed the dimensions of an atlas used by a tileset → `CONFLICT`. Only explicit user resolution clears this.
* An asset whose file the vendor renamed in a pack update carries `renamed_from`: the pack-relative path of the earlier release (T5.05). Its id, path and tile set source id follow the rename; overrides carry over.
* An override may set `remove_source: true` (T5.04): the user confirmed that the tile set source of this asset, which stays after the file left its pack (REGEN-003), can be removed. It is the only way a tile set source is ever removed.
* Assets may also carry an optional `rule` object (T2.14): the facets written by folder rules (§4.8), so effective = `detected` <- `rule` <- `overrides`.
* **Effective facets** = a deep merge of `detected` with `overrides`, where override keys win. An override value of `null` means "remove this detected key". Implement this once as `catalog.effective(asset) -> dict` and as `catalog_reader.gd: effective(asset)`. Test both on the same fixtures; the results must match (T1.07).

### 4.4 Facets (keys inside `detected`/`overrides`)

| Key | Type | Used when | Meaning |
|-----|------|-----------|---------|
| `role` | enum Role | always | Primary role. `NONE` means excluded. |
| `roles_alt` | array of [Role, float] | detection only | Other candidate roles with confidence. |
| `usage` | enum `tiles`/`sprite`/`growth_strip`/`iso_tile`/`iso_atlas`/`object`/`ui`/`portrait`/`background`/`audio`/`font` | always | How the asset is consumed. `iso_tile` (T17.12, release 1.5) is one tile of an isometric pack, a picture a tile: it is a tile of the tile set `iso` of a project with `projection: isometric` and fills the roles a sheet of tiles fills in a top-down one (T17.13); a top-down project uses nothing whose `projection` is `isometric` (no such tile, object or car), and an isometric project fills no role from a sheet of square tiles (`usage: tiles`). `iso_atlas` (T17.13) is a picture rpggen packed the tiles of an isometric pack into: the source of that tile set, of the pack `rpggen_iso`, with the role `NONE`; nobody chooses it. `growth_strip` (T17.01, release 1.5) is a crop's stages in one row of `frame` cells: not an animation, and nothing to the kinds before the farm. |
| `grid` | Grid | usage=tiles or sprite sheet | |
| `tileset` | string | usage=tiles | Name of the TileSetDef this sheet belongs to. |
| `collision` | CollisionSpec | usage=tiles/object | Default for the whole sheet. |
| `tile_overrides` | object keyed `"x,y"` | usage=tiles | Per-tile `{collision?, terrain?, custom?, skip?}`. |
| `animations` | object name→AnimSpec | usage=sprite | |
| `frame` | vec2i | usage=sprite | Frame size in px. |
| `origin` | vec2i | usage=sprite/object | Pixel inside a frame/object that becomes the node origin (the feet). |
| `directions` | int 1/4/8 | usage=sprite | |
| `headings` | int 4/8/12/16/24/32 | usage=sprite | A **rotation sheet** (T16.02, release 1.4): one object in this many views in one row of `frame` cells, each turned by 360/N from the one before; it has no `animations`. The older kinds show its first view. |
| `stages` | int ≥ 2 | usage=growth_strip | How many stages a **growth strip** has (T17.01): the cells of its row in order, the last the ripe one. It has no `animations`. How many days a stage takes is not in a pack: the farm's plan gives it. |
| `heading_order` | `up_cw`, `up_ccw`, `right_cw`, `right_ccw` | with `headings` | The way the first view points (its long side: up or right) and the way the views turn from it. |
| `heading_files` | array of string | a rotation sheet put together from files | The pictures of a vehicle that a pack has as one file a heading (`taxi_N.png`, `taxi_NE.png`, ... or `boat_0.png` to `_7`; T17.12), as paths inside the pack in the order of the sheet's cells. The asset's picture is the strip rpggen made of them (`generated/frame_strips/`), first view up and clockwise from there; four headings (`4`) come only from such files. Detected facet only. |
| `projection` | `isometric` | a picture of an isometric pack | The pack draws its world at an angle, on diamonds (T17.12). Absent everywhere else: top-down and side-view art have no key. |
| `canvas` | vec2i | with `projection` | The size of the picture the tile or the object was drawn in. The pictures of a pack share one, or one width. |
| `footprint` | vec2i | with `projection` | The diamond a tile of the pack stands on, in px: the pack's, the same on all its pictures. Never assumed to be twice as wide as high (180 x 104, 120 x 69, 132 x 66). Where it came from is in the pack's warning `isometric:<w>x<h>:<source>` with the source `tiled` (the pack's Tiled settings or an isometric Tiled map of it), `tile_information` (the width from a `Tile information.txt`, whose *Tile size* is the diamond with the side of its block under it; the height measured) or `measured` (from the pack's flat tiles). |
| `origin` | vec2i | with `projection` | The middle of the diamond inside the picture: what lies on the middle of a cell. (For a sprite it is the feet, as above; of an isometric object the two are one point.) |
| `rise` | int >= 0 | with `projection` | How many px the picture goes above the top corner of its diamond: 0 for a flat tile, more for a block, a wall, a tree. The diamond is the top of the pack's usual ground tile. |
| `turn` | int 0-7 | with `projection` | Which turn of one thing the picture is, of four or eight (`roadTile_001_0` to `_3`; `cornDouble_N`, `_E`, `_S`, `_W` are 0 to 3, going round clockwise from N). The turns of one thing are one group: every one has the tag `turn:<n>` and every one but the first `variant_of:<id of the first>`, as colour variants have. |
| `joins` | array of `n`/`e`/`s`/`w` | with `projection` | The sides of its diamond a tile joins on, as its name says them (`beachCornerES`: `[e, s]`; `roadNS`; `waterW`), in the order n, e, s, w. Read only when several files share the name before the capitals. |
| `stands_on` | `[columns, rows]` | an isometric object | How many diamonds a picture that is no tile stands on, guessed from how wide its base is: `[1, 1]` for a tree or a sign, more for a wide thing. On a map the object's `origin` lies on the middle of the cell of those nearest the camera (the highest x and y), and the cells are the ones up and back from it (T17.14): it blocks them, a building's door cell is the one in front of the middle of its south side (`[(columns - 1) // 2, rows]` from its top-left cell), and an object of several cells is drawn in two halves that meet at its origin's x and sort apart. |
| `character_index` | int | RPG Maker multi-character sheets | Which 3×4 block (0–7). |
| `ysort` | bool | object/sprite | Default true. |
| `audio` | `{ "type": "music"/"sfx", "loop": bool, "duration_s"?: number, "loop_start_ms"?: int, "loop_end_ms"?: int }` | usage=audio | `duration_s` is read from the file (WAV, OGG, MP3, FLAC) when it can be; optional. `loop_start_ms` and `loop_end_ms` (T13.17, optional, set on the Audit page) are where a looping track jumps back to and from; without them it loops as a whole. An override may set a part of `audio` (it merges) and `null` takes a loop point away. |
| `nine_slice` | `[left, top, right, bottom]` | usage=ui | Margins in px. |
| `import` | `{ "filter": "nearest"/"linear", "mipmaps": bool }` | images | Defaults: nearest, false. |
| `tags` | array of string | any | Free tags such as `chest` or `door`, used for template selection (T4.03). Side-view tags detected from folder and file words (T14.02), read by the `metroidvania` archetype only: `platform`, `one_way`, `ladder`, `hazard`, `save_point`, `ability`, and `parallax:<n>` on a background (1 is the farthest layer). Farm tags detected the same way (T17.01), read by the `farm` archetype only: `crop`, `seed`, `soil`, `watered`, `tool`, `animal`, `product`, `coop`, `barn`, `fence`, `bin`, `weather` (an overlay, never on a tile sheet), `fish`, `forage`, `growth`, and `season:<name>` (`spring`, `summer`, `autumn`, `winter`; *fall* is read as `autumn`). Sheets of one pack, size and usage that differ only by their season are one group, as colour variants are: every member has its `season:` tag and every one but the first `variant_of:<id of the first>`. |
| `derived_from` | string | a recolour variant | The id of the asset a variant was recoloured from (T13.18); detected facet only. |
| `size` | vec2i | every image asset | Pixel size of the image file (T2.14); a change on a tile sheet used by a tileset raises CONFLICT. |
| `region` | `[x, y, w, h]` | usage=portrait | Pixel rect of one face inside a face sheet (T2.11). |
| `terrain_proposal` | object | usage=tiles | Blob/corner terrain recognized on a sheet (T8.06c): `{layout, confidence, mode, terrain_set, tile_overrides}`; `layout` is `blob47_godot_12x4` (Godot's 3x3 minimal template, M16), `blob47_12x4` (the masks in ascending order), `corners16_4x4`, `corners16_drawn_4x4` (T17.01: the 16 corner tiles in the order the sheet has them, read off which corners of each tile are drawn; for art over nothing only), or `sides16_godot_12x4` (T17.01: a fence sheet, tiles that join at their sides only, in the cells of Godot's template; `mode` is `sides` and only one tile for each of the 16 combinations of sides gets a terrain). Not applied until the user accepts it in the audit's Terrain tab, which moves `tile_overrides` into the overrides and sets the override `terrain_proposal` to null. |

**Role** enum: `GROUND, WALL, CLIFF, WATER, ROAD, AUTOTILE, DECORATION, BUILDING, INTERIOR, PLAYER, NPC, ENEMY, BOSS, WEAPON, ITEM, EFFECT, PROJECTILE, UI, PORTRAIT, BACKGROUND, AUDIO_MUSIC, AUDIO_SFX, FONT, NONE`. From release 1.4 (M16) also `VEHICLE` (the player's car), `EXPLOSION`, `POWERUP` (what the player picks up to get stronger; `ITEM` stays for chests and coins) and `HAZARD` (asteroids, tyres, oil, spikes); they are labels in the audit and rows on the Mapping page in every kind. An asset of the pack `rpggen_arcade_kit` (`generated/arcade_kit/`, `detected_by: "placeholder"`) is a stand-in rpggen drew for an arcade kind; like the side-view kit it is made again on every run. From release 1.5 (M17) also `CROP` (a growth strip, or a crop of one picture), `ANIMAL` (a farm animal that is kept; `NPC` stays for people and `ENEMY` for what fights) and `TOOL` (the icon of a hoe, a watering can and the like), labels in the audit and rows on the Mapping page in every kind like those of M16. Detection gives `CROP` to every growth strip, and in a pack whose view is `farm` to a crop of one picture, `ANIMAL` to an animated sprite tagged `animal`, `TOOL` to a picture without animation tagged `tool`, and `EFFECT` to an animated overlay tagged `weather`; a pack of another view gets none of them. An asset of the pack `rpggen_farm_kit` (`generated/farm_kit/`, `detected_by: "placeholder"`, tag `farm_kit`) is a stand-in rpggen drew for a farm (T17.02), made again on every run: `turnip`, `carrot` and `berry` (growth strips of five stages, `CROP`, drawn when fewer than two crops of the packs can grow), `soil` and `watered` (one tile each, usage `tiles`, role `DECORATION`, tags `soil` / `watered`), `hoe`, `watering_can`, `sickle` and `axe` (`TOOL`, tag `tool`), `seed_bag` and `egg` (`ITEM`, tags `seed` / `product`), `hen` (`ANIMAL`, four frames of walk in the rows down, left, right, up), `shipping_bin` and `bed` (`DECORATION`, tags `bin` / `bed`), `rain` (`EFFECT`, tag `weather`, three frames of four tiles a side); the single pictures with a role the top-down recipes place by themselves (`ITEM`, `DECORATION`) have the usage `object`, so that only the farm's recipes place them. `rpggen_farm_kit.grown.<name>` (`generated/farm_kit/grown/`, tag `grown_from:<asset id>`) is the growth strip of a crop the packs have as one picture: four drawn stages, then the picture as the ripe one.

**Grid:** `{ "cell": vec2i, "margin": vec2i, "separation": vec2i }`. Columns are `floor((w - 2*margin.x + separation.x) / (cell.x + separation.x))`; rows are computed the same way with y. The margin applies to the left and top. A right/bottom remainder is allowed and ignored.

**CollisionSpec:** `{ "profile": Profile, "polygon": [[x,y],…]? }`.
* Profile is one of `NONE, FULL, BOTTOM_HALF, BOTTOM_EDGE, TOP_EDGE, LEFT_EDGE, RIGHT_EDGE, ALPHA_POLYGON, CUSTOM, ONE_WAY, LADDER`.
* `ONE_WAY` and `LADDER` (T14.02, release 1.2) are side-view values for `tiles` assets: a platform the player jumps through from below and drops through with down + jump, and a tile to climb that blocks nothing. Only the `metroidvania` archetype reads them (its TileSet gets a one-way physics layer and the custom data `ladder`); `turn_based` and `arpg` treat both as `NONE`, so a top-down project's TileSet is the same with either.
* `polygon` is required for `CUSTOM`. Its coordinates are pixels relative to the **top-left** of the cell or object. The builder converts them to Godot's tile-centered space (T1.07).

**AnimSpec:**
```json
{ "frames": [[col, row], …], "fps": 8.0, "loop": true,
  "durations": [1.0, 1.0, …]?, "flip_h": false, "active_frames": [2, 3]? ,
  "source": "assets/packs/…/hero_walk.png"? }
```
* `frames` are grid cells in the asset's own sheet, or in `source` when the animation comes from another file (per-file strips).
* `durations` are relative multipliers. Godot `SpriteFrames` frame duration is relative too.
* `flip_h: true` means "use the referenced frames mirrored". The runtime sets `AnimatedSprite2D.flip_h` while playing this animation; the recipe records it in SpriteFrames metadata (T1.07).
* `active_frames` are the frame indices where an attack hitbox is live (ARPG).
* `rects` (optional, T2.10) are explicit pixel rects `[x, y, w, h]` per frame; they take precedence over `frames` (used for non-grid sheets such as Aseprite exports). `offsets` (optional) are `[ox, oy]` per frame: the trim offset inside the untrimmed frame (`frame` facet), applied as `AtlasTexture.margin`.
* `tile_overrides["x,y"].anim` (T2.09) is `{ "frames": [[x,y],…], "durations_ms": [..] }`; M8 turns it into an animated tile.

Standard animation names: `idle_down, idle_up, idle_left, idle_right, walk_*, attack_*, hurt_*, death`. No other names are generated automatically. Users may add more through overrides.

### 4.5 SheetObject (object cutter output)

```json
{ "id": "forest_pack.tilesets.town#house_red", "sheet": "forest_pack.tilesets.town",
  "name": "House (red)", "role": "BUILDING", "region": [0, 64, 80, 64],
  "origin": [40, 63], "footprint": [0, 40, 80, 24],
  "collision": { "profile": "CUSTOM", "polygon": [[0,40],[80,40],[80,64],[0,64]] },
  "tags": ["door"], "door": [36, 63]?, "status": "CONFIRMED", "source": "user"|"auto"|"tiled" }
```

* `footprint` is the rectangle (in object pixels) that blocks movement. The default is the bottom 30% of the region at full width.
* `door` is the point where the player exits after leaving an interior and where the entrance trigger sits.

### 4.6 TileSetDef

```json
{ "name": "overworld", "tile_size": [16, 16],
  "sources": [ { "asset": "forest_pack.tilesets.grass", "source_id": 0 } ],
  "terrain_sets": [ { "name": "ground", "mode": "corners_and_sides",
                      "terrains": [ { "name": "grass", "color": "#4caf50" } ] } ],
  "physics_layers": [ { "name": "world", "layer_bits": 1, "mask_bits": 0 } ],
  "custom_data": [ { "name": "asset_id", "type": "string" },
                   { "name": "footstep", "type": "string" },
                   { "name": "move_cost", "type": "float" } ],
  "navigation": false,
  "patterns_from_objects": true }
```

* The `mode` enum is `corners_and_sides`, `corners` or `sides`. These map to `TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES`, `TileSet.TERRAIN_MODE_MATCH_CORNERS` and `TileSet.TERRAIN_MODE_MATCH_SIDES`. ⚠ VERIFY the enum names.
* TileSet assignment rules (T2.14): one TileSetDef per distinct tile size. A sheet whose role is INTERIOR goes into a separate `interior` set of the same size. Names are `overworld`, `overworld_32`, `interior`, `interior_32` and so on.
* **The tile set of an isometric project** (T17.13, release 1.5) is one more definition, `iso`, which only a project with `projection: isometric` has. It carries two keys no other definition has:

  ```json
  { "name": "iso", "tile_size": [180, 104], "projection": "isometric",
    "sources": [ { "asset": "rpggen_iso.roads_0", "source_id": 0 } ],
    "tiles": { "roads.png.roadtile_001_0": { "source": 0, "coords": [0, 0], "at": [0, 0],
                                             "of": "roads.png.roadtile_001_0" } },
    "custom_data": [ …the three above…, { "name": "tillable", "type": "bool" },
                     { "name": "water", "type": "bool" } ],
    "patterns_from_objects": false, … }
  ```

  `tile_size` is the diamond of the project's ground (the footprint of the tile chosen as `starter.ground`, else of the first isometric ground tile; once the definition exists, its own: maps are painted with it), never assumed 2:1. `sources` are the atlas pictures rpggen packs the single tiles into (assets of the pack `rpggen_iso`, usage `iso_atlas`, in `generated/iso_atlases/<pack>_<n>.png`; each has `grid.cell`, the atlas cell, which is the pack's canvas or, for a pack of one width and several heights, its largest picture). `tiles` says where every tile is: the source, the atlas `coords`, and `at`, where the picture's top left lies in its cell (a picture stands on the bottom of its cell, in the middle); `of` is the id of the first turn of the tile's own set when the picture is one of several turns (a tile in two colours is two sets). Isometric tiles on another diamond than the project's are in no tile set (`TILE-012`). The builder gives the Godot TileSet the isometric shape with the layout *diamond down*, and every tile the texture origin `origin + at - cell / 2` (the catalog's `origin` is the middle of its diamond in its picture).

### 4.7 id_allocations

```json
{ "tilesets": { "overworld": { "next_source_id": 3, "retired": [1] } },
  "entities": { "starter_map": { "npc": 2, "enemy": 1, "chest": 1 } } }
```

* `source_id` values are **never reused**. `allocate_source_id(tileset)` returns `next_source_id` and increments it.
* Removing a source moves its id into `retired`.
* Python is the only writer of `tilesets`. The editor dock (M8) is the only writer of `entities`.
* `iso_atlases` (T17.13, release 1.5; only in the catalog of an isometric project) keeps the cell of every isometric tile, so that **no painted cell moves when the project is generated again**:

  ```json
  { "iso_atlases": { "roads": { "cell": [180, 184], "columns": 8, "rows": 8, "next_cell": 97,
                                "cells": { "roads.png.roadtile_001_0": 0, "roads.png.roadtile_001_1": 1 },
                                "sources": [0, 1] } } }
  ```

  One record a pack. `cells` gives every tile that was ever placed its number, in the order of the ids at the time it was placed: a new tile gets `next_cell`, a tile that left the pack keeps its number (its cell stays empty, and is given to nobody). Tile `n` lies in picture `n // (columns * rows)`, at column `n % columns` and row `(n // columns) % rows` of it; `columns` and `rows` are fixed when the pack's first tile is placed (at most 8 by 8 and about 2048 px a side), and `sources[i]` is the source id of picture `i` in the tile set `iso` (allocated from `tilesets.iso`, never reused). `cell` only ever grows; a picture grows downwards by rows and never shrinks.

### 4.8 FolderRule

```json
{ "pack_id": "forest_pack", "glob": "Characters/Enemies/**", "set": { "role": "ENEMY" } }
```

Rules are applied in order after detection and before overrides. They write into a separate `rule` layer, so effective = detected ← rule ← overrides. A matching rule's facet keys replace detected keys. Matching uses `PurePosixPath.full_match` semantics (Python 3.13), or an equivalent helper `paths.glob_match` implemented for 3.12. ⚠ VERIFY your Python version and implement the helper with tests.

### 4.9 Map (T12.49)

Python reads `.tmx`/`.tmj` (Tiled) and `.ldtk` (LDtk, one map per level); Godot builds them
(`builder/recipes/imported_maps_recipe.gd`).

```json
{ "id": "tiled_map.maps.town", "pack_id": "tiled_map", "source": "assets/packs/tiled_map/maps/town.tmx",
  "format": "tiled", "tile_size": [16, 16], "size": [6, 4],
  "layers": [
    { "name": "Ground", "kind": "tiles", "tileset": "overworld", "cells": [[8, 0, 0, 0, 0], [2, 0, 1, 2, 0]] },
    { "name": "Collisions", "kind": "intgrid", "cells": [[7, 1], [2, 0]],
      "values": [{ "value": 1, "name": "wall", "solid": true }] },
    { "name": "spawn", "kind": "objects",
      "objects": [{ "name": "start", "type": "spawn", "x": 24, "y": 40, "w": 0, "h": 0, "props": {} }] } ] }
```

* `id` is the pack id and the dotted path of the file (`<pack>.maps.town`); an LDtk level adds its
  identifier (`<pack>.world.level_0`). `size` is in cells. Layers are listed bottom first.
* `tiles` layers: `cells` is run-length encoded over the cells row by row (`width * height` in
  all), each run `[count, source_id, column, row, transform]`. `source_id` -1 is an empty cell.
  `transform` holds the flips: 1 = flip x, 2 = flip y, 4 = transpose (Tiled's diagonal flip). Godot
  keeps them in the alternative-tile bits of the cell, so the TileSet needs no extra tiles.
  `tileset` names the generated TileSet (`generated/tilesets/<tileset>.tres`); a layer with tiles of
  several tile sets becomes one layer per tile set, named `Layer (tileset)`.
* `intgrid` layers (LDtk): runs `[count, value]`. `values` lists the values the layer uses; the
  `solid` ones become collision. `solid` starts as true for a value named wall, solid or collision
  (or for every value of a layer with such a name when no value is named) and is kept across
  regenerations, so a change in the catalog stays.
* `objects` layers: only the objects that are markers. `type` is `spawn`, `door` or `sign`, taken
  from the layer name (Tiled), the object's type or class, or the entity identifier (LDtk).
  `x`/`y`/`w`/`h` are pixels from the top left of the map. `props` are the Tiled properties or LDtk
  fields (`target_map`, `target_spawn` for a door, `text` for a sign).
* Tiled tile data may be CSV, base64, base64 + zlib or base64 + gzip. Zstandard cannot be read: the
  layer is skipped with TILE-009. An infinite map is flattened to the bounds of its tiles. Only
  orthogonal maps are read. A layer whose tile sheet is not part of a tile set is skipped with
  TILE-009 too.

---

## 5. `ownership_ledger.json` (ledger_version 1)

```json
{
  "ledger_version": 1,
  "generator_version": "0.1.0",
  "files": {
    "generated/scenes/actors/player.tscn": { "sha256": "…", "written_by": "player_recipe", "owner": "generated" },
    "game/maps/starter_map.tscn": { "sha256": "…", "written_by": "starter_map_recipe", "owner": "user_seed" }
  },
  "deleted_by_user": ["generated/scenes/objects/old_sign.tscn"]
}
```

* `owner` is either `generated` (may be rewritten) or `user_seed` (written once, then never touched).
* `declined_sha256` (optional, T12.58): the hash of a generated version the user declined with
  *Keep mine*. Promotion skips the conflict while the new content has this hash.
* Keys are posix_rel paths, sorted.
* Covered paths (T5.01): `generated/`, `addons/rpg_runtime/`, `addons/rpg_project_tools/`, `rpggen/` (except `rpggen/logs/`, `rpggen/results/`, the ledger itself and `rpggen/generation_report.json`), `assets/packs/`, `game/` (as `user_seed`), `project.godot`, `.gitignore`, `.gitattributes` and `README.md`. `GENERATION_REPORT.md` is not covered: it is rewritten after promotion.
* `project.godot`, `rpggen/generator_config.json` and `rpggen/asset_catalog.json` are merge-managed: they never produce a conflict.
* Hashes cover the file bytes **after** CRLF→LF normalization for text files (`.gd`, `.tscn`, `.tres`, `.json`, `.cfg`, `.godot`, `.md`, `.import`, `.uid`). Binary files are hashed raw. This avoids false conflicts when git rewrites line endings.

---

## 6. `build_results.json`, `validation_results.json`, `smoke_results.json`

All three files share this shape:

```json
{
  "results_version": 1,
  "phase": "build" | "validate" | "smoke",
  "ok": true,
  "started_ms": 0, "elapsed_ms": 18234,
  "issues": [ { "code": "TILE-003", "severity": "warning", "message": "…", "file": "…" } ],
  "items": [ … phase-specific … ]
}
```

`started_ms` is always 0 to keep the output deterministic. Only `elapsed_ms` varies, and diff checks ignore that field.

* Build `items`: `{ "recipe": "tileset_recipe", "output": "generated/tilesets/overworld.tres", "action": "written"|"skipped"|"merged"|"failed" }`.
* Validate `items`: `{ "check": "resource_load", "target": "…", "ok": bool }`.
* Smoke `items`: `{ "step": 3, "name": "npc_dialogue", "ok": bool, "ms": 412, "detail": "…" }`.

`ok` is false if any issue has `severity == "error"`.

---

## 7. Pack profile (`*.rpgprofile.json`, profile_version 1)

```json
{
  "profile_version": 1,
  "profile_id": "vendor_forest_v2",
  "title": "Forest Pack v2 by Vendor",
  "fingerprint": { "required_files": { "Tilesets/grass.png": "<sha256>", "Characters/hero.png": "<sha256>" },
                   "min_match": 0.8 },
  "assets": { "Tilesets/grass.png": { …partial Facets… } },
  "objects": [ …SheetObject without "id", with "sheet_path" instead of "sheet"… ],
  "folder_rules": [ … ],
  "tilesets": [ …TileSetDef without source_id values… ],
  "author": "github-username", "license": "CC0-1.0"
}
```

* A profile matches when the fraction of `required_files` present with an identical hash is at least `min_match`.
* `required_files` holds up to 20 files, chosen as the largest images.
* Profiles never contain image data.
* The partial Facets of an asset may have `headings` and `heading_order` (T16.17): a profile
  of a pack with a vehicle in N headings says so, as the catalog does (T16.02).

---

## 8. `build_state.json`

```json
{ "build_state_version": 1, "outputs": { "generated/tilesets/overworld.tres": "<input_hash>" } }
```

---

## 9. Save game (runtime, `user://saves/slot_<n>.json`, save_version 1)

```json
{
  "save_version": 1,
  "checksum": "<sha256 hex of the canonical JSON of everything except 'checksum'>",
  "header": { "slot": 1, "map": "starter_map", "playtime_s": 512, "level": 3, "saved_at_unix": 1760000000 },
  "player": { "actor_id": "hero", "stats": { "level": 3, "experience": 40, "hp": 18, "max_hp": 24 } },
  "party": [],
  "inventory": [ { "item_id": "potion", "qty": 3 } ],
  "gold": 120,
  "world": { "map": "starter_map", "spawn_id": "", "position": [128.0, 96.0], "facing": "down" },
  "flags": { "starter_map_chest_001": { "opened": true } },
  "quests": {},
  "settings_snapshot_version": 1
}
```

* Canonical JSON for the checksum: `JSON.stringify(data_without_checksum, "", true)`, where the third argument sorts keys. ⚠ VERIFY the signature of `JSON.stringify` in 4.7 (`data, indent, sort_keys, full_precision`).
* Vectors are always stored as `[x, y]` arrays.
* Three optional keys of a metroidvania (release 1.2), each **written only when it holds
  something**, so the save of a top-down game is byte for byte what 1.1 wrote and `save_version`
  stays 1: `abilities` (array of ability ids, T14.05), `broken_cells`
  (`{ "<room id>": [[x, y], ...] }`: the breakable blocks that were broken, T14.05) and `room_fog`
  (`{ "<room id>": true }`: the rooms that are on the room map, T14.08). A reader ignores entries
  it cannot use. The place a defeated player returns to is kept in `flags` (`respawn.map`,
  `respawn.x`, `respawn.y`), set by resting at a save station.
* The run of an arcade game (release 1.4, T16.01) is kept in `flags` too, as the entry
  `arcade`: `{ "stage": <index>, "lives": <n>, "score": <n>, "weapon": "<id>" }`, written when a
  stage is entered and taken away when the run ends. No other kind writes it.
* A farm (release 1.5, T17.04 and T17.05) keeps what it has to remember in `flags`, so its save
  has no key of its own: the entry `farm` is `{ "energy": 0..100, "held": 0..9, "water": 0..20 }`
  (the farmer's energy, the held slot of the hotbar, what is left in the watering can; a key
  that was never written has its default: rested, the first slot, a full can), and the entry
  `farm_field` has one key a field, named by the id of its map, whose value is
  `{ "<x>,<y>": { "w": bool, "crop": "<crop id or empty>", "grown": n, "dead": bool, "idle": n } }`:
  the cells that were worked (watered, what grows there, its watered nights, withered, the
  nights tilled soil has lain bare). A field grows overnight from this alone, whether its map
  is shown or not. No other kind writes either entry.
* The weather of a farm (release 1.5, T17.11) is not stored: the weather of a day follows
  from a seed and the number of the day. The entry `farm_weather` of `flags` is
  `{ "seed": n, "watered": n }`: the seed (0 to 2^31 - 1), drawn from the game's random
  numbers the first time a game's weather is asked for and kept from then on, and the day
  (counted from 0 since the first morning) whose rain has watered the fields already, so
  that loading a save of a rainy day does not water them again. Both are optional: `watered`
  is not there before the first rain, and a save without `seed` draws one when it is loaded.
* The seasonal sheets of a farm (T17.11): `generated/data/seasons.json`, rewritten on every
  build, is `{ "version": 1, "groups": { "<id of the group's first sheet>": { "<season or
  empty>": "res://<path of the texture>" } } }`: for every group of sheets the catalog has
  once a season (the `season:<name>` and `variant_of:<id>` tags of §3) the texture of each
  season, the sheet that names no season under the empty key. A group has at least two
  named seasons; a project whose packs have none has `groups: {}`. The runtime replaces
  the textures of an outdoor map that are members of a group by the group's texture of
  the season (the one under the empty key, else the first, for a season it lacks).
* One optional key of a game with a calendar (release 1.5, T17.03): `calendar`,
  `{ "minute": 915, "day": 12, "season": 2, "year": 3 }`. `minute` is the minute of the day
  counted from the midnight before its morning (360, which is 6:00, to 1559, which is 1:59 of
  the night); `day` the day of the season (1 to the game's `days_per_season`: 28, 14 or 7);
  `season` 0 to 3 (spring, summer, autumn, winter); `year` from 1. It is **written only by a
  game that has a calendar** (`RpgCalendar.current()` is not null), so the save of every other
  game has exactly the keys it had and `save_version` stays 1. A save without it loads on the
  first morning (6:00, day 1 of spring, year 1); numbers that are no date are read as the
  nearest one; a game without a calendar ignores the key.
* One optional key of a farm (release 1.5, T17.09): `friendship`,
  `{ "points": { "<person id>": n }, "met": [ "<person id>" ], "talked": [ "<person id>" ],
  "gifts": { "<person id>": n }, "known": { "<person id>": [ "<item id>" ] } }`. `points` are
  0 to 2500 (a heart every 250, ten hearts); `met` is who was talked to or given something, in
  that order (the People page lists them); `talked` who was talked to today and `gifts` the
  gifts of this week a person (a talk gives points once a day, a person takes two gifts a
  week; the calendar's `day_began` empties the first every day and the second on weekday 0);
  `known` the items that were given to a person, whose taste for them the People page shows.
  It is **written only by a game that has friendships** (`RpgFriendship.current()` is not null:
  the farm's mode makes them), so the save of every other game has exactly the keys it had and
  `save_version` stays 1. A save without it loads with nobody met; what is no number or no
  list in it is left out; a game without friendships ignores the key.

### 9.1 The shared section (`user://saves/meta.json`, meta_version 1)

What belongs to the game and not to one saved game. One file beside the slots, shared by the
three slots and the autosave, written through a temporary file and verified like a slot:

```json
{
  "meta_version": 1,
  "checksum": "<sha256 hex, as for a slot>",
  "values": {
    "high_scores": [ { "name": "ANA", "score": 48200, "stage": 3 } ]
  }
}
```

* `values.high_scores` (T16.01): the ten best runs of an arcade game, the best first; `name` is
  at most 8 characters, `stage` is the number of the stage the run ended in (from 1). Of two
  equal scores the earlier one stays in front.
* The file is optional. A game that never wrote it, every game made before 1.4 and a file
  that does not verify read an empty section; `save_version` stays 1 and no slot refers to it.
  Deleting a slot leaves it alone.
* `SaveManager.read_shared()`, `shared_value(key, fallback)` and `set_shared_value(key, value)`
  are the only readers and writers.

---

## 10. Fields added by later task cards

Several task cards extend these schemas. Each card that adds a field must update both this document and the JSON Schema file in the same commit. The full list:

| Field | Where | Added by |
|-------|-------|----------|
| `rects`, `offsets` | AnimSpec | T2.10 |
| `region` | Facets (portraits cut from face sheets) | T2.11 |
| `renamed_from` | Asset | T5.05 |
| `remove_source` | Facets (override only) | T5.04 |
| `starter` | generator_config | T3.11 |
| `demo_removed` | ownership_ledger | T8.08 |
| `declined_sha256` (file entries) | ownership_ledger | T12.58 |
| `anim`, `terrain.peering` | `tile_overrides` entries | T2.09, T8.06 |
| `terrain_proposal` | Facets | T8.06 |
| `terrain: {set, terrain, peering}` replaces `terrain.wangid` | `tile_overrides` entries | T8.06 |
| `maps` | asset_catalog | T12.49 |
| `imported_maps` | generator_config | T12.49 |
| `export_targets` | generator_config | T12.52 |
| `starter_map.rooms`, `room_size`, `abilities`, `pickups`, `added_rooms` | generator_config (metroidvania) | T14.06 |
| `starter.boss` | generator_config | T14.02 |
| `rooms` | world_plan | T14.06 |
| `abilities`, `broken_cells`, `room_fog` | save game | T14.05, T14.08 |
| `summary.map.world`, `summary.map.rooms`; repair kind `exit` | command-line documents | T14.10, T14.06 |
| `assets.<file>.headings`, `heading_order` | pack profile | T16.17 |
| `starter.vehicle`, `starter.projectile`, `starter.explosion` | generator_config | T16.03, T16.17 |
| `summary.map.stages`; `summary.archetype` takes `shmup`, `run_and_gun`, `racing` | command-line documents | T16.16 |
| `calendar` | save game | T17.03 |
| `archetype` takes `farm`; the input actions `use`, `next_item`, `prev_item`, `hotbar_1` to `hotbar_10` | generator_config | T17.04 |
| `farm` | world_plan | T17.05 |
| `farm.map` | world_plan | T17.06 |
| `flags.farm` (`energy`, `held`, `water`), `flags.farm_field` | save game | T17.04, T17.05 |
| `flags.farm.save_slot`, `flags.farm_bin` (`items`: rows `{ item_id, qty }`), `flags.farm_bed` (`map`, `x`, `y`, `facing`, `known`) | save game | T17.08 |
| `starter_map.starting_money`, `starter_map.pass_out_loss` | generator_config (farm) | T17.08 |
| `starter_map.farm_size`, `starter_map.plot`, `starter_map.animals`, `starter_map.added_maps` (and `difficulty` for a farm) | generator_config (farm) | T17.06 |
| `farm.people` | world_plan | T17.09 |
| `friendship` | save game | T17.09 |
| `flags.farm_weather` (`seed`, `watered`) | save game | T17.11 |
| `generated/data/seasons.json` (`version`, `groups`) | generated data (farm) | T17.11 |
| `starter_map.fishing` | generator_config (farm) | T17.10 |
| `starter_map.days_per_season`, `starter_map.day_length` | generator_config (farm) | T17.16 |
| `summary.map.farm` (a planned farm in words; the map of `summary.map` is then its village) | command-line documents | T17.16 |
| `farm.forage` | world_plan | T17.10 |
| `starter_map.festivals` | generator_config (farm) | T17.25 |
| `farm.events`; `birthday` of a Person of `farm.people` | world_plan | T17.25 |
| `game/data/events.json`, `generated/data/events.json` (`events`); `birthday` of a person of `people.json` | game data (farm) | T17.25 |
| `flags.farm_events` (`added`, `today`, `birthday_gifts`), `flags.farm_bin.shipped` (`season`, `items`) | save game | T17.25 |
| the condition atoms `birthday:<id>`, `festival`, `festival_tomorrow`, `event:<kind>` | dialogue (false in a game without festivals) | T17.25 |
| `farm.map.trails`, `farm.map.added` (the maps added to a farm); `kind` of a row of `starter_map.added_maps`; `maps` of a thing to forage, `water: ["sea"]` of a fish | world_plan, generator_config (farm), game data (farm) | T17.23 |
| `flags.farm_forage` (`picked`: `{ day, spots: { map: [place] } }`), `flags.farm_fishing` (`casts`) | save game | T17.10 |
| `game/data/forage.json`, `generated/data/forage.json` (`forage`, `fish`; the generated one also `spots`, `map`, `fishing`) | game data (farm) | T17.10 |
| the tags `use_anim:<tool>`, `of:<asset id>` and `unused_because:use_anim` | asset_catalog | T17.10 |
| `projection`, `canvas`, `footprint`, `rise`, `turn`, `joins`, `stands_on`, `heading_files`; the usage `iso_tile`; `headings` takes 4 | Facets, pack profile | T17.12 |
| the tags `turn:<n>`, `slope:up` / `slope:down`, `unused_because:other_view`, `unused_because:atlas_copy`, `unused_because:slope`; the pack warnings `view:isometric` and `isometric:<w>x<h>:<source>` | asset_catalog | T17.12 |
| `projection` (`top_down` / `isometric`) | generator_config | T17.13 |
| the usage `iso_atlas`; `projection` and `tiles` of a TileSetDef; `id_allocations.iso_atlases`; the pack `rpggen_iso` | asset_catalog (an isometric project's) | T17.13 |
| `iso_controls` (`screen` / `grid`) | generator_config | T17.14 |
| the pack `rpggen_iso_kit` with `rpggen_iso_kit.hero`, `.villager`, `.enemy` (roles PLAYER, NPC, ENEMY; tag `iso_kit`; `generated/iso_kit/*.png`) | asset_catalog (an isometric project whose packs lack the role) | T17.14 |
| `projection` (`isometric`), `sources.<id>.origins` and `entities[].more` of `rpggen/results/starter_map_cells.json`; the metadata `isometric` of a minimap texture | results, generated (an isometric project's) | T17.14 |
| `projection: isometric` is accepted for `racing`; the node `View` (`footprint`, `cell_px`, `origin`) of a track's scene; `base_zoom` of its camera | generator_config, generated (an isometric race's) | T17.15 |

---

## 11. Command-line documents (`--json`, json_version 1)

`rpggen generate|analyze|restore|diagnose|repair-world --json` prints **one** JSON document on stdout; every
human line goes to stderr. The schema is `rpggen/schema/cli.schema.json`. The document is not a
file in a project: it is the answer to one command, so it is written with `json.dumps(indent=2)`
and its keys are in the order below, not sorted. Every document starts with the envelope:

```json
{ "json_version": 1, "command": "generate", "ok": false, "exit_code": 1, … }
```

* `ok` is `exit_code == 0`. The exit codes are the same for every command:

  | Code | Meaning |
  |-----:|---------|
  | 0 | OK |
  | 1 | Generation failed (`BUILD`, `VAL`, `SMOKE`, `REGEN` or `TILE` errors) |
  | 2 | Usage error |
  | 3 | Environment or input (`ENV`, `ARCH`, `CAT`, `ASSET`, `ADAPT` errors) |
  | 4 | Cancelled with Ctrl+C (the work folder is discarded) |
  | 70 | Internal error (`BUILD-005`) |

  For a run that failed, the first error decides between 1 and 3; `BUILD-005` anywhere makes it 70.
* A **usage error** (2), a **cancel** that no running command noticed (4) and an **internal error**
  outside a generation (70) are `{ envelope…, "error": "<one sentence>" }` and nothing else.
  A mistake that `argparse` finds (an unknown option) exits with 2 and prints no document.
* `issue` is `{ "code", "severity", "message", "fix", "file" }`. `file` is always there: a
  `posix_rel` path, or `null`.

### 11.1 `generate`

```json
{
  "json_version": 1, "command": "generate", "ok": true, "exit_code": 0,
  "target": "C:/games/demo",
  "dry_run": false,
  "cancelled": false,
  "run_id": "0123abcd",
  "failed_phase": null,
  "failed_staging": null,
  "skipped": { "export": "ENV-010" },
  "timings": { "preflight": 0.4, "build": 12.5 },
  "issues": [ { "code": "ASSET-010", "severity": "warning", "message": "…", "fix": "…", "file": null } ]
}
```

* `failed_phase` is the phase that stopped the run (`PHASES_M1` names; a dry run uses
  `preflight`, `catalog` and `plan`). `failed_staging` is the kept work folder
  (`.rpggen_failed`) of a failed run. `skipped` maps a check that did not run to the code of
  the note that says why (T12.07). `timings` are seconds per phase; they vary from run to run
  and are never written to a project file. `run_id` is the eight hex characters that mark the
  run's lines in the application log (empty for a dry run).
* `cancelled` is true for exit code 4.
* With `--dry-run`, `dry_run` is true, nothing was made, and the document has a `summary`
  (it is `{}` when preflight already stopped the run):

```json
"summary": {
  "project_name": "forest", "archetype": "turn_based", "regeneration": false,
  "godot": null,
  "packs": ["forest"],
  "tile_size": 16, "tile_size_from": "packs", "resolution": [640, 360],
  "assets": 51, "objects": 2, "tilesets": 1,
  "roles": { "GROUND": { "count": 3, "need": "required" } },
  "placeholders": ["PLAYER"],
  "map": { "size": [40, 24],
           "counts": { "buildings": 1, "npcs": 1, "enemies": 1, "chests": 1, "decorations": 8 },
           "warnings": [] }
}
```

  `tile_size_from` is `packs` when the size was read from the packs (`--pack` without
  `--tile-size`) and `config` otherwise. `roles` lists every required and recommended role and
  every other role that has an asset; `need` is `required`, `recommended` or `optional`.
  `placeholders` are the roles `--placeholder` would fill (those that have no asset).
  `map` is present when the requirement check passed. `godot` is the executable that was found
  (never started), or `null`. For an arcade kind (M16) `map` has `size` `[0, 0]`, counts of 0
  and `stages`: the plan a first run would make, in words (`3 stages, 24 waves, 3 bosses`;
  `4 tracks of 3 laps, 3 rivals`), or `""` when the options make no plan (`warnings` then
  says why).

### 11.2 `analyze`

`mode` tells the three shapes apart:

* `"pack"`: `pack`, `assets` (the table as data: `id`, `path`, `usage`, `role`, `grid`,
  `frame`, `confidence`, `status`), `objects` and `tilesets` (counts), `catalog_file` (the `--out`
  file or `null`), `issues` and, with `--expected`, `accuracy` (`groups`, `correct`, `total`,
  `misses`).
* `"corpus"`: `report` (the file written), `passed`, `failures`, `groups`, `thresholds`. The exit
  code is 1 when a threshold is missed.
* `"private_corpus"`: `report` and `summary` (the content of the written report).

An error (`ARCH-*` and so on) is `{ envelope…, "issues": [ … ] }` with exit code 3 (or 1).

### 11.3 `restore`, `diagnose` and `repair-world`

* `repair-world` (T13.24): `target`, `dry_run`, `repairs`, `offered` and `unfixable` (lists of
  `{ "kind": "retarget"/"spawn"/"door"/"exit"/"unfixable", "map", "node", "what" }` (`exit`: the exit of a metroidvania's room): what was written
  or, with `--dry-run`, would be; what a map the run may not write would need; and what cannot be
  mended) and `backup` (the folder name under `.rpggen_backups` the maps went to, or `null`).
  `rpggen/world_repair.json` in the project holds the last run's `repairs`, `skipped` and
  `unfixable`.
* `restore`: `target`, `backup` (the `--backup` name or `null`), `saved_state` (the folder the replaced state
  was saved to; `null` on failure) and `issues` (the error that stopped it, or `[]`).
* `diagnose`: `target` and `bundle` (the zip written).

## 12. `rpggen/world_plan.json` (world_plan_version 1, T13.20)

Written by rpggen (generated-owned) for a config with `starter_map.areas`, and read by the recipes.
It is **stored and reused**: once a map of an area other than the starter map exists, the seed and
the rows of the table no longer change it; a new row is appended and gets a door pair with the
area it joins.

| Key | Type | Notes |
|-----|------|-------|
| `world_plan_version` | int | 1 |
| `seed` | int | The seed the world was planned with. |
| `areas` | array of Area | The village first, then the rows in table order, then the rows added later. |
| `grid` | object | Area id → `[x, y]` on the world's grid. The village is `[0, 0]`, the first area `[1, 0]`. |
| `notes` | array of string | What the planner changed (a biome the packs cannot fill, a cave that is not locked). They are in the report under *World*. |
| `key` | object, optional | `{ "item", "area", "opens", "chest" }`: the key item, the area whose chest holds it, the area it opens. Only when a cave is locked. |
| `farm` | object, optional | The crops of a farm (§12.2). A farm without `starter_map.areas` has the file for this section alone: `areas` is `[]`, and its maps are those of a game without a plan. |
| `maps` | object | Area id → `{ "map_hash" }`: the ledger hash of the map rpggen built, recorded once. A map that was there before the run that would have built it has no entry: a person may have made or changed it (T13.24). |

**Area:** `id` (the slug of the name, unique; the village is `starter_map`), `name`, `biome` (what
it got), `wanted_biome` (only when it differs), `size`, `map` (`game/maps/<id>.tscn`), `ground`
(the ground asset the biome prefers, or ""), `doors`, and for every area but the village
`chests` (`{ id, cell, gold, items: [{item_id, qty}] }`), `enemies` (`{ id, cell }`),
`decorations` (cells), `decor_words`, `water` (`[x, y, w, h]`, a shore), and `gates`
(`{ id, cell, key_item, door }`). The village's inside is laid out by the starter-map planner.

**Door:** `id` (the node name, `<area>_door_<other>`), `edge` (`N`/`E`/`S`/`W`), `cell` (in the
wall), `spawn` (the floor cell in front of it, where a player arrives), `spawn_id`
(`from_<other>`), `facing`, `to` (area id), `to_map`, `to_spawn`, and `key` when it is locked. The
village's east door uses the starter map's own exit; its other doors are moved along the wall to
free floor, so their `cell` is where the plan wanted them.

### 12.1 `rooms` (a metroidvania, T14.06)

A metroidvania's plan has no areas (`areas` is `[]`); its world is the `rooms` object. `grid` and
`maps` are keyed by room id. The plan is stored and reused in the same way: once the scene of one
room exists, the options and the seed no longer change it, and a row of `starter_map.added_rooms`
appends a room.

| Key | Type | Notes |
|-----|------|-------|
| `version` | int | 1 |
| `room_size` | `[w, h]` | Tiles; every room of the first plan has this size. |
| `abilities` | array of string | The abilities of the world, in the order they are found. |
| `start`, `end` | room id | Where the game starts and where the hermit ends it. |
| `guardian` | room id or `""` | The room of the guardian, which gives the first ability. |
| `path` | array of room id | The way from `start` to `end` (the critical path). |
| `list` | array of Room | The rooms, in plan order; added rooms last. |

**Room:** `id` (`room_01`, or `room_<slug>` for an added room), `name`, `kind` (`start`,
`corridor`, `shaft`, `guardian`, `pickup`, `end`), `map` (`game/maps/rooms/<id>.tscn`), `cell`
(`[x, y]` on the world's grid; a room above another has the smaller `y`), `size`, `added` (true
for a room of `added_rooms`), `tiles`, `exits`, and what stands in it, each a **feet cell** (the
cell whose floor the thing stands on): `spawn`, `sign`, `station`, `npc`, `chest`, `enemies`,
`items`, `pickup` (`{ "ability", "cell" }`), `guardian` (`{ "cell", "grants" }`) and `gates`.

* `tiles` is the room as rows of characters, one per cell: `#` ground, `.` air, `=` a one-way
  platform, `H` a ladder, `T` the top of a ladder (a ladder with a platform on it), `^` a hazard
  and `B` a breakable block. The recipe paints exactly this; nothing about a room's shape is
  decided in GDScript.
* **Exit:** `id` (`<room>_exit_<n|e|s|w>`, also the name of its trigger and its spawn point),
  `edge`, `cell`, `to` (room id), `to_exit`, and `needs` (an ability) when the way to it is
  closed by a gate.
* **Gate:** `{ "ability", "kind", "size", "cell" }`: what the room's shape asks for. `kind` is
  `ledge` (double jump, high jump), `gap` (dash), `wall` (break blocks) or `shaft` (wall jump);
  `size` is the height or width in tiles, out of reach without the ability and within reach
  with it (and with the abilities found before it).

### 12.2 `farm` (the crops of a farm, T17.05)

Planned once by `rpggen/core/crop_plan.py` from the growth strips of the packs (usage
`growth_strip`, T17.01) and the seed, and **stored and reused**: once the section is there the
seed and the options no longer change it, and a growth strip the packs gain later is appended.

| Key | Type | Notes |
|-----|------|-------|
| `plan_version` | int | 1 |
| `seed` | int | The seed the crops were planned with. |
| `difficulty` | enum `easy`/`normal`/`hard` | How many watered nights a picture of a strip stands for (0.75, 1, 1.5). `normal` until the farm's options have the key (T17.06). |
| `crops` | array of Crop | In the order the seed gave. The first grows in spring: a new game starts with its seeds. |
| `notes` | array of string | What the planner did beside planning (the drawn crops of a pack with fewer than two). |

**Crop:** `id` (the name of the strip without its cell size and frame count, unique), `name`,
`asset` (the growth strip, or `""` for a drawn crop, which has a `color` instead), `seed` and
`produce` (item ids: `seed_<id>`, `crop_<id>`), `seasons` (of `spring`, `summer`, `autumn`,
`winter`; shared out so that every season has at least two crops), `days` (watered nights from
seed to harvest: a night a picture after the first, times the difficulty, 2 to 14), `stages`
(the pictures of the strip; the last is the ripe one), `regrow` (0, or the days to the next
harvest of a crop that grows again: every third crop of a plan), `seed_price`, `price` (one
harvest) and `energy` (what eating one restores).

**`game/data/crops.json`** (`rpggen/schema/crops.schema.json`) is what the game reads:
`{ "crops": [ Crop ] }`, a Crop as above without `asset` and `color`, with `scene` (the RpgCrop
scene, `res://generated/scenes/farm/crops/<id>.tscn`) and optionally `yield` (how many a
harvest gives, 1). The builder writes it once (it is the user's afterwards) and writes the same
to `generated/data/crops.json` on every build; the game reads the user's file and takes from
the generated one the crops the user's does not list. An entry of the user's file may instead
be `{ "id": "<crop>", "removed": true }` (the schema's `Removed`): the crop is taken away and
the generated list does not bring it back. The same entry is valid among the `animals` of
`game/data/animals.json` and in the `forage` and `fish` lists of `game/data/forage.json`, which
are filled in from their generated lists in the same way (`RpgAnimalData`, `RpgForage`), and in
`game/data/people.json`, which is read alone (`RpgFriendship`: the entry is nobody). The arcade
kinds' `game/data/stages.json` has no such entry: a stage deleted there comes back from the
generated list, as it has since M16. The picture a crop shows after `grown`
watered nights is `grown * (stages - 1) // days`, the same in `crop_plan.stage_of` and
`RpgCropData.stage_of`.

### 12.3 `farm.map` (the map of a farm, T17.06)

Planned once by `rpggen/core/farm_plan.py` from the options, the seed and what the packs say of
their buildings and their water, and **stored and reused**: once `game/maps/farm.tscn` exists
the seed and the options no longer change it. The farm's own options are keys of `starter_map`
beside the village's: `farm_size` (`small`, `medium`, `large`: a field of 32 x 24, 40 x 30 or
48 x 36 cells), `plot` (`small`, `medium`, `large`: 6 x 4, 12 x 8 or 16 x 10 cells that can be
tilled), `animals` (`none`, `coop`, `coop_and_barn`), `difficulty` (how much there is to clear)
and `added_maps` (at most 8 rows `{ "name", "kind" }`: the maps of 12.3a).

**The plan is a grid of cells and has no position on the screen.** A cell is `[x, y]`, `x` to
the east and `y` to the south, `[0, 0]` the north-west corner; a rectangle is `[x, y, w, h]`.
The same plan is painted with square tiles or with diamonds (T17.14). The outermost cells of
the field are its edge (nobody walks there) but for the way out.

| Key | Type | Notes |
|-----|------|-------|
| `plan_version` | int | 1 |
| `seed` | int | The seed the farm was asked for with (a note says when a later one made it). |
| `id`, `map` | string | `farm`, `game/maps/farm.tscn`. |
| `farm_size`, `plot`, `animals`, `difficulty` | enums | What it was planned with. `farm_size` is the field it got (a note says when the packs' buildings needed a larger one); `plot` is what was asked for. |
| `size` | `[w, h]` | The cells of the field. |
| `house` | Building | The farmhouse, in the north of the field. |
| `bin` | object | `{ "cell", "front" }`: the shipping bin against a side of the house, and the cell south of it where the farmer stands. |
| `tillable` | array of cell | The plot, cell by cell: the ground that can be tilled (the builder writes it as the tile's custom data). |
| `water` | object | `{ "kind", "cells", "fill" }`: a `pond` (several cells; the packs have water tiles) or a `well` (one cell), and the cell south of it where the can is filled. |
| `animal_houses` | array of Building | The coop, then the barn; `[]` without animals. Each has a `yard`. |
| `paths` | array of cell | Ground that is a path: from the door of the house to the way out, to the plot, the water and before every gate. The first is the door, the last the way out. Nothing lies on a path. |
| `debris` | array | `{ "kind", "cell" }`: what there is to clear, on the plot and round it: `branch`, `stump` (in the way until they are cleared) and `grass` (walked over). |
| `trees` | array of cell | Trees within two cells of the edge (three on a large field). In the way. |
| `scenery` | array | `{ "kind", "cell" }` near the edge: `bush`, `rock` (in the way), `flowers` (walked over). |
| `exit` | object | `{ "edge", "cell", "spawn", "facing", "to" }`: the gap in the edge (`E`, `S` or `W`), the cell inside it where the farmer arrives and where it looks, and the map it leads to (`starter_map`, the village). |
| `start` | object | `{ "map", "cell", "facing" }`: where a new game starts: a cell of the room of the house, beside the bed. |
| `added_maps` | array of string | The names of *Added maps*, in the order they were added. |
| `trails` | array of Trail | *Optional* (T17.23; a farm planned before it has none). The places set aside for the doors to added maps, at most 8, chosen when the farm is planned whether or not it has added maps: `{ "edge", "cell", "spawn", "facing" }`, `cell` the cell **beside** the edge (not in it) where the door lies and `spawn` the cell one further in where the farmer arrives. Both can be walked to from the house, nothing of the plan lies on them, and no forage place of `farm.forage.spots` is one of them. They are chosen after everything else, with dice of their own, so the rest of the plan is what it was without them; the ones no tree stands before come first. |
| `added` | array of AddedMap | *Optional* (T17.23). One entry a map that was added, in the order of `added_maps`; see 12.3a. A farm without `trails` has none: its `added_maps` stay names. |
| `notes` | array of string | What the planner changed (a later seed, a smaller plot, a larger field). |

**Building:** `id` (`farm_house`, `farm_coop`, `farm_barn`), `kind` (`house`, `coop`, `barn`),
`rect` (the cells it stands on; 6 x 4, 4 x 3 and 6 x 4 unless the packs say otherwise), `door`
(the cell **before** its bottom row where the farmer goes in and comes out; it is walked on),
`interior` and, for an animal house, `yard`. **Interior** (a room, a map of its own): `id` (the
building's), `size` (`[w, h]` with its walls, which are its outermost cells), `door` (the way
out, a cell of the bottom wall), `arrive` (the floor cell before it), and in the house `bed`
(`{ "cell", "size" }`: its head and `[1, 2]`, a cell wide and two long) and `start`, in an
animal house `trough` and `stalls` (a cell an animal: four). **Yard:** `rect` (the ground
inside the fence, before the building and a cell wider at each side; the building's `door` is
one of its cells), `fence` (cell by cell: round the yard, up to the wall of the building),
`gate` (a cell of that ring that is no fence: it is walked through) and `side` (`S`, `E` or
`W`: where the gate is).

**In the isometric view** (`projection: isometric`, T17.14) the plan is this same grid: only
what the planner is told of the packs is the view's (`orchestrator.farm_facts`). The footprint
of the farmhouse, of a coop and of a barn is `stands_on` of the picture an isometric pack drew
as a `BUILDING` (the chosen starter building first; one tagged `coop` or `barn` for that
house), its door before the middle of its south side (`[(w - 1) // 2, h]`), and the water is a
pond when a pack has an isometric tile with the role `WATER`, else a well. The planner gives no
building less than two cells each way, so a house drawn on one diamond gets a footprint of 2 x
2: the builder stands it in the last row of that footprint, over the plan's door cell, and the
rest of the footprint stays ground. The builder paints the plan on the project's tile set of
diamonds and on a `Soil` layer of diamonds of the same footprint (`generated/tilesets/
farm_soil.tres`, Godot's isometric shape; tilled and watered soil are the flat isometric tile
a pack tagged `soil` or `watered`, else drawn diamonds, as the plot always is: no isometric
ground is drawn anywhere else). The drawn farm kit is `iso_math.unit` of the footprint large
there (34 px for 60 x 34), and leaves out what lies flat on squares: `soil`, `watered`,
`shipping_bin`, `bed` (`farm_kit.NOT_ISOMETRIC`; the builder draws the bin and the bed as
boxes on their diamonds). A single picture an isometric pack drew on a diamond and tagged
`crop` is a crop there whatever its role (the reader of such a pack gives what stands on a
diamond the role `DECORATION`): the first of its turns gets a strip of drawn stages that ends
in it (`farm_kit.to_grow`), whose `origin` is the middle of the picture's diamond.

`farm_plan.check` is what `VAL-031` reports: from the door of the house the farmer walks (to
the four sides, not through the edge, a building, the bin, water, a fence, a tree, a bush, a
rock, a branch or a stump) to a cell of the plot, to a cell beside the water, to a cell beside
the bin, through every gate into its yard and to its door, and to the way out; the plot has
twelve cells; nothing lies on something else (only a thing to clear on the plot); the farmer
starts on the floor of the house beside the bed and can walk to its door.

### 12.3a `farm.map.added` (the maps added to a farm, T17.23)

Planned by `rpggen/core/added_map_plan.py`, one entry a row of `starter_map.added_maps`, from
the farm's `seed` and the map's number, and **stored once**: a row that is new plans one more
entry, and the stored ones stay byte for byte (a row whose name the plan has is not read
again, whatever kind it says now). A map is a grid of cells like the farm, painted with squares
or with diamonds by `recipes/farm/added_maps_recipe.gd`, **built once** as
`game/maps/farm_map_<n>.tscn` and then the user's.

| Key | Type | Meaning |
|-----|------|---------|
| `plan_version` | 1 | |
| `seed` | int | The farm's seed. |
| `index` | int | 1 to 8: its number among the added maps. |
| `id`, `map` | string | `farm_map_<index>` and `game/maps/farm_map_<index>.tscn`. The id is the number, not the name, so no name can be the id of another map. |
| `name` | string | The row's name: what the map is called in the game (`display_name` of its root). |
| `kind` | string | `forest` or `beach`. The table of kinds is `added_map_plan.PLANNERS`; `cave` is reserved (T17.24). |
| `size` | `[cols, rows]` | 28 x 22 for a forest, 30 x 20 for a beach. |
| `ground` | string | The id of the packs' ground tile for the kind (a `GROUND` tile named or tagged *sand*, *beach*, *shore* or *desert* for a beach), or `""`: the ground is then drawn (sand over the tiles; the farm's ground under a shade for a forest). |
| `trail` | int | The index of the farm's trail (`farm.map.trails`) whose door leads here. |
| `door` | object | `{ "edge", "cell", "spawn", "facing", "to": "farm" }`: the gap in the edge of this map that leads back, and the cell before it. |
| `paths` | array of cell | A forest: from the way in to its clearing. `[]` for a beach. |
| `clearing` | `[x, y, w, h]` | A forest only: cells without trees. |
| `water` | object | A beach only: `{ "kind": "sea", "side", "cells" }`, the sea along one side (`N`, `E`, `S`, `W`), three to five cells deep, the cells of the edge on that side among them. The cells carry the `water` data of the `Soil` layer, so the rod is cast there. |
| `fish` | object | A beach only: `{ "from", "at" }`: the cell the rod is cast from and the cell of the sea beside it. |
| `trees`, `scenery`, `debris` | | As on the farm (`farm.map`). |
| `spots` | array of cell | The places where a thing to forage may lie in the morning: 8 in a forest, 6 on a beach (most of them near the water), fewer when the map has less room. Written as `Forage/Spot<n>`. |
| `notes` | array of string | What the planner did again. |

**The check** (`added_map_plan.check`, part of `farm_plan.check`, `VAL-031`): the way in is a
cell of the edge with the floor before it; nothing lies on something else or outside the map;
from the way in the farmer walks to every forage place, to the clearing and to the place the
rod is cast from, which lies beside the sea; every added map has a trail of its own. An
arrangement that fails is thrown again (twelve times at most).

**The door pair.** The farm's side is not written into `game/maps/farm.tscn`: that map
instances `generated/scenes/farm/trails.tscn` once (its node `Trails`), and the builder writes
that scene on every build with, for every entry, the door `to_<id>` on the trail's `cell`, the
spawn `from_<id>` on its `spawn` and a mark on the ground. The added map's side is the door
`to_farm` in its gap and the spawn `from_farm`.

### 12.4 `farm.people` (the people of a farm's village, T17.09)

Planned once by `rpggen/core/people_plan.py` from the `NPC` assets of the catalog, the seed and
what the caller knows of the village (how many houses, whether there is a shop and a pond, the
item ids of the game), and **stored and reused**: once the key is there the seed and the
options no longer change it, and an NPC the packs gain later is appended. `people` is an
optional key of the `farm` section, an array of Person in the order the seed gave; a village
has at most twelve people unless the option `people` (1 to 40) says otherwise, and three
without a picture of their own (`asset` is `""`) when the packs have no NPC.

**Person:** `id` (the name in lower case, unique: the id of the friendship and of the dialogue
atom `friendship:<id>>=N`), `name` (from a list in the planner, by the seed), `asset` (the NPC
sprite), `home` (the number of a house of the village, from 1; the houses are shared out
evenly), `job` (`shopkeeper` for one person of a village with a shop, else `""`), `pattern`
(which day it has: `shopkeeper`, `villager`, `stroller`, `angler`), `loves`, `likes` and
`dislikes` (item ids of the game, no item twice; never a tool or a seed; two, three and two,
fewer in a game with few items), `schedule`, and in a farm with festivals `birthday`
(`{ "season", "day" }`, T17.25, §12.7: optional, and added to the people a project stored
before it without anything else of them changing).

**Schedule entry** (what `RpgSchedule` reads, `actors/schedule.gd`): `hour` (from which hour of
the day it holds: 6 to 23, then 0 and 1 of the night), `days` (optional: the days of the week
it holds on, 0 to 6; without it every day), `weather` (optional: the weather it holds in;
the planner writes `rain`) and `place`. In the plan a place is one of `home`, `work`, `square`
and `pond`. The entry in force is the last whose hour has come among those of the day and the
weather; an entry with a `weather` wins over one without. Every planned schedule begins at home
at 6:00, ends there in the evening and keeps the person at home when it rains (the shopkeeper
works whatever the weather, from 8:00 to 18:00 on six days, and has weekday 6 off).

`people_plan.check` finds: somebody without a home or with a home the village does not have, a
schedule without an entry for every day, an entry that names another place than the four, work
without a job, the pond or the shop of a village without one, a taste for an item the game
does not have, an item in two tastes, two people of one id, two shopkeepers.

**`game/data/people.json`** (`rpggen/schema/people.schema.json`) is what the game reads:
`{ "people": [ Person ] }`, a Person as above without `asset` and `pattern`, with `scene` (its
NPC scene) and with the places of its schedule turned into where they are for this person
(`people_plan.people_file`): an entry has `map` (the id of the map, `RpgMapRoot.map_id`; none:
the map the NPC is on) and either `place` (the name of a marker of that map, a `Marker2D` in
the group `rpg_place`) or `cell` (`[x, y]`), and optionally `facing`. The builder writes the
file **once**; it is the user's afterwards: a person's tastes, name and day are changed there,
and `RpgFriendship` reads it when the game starts and gives each NPC that carries an
`RpgSchedule` without entries of its own the schedule of its person.

### 12.5 `farm.animals` (the animals of a farm, T17.07)

Planned once by `rpggen/core/animal_plan.py` from the sprites of the catalog with the role
`ANIMAL` and the animal houses of the farm's own plan (§12.3, `animal_houses`), and **stored
and reused**: once the key is there the seed no longer changes it, and a kind or a colour the
packs gain later is appended. It is an optional key of the `farm` section: **a farm without an
animal house (`animals: none`) has none**, and nothing of the animals is written for it. The
planner reads no option.

`plan_version` (1), `seed`, `feed` (`item`, `name`, `price`: hay, what goes into a trough),
`names` (what an animal is called when it is bought, in an order the seed gives), `notes` (a
house the packs have no animal for stays empty) and `kinds`, the coop's first.

**Kind:** `id` (`hen`: the word of the asset's tags that names an animal, else the last such
word of its id, else the first word of its file name), `name`, `house` (`coop` for a hen, a
chicken and a duck; `barn` for a cow, a sheep, a goat, a pig and every other animal), `ticket`
(`animal_<id>`: the item the shop lists the kind as; it never reaches the bag) and `cost`,
`product` and `price`, `large` (`<product>_large`: what an animal gives from five hearts on)
and `large_price` (half as much again), `collect` (`floor` for the kinds of the coop: the
product lies in the house in the morning; `hand` for the others: `interact` with the animal
takes it) and `variants`. Only the kinds whose house the farm has are planned. The products
and prices come from a table in the planner (egg 25, duck egg 35, milk 60, goat milk 50, wool
70, truffle 90; 40 for an animal nobody knows); an animal costs six of its products.

**Variant:** `id` (`hen_01_black`: the animal's own name and its colour), `colour` (`""` for
an animal drawn in one), `asset` (the sprite it walks in) and `sleep` (the sprite it sleeps
in when that is another file, else `""`). There is one for each colour of each animal the
packs drew (T16.21); the drawn hen of the farm kit is one variant without a colour.

`animal_plan.check` finds: two kinds of one id, a kind without a picture, in a house that is
neither, without a price, or whose product is taken in a way nobody knows.

**`game/data/animals.json`** (`rpggen/schema/animals.schema.json`) is what the game reads:
`{ "animals": [ Kind ], "feed", "names", "houses" }`. A Kind is as above, each of its variants
with `scene` (`generated/scenes/farm/animals/<kind>__<variant>.tscn`). `houses` is a row for
each animal house of the farm's plan: `kind`, `map` (the scene of its room), `yard_map` (the
scene of the map its yard is on) and `stalls` (how many animals it has room for). The builder
writes the file **once**; it is the user's afterwards. `generated/data/animals.json` is the
same, written on every build: `RpgAnimalData` takes from it the kinds and the houses the
user's file does not list. The items of a kind (`product`, `large`, `ticket`) and the feed are
seeded once into `game/data/items/`.

**In the saved game** the herd is in the flags, with no new key of the save: the entity
`farm_animals` has `herd` (a row an animal: `id`, `kind`, `name`, `house`, `stall`, `variant`,
`friendship` (0 to 1000), `fed`, `petted`, `ready` (the item it has to give, or `""`)),
`trough` (house -> full today), `bought` and `bought_<kind>` (how many were bought: the next
name and the next colour).

### 12.6 `farm.forage` (the fish and the forage of a farm, T17.10)

Planned once by `rpggen/core/forage_plan.py` from the `ITEM` pictures of the catalog tagged
`forage` and `fish` (the packs' own, else the seven drawn ones of the farm kit: four things to
forage, one a season, and three fish), the seed and the farm's own map (§12.3), and **stored
and reused**: once the key is there the seed no longer changes it, and a fish or a thing the
packs gain later is appended. `forage` is an optional key of the `farm` section:

| Key | Type | What |
|-----|------|------|
| `plan_version` | 1 | |
| `seed` | int | The seed it was planned with. |
| `fishing` | bool | The rod is sold: the option `starter_map.fishing` is on **and** the farm's map has a pond or a beach among its added maps (T17.23). It is the one key that is not kept: it follows the option and the map on every generation. |
| `forage` | array of Thing | The things to forage, in the order the seed gave. |
| `fish` | array of Fish | The fish. |
| `spots` | array of `[x, y]` | The cells of the farm's map where a thing may lie in the morning, sorted from the top: 6, 8 or 10 for a small, a medium or a large field. |
| `notes` | array of string | What the planner added (the drawn ones, when a plan is made without the kit). |

**Thing:** `id` and `item` (the id of the item it is, `forage_<name>`), `name`, `asset` (the
picture; `""` for a drawn one of a plan made without the kit, which then has a `color`),
`seasons` (from the picture's `season:<name>` tags, else a season of its own; every season has
at least one thing), `price` and `energy` (what eating one restores). A thing of a kind of
added map also has `maps` (T17.23: `["beach"]`): it lies only on maps of that kind, and on such
a map only the things that name it lie. The things of a beach (the packs' `ITEM`s tagged
`forage` and `beach`, else the kit's drawn shell and seaweed) are appended when the farm gets
its first beach.

**Fish:** the same keys (the item is `fish_<name>`), and `times` (`morning`: before 12:00,
`day`: before 18:00, `evening`), `water` (`["pond"]`, or `["sea"]` for a fish of a beach:
an `ITEM` tagged `fish` and `sea`, else the kit's drawn sardine and sea bass) and `speed` (how fast its mark moves
along the bar: 1.0, 1.2 or 1.4, the dearer the faster). A fish bites at two of the three times
and in three of the four seasons unless the packs have fewer than three fish; at every time of
every season at least one bites.

**The places** (`forage_plan.free_cells`, `spots_for`) are read off the farm's map, which is
not changed: cells the farmer can walk to from the door of the house, within five cells of the
edge, that are not the plot nor beside it, not a path, not in a yard, not before a door, the
bin or the way out, not beside the water, and with nothing of the plan on them; chosen by the
seed, no two nearer than four cells while the farm has room. The builder writes them into
`game/maps/farm.tscn` as `Marker2D` nodes `Forage/Spot1` ... (the map is written once: a farm
map that was made before has none, and the game then goes by `spots` of
`generated/data/forage.json`). **Which place has what on which day is not planned and not
stored**: the game derives it from its seed, the map, the index of the day and the season
(`RpgForage.forage_of`), and keeps only what was picked up today (`flags.farm_forage`).

`forage_plan.check` finds: a season with nothing to forage, a time of a season at which no
fish bites, two entries of one id.

**`game/data/forage.json`** (`rpggen/schema/forage.schema.json`) is what the game reads:
`{ "forage": [ Thing ], "fish": [ Fish ] }` without `asset` and `color`
(`forage_plan.forage_file`). The builder writes it **once**; it is the user's afterwards. It
writes the same lists with `spots`, `map` (`farm`: the id of the map the cells are of) and
`fishing` to `generated/data/forage.json` on every build; the game reads the user's file and
takes from the generated one the entries the user's does not list.

### 12.7 `farm.events` (the festivals of a farm's year, T17.25)

Planned once by `rpggen/core/event_plan.py` from the options (`starter_map.festivals`,
`days_per_season`) and what the farm's section says of its crops and its fishing, and **stored
and reused**: once the key is there the options no longer change it. `events` is an optional
key of the `farm` section; a farm with `festivals` off has none (and a stored one is left as
it is: the game then shows nothing of it). The seed changes nothing of the plan: there is one
festival a season, on a fixed day.

| Field | Type | Meaning |
|-------|------|---------|
| `plan_version` | 1 | |
| `seed` | int | The seed of the generation that planned it |
| `days_per_season` | 7, 14, 28 | The length of a season the days were planned for |
| `festivals` | array of Event | Four, in the order of the seasons |
| `notes` | array of string | What the planner had to say (a farm that cannot fish) |

**Event:** `id`, `kind` (`egg_hunt`, `fishing_count`, `produce_contest`, `feast`; the files
also take `gathering`, which has nothing to do, and `wedding`, which the game adds at run time,
T17.26), `name`, `season` (`spring` to `winter`), `day` (1 to 28), `from` and `to` (the hours
the people stand at `place`: 9 and 20), `place` (`square`: the marker of the village the
people gather at). By kind: an egg hunt has `spots` (the markers `festival_egg_1` to `_5`),
`each` (20: what an egg pays), `goal` (5) and `prize`; a fishing count has `goal` (3) and
`prize`; a produce contest has `table` (the marker `festival_table`), `judge` (`price`: the
dearest thing the bin sold that season, or `count`: how many things), `goal` and `prize`; a
feast has `table` and `points` (60: the friendship everybody gains). `prize` is
`{ "gold" }`, `{ "item", "qty" }` or both. Optional in the files: `year` (only in that year)
and `shop_closed` (false: the shop keeps its hours).

**The day.** A festival is the fifth day of a week (a Friday: never weekday 6, the day the
shop is closed anyway): in spring and summer of the middle week of the season, in autumn and
winter of its last. That is day 12, 12, 26 and 26 of a season of 28 days, 5, 5, 12 and 12 of
one of 14, and 5 of every season of 7 (`event_plan.festival_day`). The day is planned for the
length the project has when it is planned; the game folds a day a shorter season no longer has
into it week by week (`RpgFarmEvents.day_in`: `(day - 1) % days_per_season + 1`), so it stays a
Friday. Summer's festival is the fishing count where `farm.forage.fishing` is true and a
second produce contest (`summer_fair`, `judge: count`, `goal` 10) where it is not. The `goal`
of the autumn contest is the middle one of the prices of the crops that grow in autumn.

`event_plan.check` finds: two events of one id, a kind or a season nobody knows, a day the
planned season does not have, two festivals on one day, an egg hunt without spots, a contest
or a feast without a table.

**`game/data/events.json`** (`rpggen/schema/events.schema.json`) is what the game reads:
`{ "events": [ Event ] }`, an Event as above with `map` (`starter_map`: the id of the map its
markers are on; `event_plan.events_file`). The builder writes it **once**; it is the user's
afterwards. It writes the same list to `generated/data/events.json` on every build; the game
reads the user's file and takes from the generated one the events the user's does not list,
and an entry `{ "id", "removed": true }` of the user's file keeps an id out. The markers the
events name are made on the village when it is built (`Places/festival_table`,
`Places/festival_egg_<n>`); a village that exists is never built again, and the game then
puts the things round the marker `place`.

**Birthdays** are not events of the plan: each Person (§12.4) has a `birthday`
(`{ "season", "day" }`), given by `people_plan.with_birthdays` to whoever has none (so the
people a project stored before T17.25 get theirs and nothing else of them changes): by the
seed and the person's id, in the season that has the fewest so far, never on a festival's day
or on the first day of spring, and no two on one day while the year has days enough. A farm
with `festivals` off gives nobody a birthday.

**At run time** (`RpgFarmEvents`, the child `Events` of the farm's mode, at work only when the
mode's `festivals` is true) nothing new is saved under a key of its own: `flags.farm_events`
holds `added` (the events `add_event` added: a wedding), `today` (`{ day, id, found, count,
done }`: what was found, caught or judged on the festival of the day with that index) and
`birthday_gifts` (`{ day, people }`: who had the gift of their birthday today), and
`flags.farm_bin.shipped` holds `{ season: "<year>:<season>", items: { item id: qty } }`, what
the nights of the season sold (the produce contest is judged on it).
