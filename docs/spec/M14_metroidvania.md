# M14 — The Metroidvania Archetype (release 1.2.0)

**Goal:** a third archetype, **Metroidvania**: side-view platforming, abilities that open the
world, rooms joined by edge exits, a guardian, save stations and a room map, generated from a
side-view pack and validated by its own smoke test. **This milestone starts after `v1.1.0` is
tagged** (T13.23) and ends with `v1.2.0`.

This file follows the format of M01–M13. It was written against commit `9726d0e` and revised the
same day. **Files live in** `godot_templates/addons/rpg_runtime/archetypes/metroidvania/`,
`godot_templates/builder/recipes/metroidvania/` and `builder/smoke/smoke_steps_metroidvania.gd`.
The archetype shares the title screen, settings, saving, inventory, equipment, dialogue, shops,
quests, credits, input glyphs, languages, the pause menu, the lock-and-key planner (T13.21) and
the world repair (T13.24) with the other two. It does **not** use the top-down `RpgActor` for the player, the party on the
map, encounter zones, followers, Y-sort or the interior recipe.

## Ground rules for this milestone

* The M12 and M13 ground rules apply unchanged, including the post-release compatibility
  contract of M13: the app and the runtime become **1.2.0**, `config_version` stays 1 with
  additive keys, `save_version` stays 1 with optional keys (every new save key here is new, with
  no change of meaning), and a 1.0 or 1.1 project regenerates without a prompt.
* **No path breaks.** T14.01 moves the real-time combat scripts to a shared folder and leaves a
  shim at every old path for the whole of 1.x, so a user's script that preloads
  `archetypes/arpg/hitbox.gd` keeps working. The `.uid` files move with the scripts (never
  edited), so scenes that reference them by uid remap by themselves.
* **Archetype isolation.** `metroidvania` is the third value of `config.archetype`,
  `staging.ARCHETYPES` and `orchestrator.ARCHETYPE_SMOKE_STEPS`; the existing install filter
  (`staging._other_archetype`) keeps its folders out of the other two archetypes' projects. A
  recipe that is shared (the TileSet recipe, the UI recipes) changes its output **only when
  `config.archetype == "metroidvania"`**; every such card has a test that a top-down project's
  output is byte-identical before and after the card. Until T14.13, the wizard's card is
  disabled by `METROIDVANIA_AVAILABLE = False` in `rpggen/features.py`, as `ARPG_AVAILABLE` was.
* **New error codes** go into `03_ERROR_CODES.md` first, then `python tools/gen_error_codes.py`.
  Codes reserved by this milestone: `ASSET-030` (informational: a side-view player without a
  jump or fall animation). `VAL-027` and `VAL-028` (M13, warnings) are reused for rooms.
* **Dependencies.** None new.
* **The sample pack is not changed.** The side-view demo uses a second, separate CC0 sample pack
  (T14.09), so every top-down golden, screenshot and "Try the sample" test stays as it is.
* **Perf.** T14.11 adds a ceiling for the metroidvania generation of the side-view sample pack,
  and the CI integration jobs are split per archetype so the wall-clock time does not grow by
  half on one runner.
* After any change to detection, run `python -m rpggen.dev update-goldens` and review the diff;
  T14.02 changes detection, so the corpus (T12.26) must be unchanged after it.

## Order of work

| Step | Tasks | Why this order |
|------|-------|----------------|
| 1 | T14.01, T14.02, T14.09 | The move, detection and the side-view pack are independent and everything else needs them |
| 2 | T14.03 → T14.04 → T14.05 → T14.06 → T14.07 → T14.08 | The runtime, in dependency order |
| 3 | T14.10 → T14.11 | The wizard, then the smoke test |
| 4 | T14.12 → T14.13 | Docs and the gate, then tag `v1.2.0` |

## Index

Sizes are rough: **S** under a day, **M** 1–3 days, **L** 3–7 days, **XL** more than a week.

| Card | Title | Size | Depends on | Status |
|------|-------|:----:|------------|--------|
| T14.01 | Shared real-time combat primitives | M | — | open |
| T14.02 | Side-view detection: tags, collision values, backgrounds | M | — | open |
| T14.03 | Platform actor | L | T14.01, T14.02 | open |
| T14.04 | Side-view NPCs, objects and the camera | M | T14.03 | open |
| T14.05 | Abilities and gates | M | T14.04 | open |
| T14.06 | Rooms and the world graph | XL | T14.05 | open |
| T14.07 | Side-view enemies and the guardian | M | T14.06 | open |
| T14.08 | HUD, room map and save stations | M | T14.07 | open |
| T14.09 | Side-view sample pack and *Try the sample* | M | — | open |
| T14.10 | Wizard: the Metroidvania card, roles, options and preview | M | T14.08, T14.09 | open |
| T14.11 | Metroidvania smoke steps and integration test | M | T14.10 | open |
| T14.12 | Documentation, screenshots and changelogs | M | T14.11 | open |
| T14.13 | Gate (1.2.0) | M | T14.12 | open |

---

## T14.01 — Shared real-time combat primitives

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_runtime/combat/realtime/` (new: `damage_info.gd`,
`hitbox.gd`, `hurtbox.gd`, `health.gd`, `projectile.gd`, `state_machine.gd`, `pickup.gd`,
`screen_feedback.gd`, moved from `archetypes/arpg/` with their `.uid` files), shims at the old
paths, every script under `archetypes/arpg/` that preloads them, `godot_templates/builder/recipes/arpg/*.gd`,
`godot_templates/addons/rpg_runtime/combat/combat_mode.gd`, `godot_templates/tests/unit/test_arpg_runtime.gd`,
`test_ranged_combat.gd`, `tests/integration/test_template_project.py`, `tests/integration/test_regeneration.py`

The ARPG primitives are `class_name` scripts inside the ARPG folder, which the install filter
keeps out of every other archetype's project. T14.03 and T14.07 need them.

**Spec**
* The eight scripts move to `combat/realtime/` **with their `.uid` files**, so their uids are
  unchanged and every scene that references them by uid resolves. Class names and behaviour are
  unchanged; every `preload` and `load` path is updated.
* A shim stays at each old path for 1.x: a script with no `class_name` that only
  `extends "res://addons/rpg_runtime/combat/realtime/<name>.gd"`, with a comment naming the new
  path and the 2.0 removal. The shim gets a **new** `.uid` file created by Godot (committed, never
  edited). A user's `preload("res://addons/rpg_runtime/archetypes/arpg/hitbox.gd")` therefore
  still works and yields the same class.
* Regeneration of a 1.0 or 1.1 ARPG project: the ledger sees the shims as modified generated-owned
  files and the new folder as added; nothing is deleted. The generated README's upgrade note
  gives the old and new paths and says that a project opened in the editor before the
  regeneration may need **Project → Reload Current Project** once so the global class cache
  (`.godot/global_script_class_cache.cfg`) is rebuilt; `REGEN-005` already refuses to regenerate
  while the editor is open.
* `combat_mode.gd` documents which archetypes use the real-time set.

**Tests**
* The existing ARPG and ranged tests pass unchanged except for paths.
* `test_template_project` asserts that each moved class is defined exactly once, under
  `combat/realtime/`, and that each shim extends it.
* Regeneration integration: an ARPG project generated by the 1.1 build (the fixture of T13.23)
  regenerates cleanly, a scene that instanced an enemy still loads, and a user script that
  preloads the old path still runs in the smoke test.

**Done when**
* The tests pass and `godot-test` is green.

---

## T14.02 — Side-view detection: tags, collision values, backgrounds

**Depends on:** nothing
**Files:** `rpggen/core/classifier.py`, `rpggen/core/catalog.py`,
`rpggen/schema/catalog.schema.json` (`CollisionSpec` values), `docs/spec/02_SCHEMAS.md`,
`rpggen/core/adapters/naming.py`, `rpggen/core/requirements.py`, `rpggen/core/mapping.py`,
`tools/make_synthetic_packs.py` (a `platformer` pack), `tests/unit/test_classifier.py`,
`tests/unit/test_requirements.py`, `tests/unit/classifier_cases.json`

**Spec**
* `CollisionSpec` gains the values `one_way` (a platform the player jumps through from below
  and drops through with down + jump) and `ladder` (climbable, no collision). The grid editor
  and bulk panel offer them for `tiles` assets; the TileSet recipe (T14.03) reads them for the
  metroidvania only, and the other archetypes treat both as `none` (a top-down map has no
  gravity).
* Tags detected from folder and file words: `platform` (platform, ledge), `one_way` (oneway,
  one_way, semi, thin platform), `ladder` (ladder, rope, vine), `hazard` (spike, spikes, lava,
  thorn, saw), `save_point` (save, checkpoint, bench), `ability` (powerup, power_up, upgrade,
  ability, orb), `parallax:<n>` (`bg_far`, `background_1`, `layer2`; `far`, `mid`, `near` give
  1, 2, 3). Tags change nothing in the other archetypes; the top-down goldens do not move.
* `classifier.pack_view(inventory)` guesses `side` or `top` per pack from the words
  (platformer, sidescroller, metroidvania, jump; versus rpg, topdown, overworld) and from
  character sheets whose animations include `jump` or `fall` and no `up` or `down` walk. It is a
  pack warning, shown on the pack card, and the Archetype page's hint (T14.10).
* `requirements.REQUIRED["metroidvania"] = ["PLAYER", "GROUND"]`; `OPTIONAL` adds the roles
  the archetype uses: `BACKGROUND` (parallax layers), `DECORATION`, `ENEMY`, `BOSS` (the
  guardian), `ITEM`, `NPC`, `UI`, `PORTRAIT`; mapping labels say what each is for ("Ground
  tiles: floors and walls of every room").
* Synthetic pack `platformer`: a 16-px tile sheet with ground, one-way platforms, a ladder and
  spikes (folders `tiles/platforms`, `tiles/ladders`, `tiles/hazards`), a hero with idle, run,
  jump, fall, climb, attack and dash (whole strips), a patrol enemy, a flyer, a guardian, a save
  bench, two ability orbs, three parallax backgrounds, a sign and an NPC. Golden added.

**Tests**
* The classifier cases for every new tag and for `pack_view`.
* The collision values validate; the facets round-trip; a top-down project with a `one_way`
  tile builds the same TileSet as with `none`.
* The platformer golden; no other golden moves.

**Done when**
* The tests pass and the corpus is unchanged.

---

## T14.03 — Platform actor

**Depends on:** T14.01, T14.02
**Files:** `archetypes/metroidvania/platform_actor.gd`, `platform_player.gd`, `platform_input.gd`,
`platform_math.gd`, `metroidvania_mode.gd`, `metroidvania_strings.gd` (all under
`godot_templates/addons/rpg_runtime/archetypes/metroidvania/`), `godot_templates/builder/recipes/tileset_recipe.gd`
(the side-view physics layers and custom data, **for this archetype only**),
`builder/recipes/metroidvania/mode_recipe.gd`, `builder/recipes/metroidvania/player_recipe.gd`,
`builder/recipes/project_settings_recipe.gd` (input actions `jump`, `dash`, `attack`, `down`,
added for this archetype only), `godot_templates/tests/unit/test_platform_actor.gd` (new),
`test_tileset_merge.gd`

```gdscript
class_name RpgPlatformActor extends CharacterBody2D
@export var run_speed := 110.0           # px/s at 16 px tiles; scaled by tile_size / 16
@export var jump_height_tiles := 3.25    # the peak of a full jump
@export var jump_time_to_peak := 0.38    # s; gravity and jump speed derive from these two
@export var fall_gravity_mul := 1.6      # falls faster than it rises
@export var coyote_s := 0.1
@export var jump_buffer_s := 0.12
@export var max_fall_speed := 360.0
var facing := 1                           # -1 left, 1 right; flips the sprite, never the body
var on_ladder := false
signal landed(speed: float)
signal jumped
```

**Spec**
* Movement in `_physics_process` with `move_and_slide`, `floor_snap_length` set, up direction
  `Vector2.UP`. A jump released early cuts the upward velocity in half (variable height).
  Coyote time and a jump buffer as exported above. Wall slide (0.3× fall speed against a wall
  while pushing into it) and wall jump are gated behind the `wall_jump` ability (T14.05); dash
  behind `dash`; a second jump behind `double_jump`.
* **TileSet, metroidvania only.** When the config's archetype is `metroidvania`, the TileSet
  recipe adds physics layer 2 for `one_way` tiles with the polygon's one-way flag
  **⚠ VERIFY** (`TileSet.add_physics_layer`, `TileData.set_collision_polygon_one_way`), the
  custom data layers `ladder`, `hazard` and `breakable` (bool), and sets them from the collision
  value and the tags. For the other archetypes the recipe's output is byte-identical to 1.1
  (a test compares the sample pack's TileSet before and after this card), so the TileSet merge
  of regeneration never sees a new layer on a top-down project.
* One-way platforms: down + jump drops through for 0.2 s by disabling the mask bit.
* Ladders: up or down over a `ladder` tile enters climbing (gravity off, `climb` animation,
  70 px/s); jump or leaving the tile exits.
* Hazards: touching one costs 1 HP, 0.6 s invulnerability, and a return to the last safe ground
  position (the last cell stood on for 0.25 s) after a 0.3 s fade. Death at 0 HP goes through
  the shared defeat policy (`combat/defeat_policy.gd`): the game-over screen, or the last save
  station (T14.08).
* Animation: `idle`, `run`, `jump`, `fall`, `climb`, `attack`, `dash`, `hurt` through the
  existing `RpgAnimationDriver` with a side-view facing: `RpgAnimationDriver.play_side(base,
  facing)` picks `<base>_right` or `<base>_side`, mirrors it for the left unless the pack has
  `<base>_left`, and falls back to `<base>` without a direction. A character without `jump` or
  `fall` uses `idle` in the air, with `ASSET-030` (informational) in the report.
* Attack: a hitbox on the facing side on the attack's active frames (T14.01 primitives), damage
  from `get_stat("attack")` so equipment counts. Enemies' hurtboxes as in the ARPG.
* `platform_math` holds the derived gravity and jump speed (`2h/t²`, `2h/t`) and is pure.
* Interaction (`interact`): the nearest interactable within a tile ahead, facing either way
  (T14.04 defines the side-view interactables).

**Tests**
* `platform_math`: a full jump reaches 3.25 tiles ±2 %; a released jump is lower.
* Coyote: a jump pressed 0.08 s after leaving a ledge succeeds; 0.15 s fails. The buffer: a
  press 0.1 s before landing jumps on landing.
* One-way: the actor lands from above, passes from below, and drops with down + jump.
* Ladder enter and exit; hazard damage, invulnerability and the return to safe ground.
* Attack hits an enemy hurtbox on the facing side only.
* `play_side` with a `_right`, a `_side`, a `_left` and a bare animation.
* The top-down TileSet is byte-identical; `test_tileset_merge` with a side-view TileSet.

**Done when**
* `godot-test` is green and the probes for the one-way flag and the custom data layers are in
  `godot_api_verified.md`.

---

## T14.04 — Side-view NPCs, objects and the camera

**Depends on:** T14.03
**Files:** `archetypes/metroidvania/side_npc.gd`, `side_camera.gd`, `side_interactable.gd` (new,
under `godot_templates/addons/rpg_runtime/archetypes/metroidvania/`), `godot_templates/addons/rpg_runtime/world/chest.gd`,
`sign.gd`, `door.gd`, `spawn_point.gd` (a `side_view` export that turns off the top-down
facing), `actors/npc.gd`, `actors/animation_driver.gd`, `builder/recipes/metroidvania/objects_recipe.gd`
(new), `builder/recipes/actor_recipes.gd`, `godot_templates/tests/unit/test_side_objects.gd` (new),
`test_world_runtime.gd`

The shared world objects assume a top-down map: `RpgNpc` extends the top-down actor and plays
`idle_down`, chests and signs face the player by direction, `RpgDoor` fades to a spawn point,
and the top-down map root owns the camera. Placed in a side-view room, a villager would look for
a frame that does not exist and the camera would be the wrong one.

**Spec**
* `RpgSideNpc` (`CharacterBody2D` with gravity from `platform_math`, so it stands on the
  floor): idle facing left or right, turns to face the player when talked to, uses
  `play_side`. The actor recipe builds NPC scenes with it for this archetype and with `RpgNpc`
  otherwise; the dialogue runner does not care which.
* `RpgSideInteractable` (Area2D, `interact()` virtual): the base of the save station, the
  ability pickup's marker and the end-room trigger. Chests and signs keep their scripts; with
  `side_view = true` they skip the facing logic and the interaction check is "within a tile
  ahead" instead of "in front by direction". `RpgDoor` with `side_view` is a door the player
  enters with up (a house in a room, used by nothing in the demo but available in the dock).
* `RpgSideCamera` replaces the top-down camera for this archetype: the room's map root owns it
  (`RpgRoom`, T14.06, sets limits), the player's scene has none, and a test proves a room has
  exactly one enabled `Camera2D`.
* The animation driver's facing fallback (T14.03's `play_side`) is also used by the top-down
  NPC when a sheet has only side frames, so a side-view NPC asset placed on a top-down map does
  not log missing-animation errors (a fallback, not a feature: the report notes it).
* The dock's placement (`placement.gd`) snaps a dropped object to the floor below the drop point
  in a side-view room (a ray down to the nearest solid tile) instead of Y-sorting.

**Tests**
* The side NPC stands on the floor, faces the player when talked to, and the dialogue runs.
* A chest and a sign with `side_view` interact from either side and never from above.
* Exactly one enabled camera per room; its limits are the room's.
* The dock drop lands on the floor.

**Done when**
* The tests pass.

---

## T14.05 — Abilities and gates

**Depends on:** T14.04
**Files:** `godot_templates/addons/rpg_runtime/core/game_state.gd` (`abilities`, `broken_cells`),
`archetypes/metroidvania/ability_pickup.gd`, `ability_gate.gd`, `abilities.gd` (the table),
`platform_player.gd`, `ui/strings.gd`, `godot_templates/addons/rpg_runtime/world/gate.gd` (a gate
may require an ability), `dialogue/condition.gd` (`ability:<id>` atom), `godot_templates/tests/unit/test_abilities.gd`
(new), `test_game_state.gd`, `test_save_manager.gd`

**Spec**
* `abilities.gd`: `double_jump`, `dash` (a 0.18 s burst at 3× run speed, invulnerable, 0.6 s
  cooldown, one per airtime), `wall_jump`, `high_jump` (+1.25 tiles), `break_blocks` (the attack
  breaks tiles whose custom data `breakable = true`; the cells are remembered in the save under
  `broken_cells`, `{room_id: [[x, y], ...]}`). Each has a name key, a description key and an
  icon (the ITEM or ability asset chosen by the recipe; a generated glyph otherwise).
* `GameState.abilities: Array[String]` and `broken_cells` are **new optional save keys** with
  empty defaults (`save_version` stays 1; a 1.0 save loads with none); `grant(id)` emits
  `ability_granted`; the player reads the set every frame (no caching, so a cutscene can grant
  mid-air).
* `RpgAbilityPickup` (a `RpgSideInteractable`, persistent by entity id): touching it grants the
  ability, plays `sfx_pickup`, shows a toast with the name and the key hint (`Press [Space]
  twice`), and removes itself.
* `RpgAbilityGate`: a marker the planner uses; the gate itself is only geometry (a ledge too
  high, a gap too wide, a breakable wall). `RpgGate` (T12.70) gains `required_ability` beside
  `required_key`, so a door can also ask for an ability.
* The dialogue condition atom `ability:<id>`; the dialogue tab's checker knows it.

**Tests**
* Grant, save and load round trip; a save without `abilities` loads empty; the 1.0 save fixture
  loads.
* A pickup grants once and is gone after reload.
* Double jump: a second press in the air gives a second jump, once; dash: the distance and the
  cooldown; wall jump only with the ability; a broken block stays broken after reload.
* The condition atom.

**Done when**
* The tests pass.

---

## T14.06 — Rooms and the world graph

**Depends on:** T14.05
**Files:** `rpggen/core/room_plan.py` (new), `rpggen/core/lockkey.py` (T13.21, used),
`rpggen/core/map_preview.py` (side-view rendering), `rpggen/core/config.py` and
`rpggen/schema/config.schema.json` (`starter_map` for `metroidvania`: `rooms` 5–12, `room_size`
[40, 23] by default, `abilities` a list from the table, `enemies`, `pickups`),
`rpggen/schema/world_plan.schema.json` (T13.20's, extended with `rooms`), `docs/spec/02_SCHEMAS.md`,
`rpggen/core/orchestrator.py` and `preflight.py` (the stored plan, as T13.20),
`godot_templates/builder/recipes/metroidvania/rooms_recipe.gd` (new), `builder/recipes/metroidvania/metroidvania_build.gd`,
`builder/recipes/metroidvania/parallax_recipe.gd`, `archetypes/metroidvania/room.gd`,
`room_exit.gd`, `godot_templates/addons/rpg_runtime/world/scene_router.gd` (a transition without a
fade for room exits), `godot_templates/builder/lib/map_graph.gd` and `builder/tools/world_repair.gd` (room exits),
`godot_templates/tests/unit/test_rooms.gd` (new), `tests/unit/test_room_plan.py` (new),
`tests/integration/test_regeneration.py`

**Spec**
* **Room.** A map scene (`RpgRoom extends RpgMapRoot`) one or more screens large, with layers
  `Background` (parallax, built from BACKGROUND assets by `parallax:<n>` with `Parallax2D`
  **⚠ VERIFY** the 4.7 node), `Ground`, `Platforms`, `Hazards`, `Decoration`, `Foreground`, and
  exits on its edges (`RpgRoomExit`: an Area2D on the edge with `target_room`, `target_exit`).
  Crossing an exit changes the room with the player's velocity kept and a 0.25 s camera slide;
  no fade. The room owns the `RpgSideCamera` (T14.04) and sets its limits.
* **World graph.** `room_plan.plan(options, seed, catalog)` makes `rooms` rooms on a grid of
  screens: a start room (save station, sign), corridors, a vertical shaft, a guardian room,
  pickup rooms (one per ability in `abilities`) and an end room (an NPC with a line and the
  credits trigger). Rooms connect through exits on shared edges. Every room has a ground floor
  with platforms reachable by a full jump (≤ 3 tiles up, ≤ 4 across) unless the room is a gate.
* **Lock and key.** The planner calls `lockkey.plan` (T13.21) over the room graph with the
  abilities as keys: a 5-tile ledge needs `double_jump` or `high_jump`, a 6-tile gap needs
  `dash`, a breakable wall needs `break_blocks`, a shaft needs `wall_jump`; every ability is
  reachable with the ones before it, and the end room needs them all. The option bounds make the
  input always solvable (`rooms ≥ len(abilities) + 3`, enforced by the schema, the Options page
  and the CLI's usage error), and a test proves the planner never produces a VAL-027 or VAL-028
  over 200 seeds.
* **The plan is stored and reused**, exactly as T13.20: `rpggen/world_plan.json` gets a `rooms`
  section at promotion; a regeneration builds only the rooms whose scene is missing and never
  re-plans once any room exists; the *Starter world* options are disabled with the same text
  once a room exists; adding a room appends it to the stored plan, joined to the room the user
  picks, with no abilities involved.
* **Validation and repair.** `map_graph.gd` (T13.24) learns room exits: an exit without a
  partner is `VAL-028`, a room unreachable from the start room is `VAL-027`; both **warnings**
  (M13), listed under *Notes*. The world repair of T13.24 mends them with the same rules (an
  exit's partner is created on the matching edge of the target room; an unreachable room gets an
  exit pair on the edge it shares with the nearest reachable room), by itself for rooms whose
  `map_hash` is unchanged, on request otherwise. Ability gating is not validated or repaired on
  user rooms (a person may add a shortcut).
* **Preview.** The Options page's preview draws the world as a grid of screens with the exits,
  the pickup icons and the gates' letters, in side-view colours; clicking a room shows its
  platforms. `tools/make_map_plan_cases.py` gets side-view cases.
* **Recipe.** `rooms_recipe` writes `game/maps/rooms/<room_id>.tscn` (user_seed), the exits
  with their targets, the save station, the pickups and the enemies (T14.07) from the plan; the
  boot scene's first scene is the start room. `minimap_recipe` renders rooms like any map.

**Tests**
* `room_plan`: deterministic; the room count; every room reachable through exits; the
  critical path order; no VAL-027/028 over 200 seeds; the option bounds (the schema refuses
  `rooms` below `len(abilities) + 3`).
* The stored plan: a regeneration with a different seed builds nothing new and changes no room;
  an appended room is built and joined; a hand-removed exit on an edited room gives VAL-028 as
  a warning and the build succeeds; the same on an unedited room is repaired and reported.
* `test_rooms.gd`: an exit changes the room and keeps velocity; the camera clamps; the parallax
  layers scroll at their factors.
* The preview draws one cell per room.

**Done when**
* The tests pass.

---

## T14.07 — Side-view enemies and the guardian

**Depends on:** T14.06
**Files:** `archetypes/metroidvania/enemies/patrol.gd`, `flyer.gd`, `shooter.gd`, `guardian.gd`,
`enemy_base.gd` (all new), `builder/recipes/metroidvania/enemy_recipes.gd`, `builder/recipes/data_recipe.gd`
(enemy definitions for the archetype), `godot_templates/tests/unit/test_side_enemies.gd` (new)

**Spec**
* `RpgSideEnemy` (CharacterBody2D with the shared hurtbox and health): takes damage, knockback
  along x, drops loot (the ARPG's loot table), is persistent (dead stays dead per room until a
  save station is used, then respawns, as a metroidvania does).
* **Patrol:** walks on its platform, turns at an edge or a wall (a `RayCast2D` ahead and down),
  hurts on contact. **Flyer:** no gravity; hovers on a sine, chases within 5 tiles, returns to
  its anchor. **Shooter:** stands, fires a projectile (T14.01) at the player every 1.5 s when
  in line of sight within 8 tiles. The kind comes from the enemy asset's tags (`fly`, `bat`,
  `bird` → flyer; `shoot`, `turret`, `archer` → shooter; else patrol), overridable in the
  catalog.
* **Guardian:** the BOSS asset (or the ENEMY with the most HP) in the guardian room: 20 HP at
  tile size 16 scaled by the stats, three phases (walk and lunge; add a jump that shakes the
  room and drops a projectile from the ceiling; faster), telegraphed by a 0.4 s `hurt`-tinted
  pause; the room's exits close (gates) while it lives; its death opens them, grants the first
  ability of the plan and sets `defeated:<id>`.
* `data_recipe` gives each enemy of the archetype a definition with HP, attack, XP and gold from
  its `enemy_definition` defaults.

**Tests**
* The patrol turns at an edge and a wall; the flyer returns; the shooter fires on sight only.
* The guardian's phases change at the HP thresholds; death opens the exits and grants the
  ability.
* Persistence across a room change and respawn after a save.

**Done when**
* The tests pass.

---

## T14.08 — HUD, room map and save stations

**Depends on:** T14.07
**Files:** `archetypes/metroidvania/ui/hud.gd`, `save_station.gd`, `builder/recipes/metroidvania/hud_recipe.gd`,
`godot_templates/addons/rpg_runtime/ui/minimap.gd` and `world_map_menu.gd` (room mode),
`world/minimap_data.gd`, `core/game_state.gd` (`room_fog`), `core/save_manager.gd` (save stations
as the save point when the archetype says so), `combat/defeat_policy.gd`, `ui/strings.gd`,
`godot_templates/tests/unit/test_minimap.gd`, `test_save_manager.gd`, `test_metroidvania_ui.gd` (new)

**Spec**
* **HUD:** HP as pips (one per 4 HP, from the UI asset's frame or a generated pip), the
  abilities as icons that light up when granted, the equipped weapon, gold. Toasts for pickups.
* **Room map:** the minimap and the world map show rooms as cells of the world grid: visited
  rooms filled, the current one outlined, save stations and unused pickups marked, the exits
  as notches. Visited rooms are a **new optional save key** `room_fog` (`{room_id: true}`), so
  the top-down `map_fog` keeps its meaning and a top-down save is untouched.
* **Save stations:** `RpgSaveStation` (a `RpgSideInteractable` → the save menu). The
  archetype's settings (`metroidvania_mode`) make the pause menu's *Save* say *Save at a
  station* and disable it; autosave happens on every room change into the slot `auto`. Using a
  station restores HP, respawns the room's enemies and sets the respawn point; the defeat
  policy returns the player to the last station used with the state of the autosave (the
  metroidvania convention: progress since the last save is kept, position is not).

**Tests**
* The HUD reflects HP, abilities and gold.
* The room fog marks the visited rooms and survives a save; a top-down save is unchanged; the
  1.0 save fixture loads.
* A station saves, restores HP and respawns enemies; the defeat policy returns to it.

**Done when**
* The tests pass.

---

## T14.09 — Side-view sample pack and *Try the sample*

**Depends on:** nothing
**Files:** `sample_pack_side/` (new), `tools/build_sample_pack.py` (`--side`), `tools/sample_audio.py`,
`rpggen/paths.py` (the bundled packs), `packaging/rpggen.spec`, `rpggen/gui/pages/welcome_page.py`,
`rpggen/gui/wizard.py`, `tests/gui/test_sample_pack.py`, `tests/unit/test_tools_fixtures.py`,
`THIRD_PARTY_NOTICES.md`

The bundled sample pack is a top-down village and stays as it is (ground rules). A platformer
needs its own.

**Spec**
* `sample_pack_side` is a second CC0 pack, drawn by `build_sample_pack.py --side` with the same
  programmatic style as the first (no sourced art, so no new licence): a 16-px tile sheet
  (ground, one-way platforms, a ladder, spikes, a breakable block), a hero strip (idle, run,
  jump, fall, climb, attack, dash, hurt, facing right), a patrol enemy, a flyer, a guardian, a
  save bench, ability orbs, three parallax backgrounds, a sign, an NPC with a portrait, a UI
  panel, the same sound set as the first pack, and `LICENSE` (CC0) with `SOURCE.txt`. About the
  size of the first pack, so the installer grows by a few hundred kilobytes at most.
* **Try the sample** on the welcome view becomes a split button: *Top-down village*
  (today's path, unchanged, the default) and *Side-view cave* (the new pack, archetype
  `metroidvania`, the same walk to the Options page). The second entry is hidden while
  `METROIDVANIA_AVAILABLE` is false.
* The pack has its own golden and is in the perf corpus (T14.11).

**Tests**
* The pack builds deterministically; its golden; the welcome view's two entries and the
  state each one fills; the first entry's state is byte-identical to 1.1's.

**Done when**
* The tests pass and the top-down sample's golden and screenshots are unchanged.

---

## T14.10 — Wizard: the Metroidvania card, roles, options and preview

**Depends on:** T14.08, T14.09
**Files:** `rpggen/features.py` (`METROIDVANIA_AVAILABLE`), `rpggen/gui/pages/archetype_page.py`,
`rpggen/gui/pages/mapping_page.py`, `rpggen/core/mapping.py`, `rpggen/core/requirements.py`,
`rpggen/core/sound_slots.py` (`sfx_jump`, `sfx_land`, `sfx_dash`, `sfx_ability`, fixed slots),
`rpggen/core/options.py`, `rpggen/gui/models/options_model.py`, `rpggen/gui/pages/options_page.py`,
`rpggen/gui/widgets/options_sections.py`, `rpggen/gui/widgets/binding_table.py` (rows for
`jump`, `dash`, `attack`, `down`, shown for this archetype), `rpggen/gui/widgets/map_preview.py`,
`rpggen/gui/pages/welcome_page.py` (the dashboard's third card drawing, T13.08), `rpggen/core/config.py`,
`rpggen/core/orchestrator.py` (`ARCHETYPE_SMOKE_STEPS`), `rpggen/core/staging.py` (`ARCHETYPES`),
`rpggen/core/dry_run.py`, `rpggen/core/report.py`, `rpggen/cli.py` (`--archetype metroidvania`),
`godot_templates/project_files/README.metroidvania.md` (new), `tests/gui/test_archetype_page.py`,
`tests/gui/test_options_page.py`, `tests/gui/test_mapping_page.py`, `tests/unit/test_config.py`,
`tests/unit/test_sound_slots.py`, `tests/gui/test_layout_fit.py`

**Spec**
* A third card, **Metroidvania** (Run → Jump → Find an ability → Open the way → Explore), drawn
  with the pack's art like the others (T12.34), at the device pixel ratio (T13.10): the
  player's `jump` or `run` frame if it has one. The page's hint reads `pack_view` (T14.02): a
  pack that looks side-view suggests this card, a top-down pack shows "Your characters have
  walk-down animations; a metroidvania uses side-view sprites" under the card without disabling
  it. A player without a `jump` animation gets the ASSET-030 line as the ARPG's swing warning
  is shown.
* The card is disabled with the tooltip "Coming in a later version" while
  `METROIDVANIA_AVAILABLE` is false; T14.13 sets it true. The three cards fit at the minimum
  window size in both themes (T12.16).
* Mapping: the archetype's role list and labels; the Sound section's four new fixed slots,
  filled by name as the others (`jump.wav`, `land`, `dash`, `powerup`).
* Options: the *Starter map* box becomes *Starter world* for this archetype: rooms, room size,
  the abilities (checkboxes in the plan's order), enemies and pickups, with the
  `rooms ≥ abilities + 3` bound enforced live; the preview is the side-view one of T14.06; the
  layer list is the room layers; *Navigation* is hidden (no pathfinding); the bindings table
  shows the four new actions; the summary panel and the dry run describe the world ("6 rooms,
  2 abilities, a guardian"). The factory presets (T13.06) apply with `navigation` ignored.
* The generated README (`README.metroidvania.md`) explains the controls, the rooms folder, how
  to add a room (copy one, set the exits, or add a row in the wizard), the abilities table, the
  gates, enemies by tag, save stations and the map.
* The CLI accepts the archetype; the report names it; `dry_run` plans the world.

**Tests**
* The card's state with the flag on and off; the hint for a side-view and a top-down pack.
* The options model for the archetype; the bound; the summary text; the config round trip with
  the new `starter_map` keys; the bindings rows; T12.16 for the third archetype in both themes.

**Done when**
* The tests pass with the flag on in the test session (the gate flips the default).

---

## T14.11 — Metroidvania smoke steps and integration test

**Depends on:** T14.10
**Files:** `godot_templates/builder/smoke/smoke_steps_metroidvania.gd` (new),
`tests/integration/test_m14_side_sample.py` (new), `tests/integration/test_all_synthetic_packs.py`,
`tests/integration/test_determinism.py`, `tests/perf/test_perf.py` (a ceiling for the side-view
sample), `.github/workflows/*.yml` (the integration job split per archetype)

Appended after the M6 sequence (title, new game, dialogue, inventory, save and load):
1. `jump_clears_gap` — in the start room, run right and jump; the player lands on the far side of
   the 3-tile gap.
2. `one_way_platform` — jump through the one-way platform from below and stand on it; press down
   + jump and fall through.
3. `hazard_hurts_and_returns` — walk onto the spikes; HP drops by 1 and the player is back on the
   last safe ground within 1 s.
4. `gate_blocks` — at the double-jump ledge, jump; the player does not reach the ledge within 2 s.
5. `room_transition` — walk through the east exit; the current room changes and the player
   appears at the matching west exit with the same facing.
6. `npc_talks` — talk to the side NPC; the dialogue runs and the NPC faces the player.
7. `guardian_dies` — enter the guardian room; the exits close; boost attack to 99 and attack until
   `died`; the exits open and `abilities` contains the first ability.
8. `double_jump_reaches_ledge` — back at the ledge, jump twice; the player stands on it.
9. `pickup_dash` — touch the dash orb; `abilities` contains `dash`; the toast is shown.
10. `dash_crosses_gap` — at the 6-tile gap, dash; the player lands across.
11. `save_station_persist` — use the station; quit to the title; continue; the player is at the
    station with both abilities, and the room's enemies are back.
12. `end_room` — reach the end room and talk to the NPC; the credits flag is set.

**Tests**
* `test_m14_side_sample.py` generates the side-view sample pack as `metroidvania`, validates,
  runs the smoke test and asserts the step list `M14_STEPS`; the synthetic `platformer` pack
  passes too, and the determinism test covers the archetype.
* The `basic16` pack (no jump animation) generates as `metroidvania` with ASSET-030 and passes
  the smoke test with the idle frame in the air.
* The perf ceiling for the side-view sample; CI runs the three archetypes' integration suites
  as three jobs.

**Done when**
* The integration tests pass locally with `RPGGEN_GODOT` set, and in CI.

---

## T14.12 — Documentation, screenshots and changelogs

**Depends on:** T14.11
**Files:** `README.md`, `docs/user_guide.md`, `docs/status.md`, `docs/regeneration.md` (rooms and
the stored plan), `docs/errors.md` (generated), `docs/spec/02_SCHEMAS.md`, `docs/spec/03_ERROR_CODES.md`,
`docs/architecture.md` (§48: more archetypes), `CHANGELOG.md`, `godot_templates/addons/rpg_runtime/CHANGELOG.md`
and `README.md`, `godot_templates/project_files/README.template.md`, `tools/make_doc_screenshots.py`,
`docs/images/*`, `tests/gui/test_doc_screenshots.py`

* The user guide: a section **Metroidvania** (choosing it, the side-view sample, the roles, the
  world options, playing: controls, abilities, rooms, save stations, the map; editing rooms in
  Godot; adding a room). The README's first paragraph names three archetypes.
* Screenshots: the Archetype page with three cards, the side-view preview, the welcome view's
  split button. `test_the_screenshots_match_the_files_the_guide_uses` passes.
* `docs/status.md`: M14 done; the manual rows for M14 (T14.13) are listed.
* `CHANGELOG.md` gets `1.2.0`; the runtime changelog too, with the path shims and the new
  optional save keys.

**Done when** the docs test passes and no document says "two archetypes".

---

## T14.13 — Gate (1.2.0)

**Depends on:** T14.12

* `METROIDVANIA_AVAILABLE = True`; the wizard's metroidvania path is covered by an automated GUI
  integration test (as T9.08 asked for the ARPG).
* Every suite is green on Windows and Ubuntu, on both PySide6 legs; perf is within its
  ceilings, including the new one.
* T12.16 passes at the minimum size in both themes for all three archetypes.
* All three archetypes pass the smoke test on their sample packs and every synthetic pack,
  including `platformer`; generated projects contain only their own archetype folder (the
  template test of T14.01).
* **Upgrade test:** ARPG and turn-based projects generated by the `v1.1.0` build regenerate
  without a prompt, their maps and `game/` byte-identical, their TileSets unchanged, and a user
  script that preloads an old combat path still runs.
* The corpus (T12.26) is unchanged on all four measures after T14.02.
* The top-down sample pack's golden and screenshots are unchanged.
* Manual rows: play the side-view demo to the end room with a gamepad (jump feel, coyote time,
  the wall slide, the guardian's telegraphs); talk to the side NPC and open a chest from both
  sides; drop an object from the dock into a room; add a room in the wizard and regenerate;
  break a block, save at a station, die, and check the block stays broken; generate a
  metroidvania from a real side-view pack you own.
* `docs/status.md` lists nothing from this milestone as open except the manual rows.

**Done when** all of the above is true; then tag `v1.2.0`.
