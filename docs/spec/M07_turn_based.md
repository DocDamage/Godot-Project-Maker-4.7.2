# M7 — Turn-Based Archetype

**Goal:** an overworld enemy triggers a battle scene. The battle runs on a data-driven command system with a seeded RNG, resolves to victory, defeat or escape, grants rewards, and returns to the map, where the enemy stays defeated across saves. A full smoke test passes.

**Files live in** `addons/rpg_runtime/archetypes/turn_based/` (runtime) and `builder/recipes/turn_based/` (recipes). The generator copies only the chosen archetype's runtime folder into a project. The template project contains both, so both are tested.

---

## T7.01 — Battle data

**Depends on:** M6 gate
**Files:** `battle_command.gd`, `commands/*.gd`, `battle_actor.gd`, tests

```gdscript
class_name RpgBattleCommand extends Resource
@export var id: StringName
@export var label: String              # tr key
@export var targets: int = 1           # 0 = self, 1 = one enemy, 2 = one ally, 3 = all enemies
@export var priority: int = 0          # higher acts first within the same round (Defend uses 10)
func can_use(user: RpgBattleActor, battle) -> bool: return true
func execute(user: RpgBattleActor, targets: Array[RpgBattleActor], battle) -> Array[Dictionary]:
	return []   # returns log entries: [{type:"damage"|"heal"|"text"|"status", target, amount, text}]
```

Concrete commands, each a script that extends `RpgBattleCommand`, with matching `.tres` instances generated in `game/data/battle_commands/` (user_seed):

| id | Behavior |
|----|----------|
| `attack` | Damage formula below. |
| `defend` | Sets `user.defending = true` until the user's next turn; incoming damage × 0.5 (rounded down, minimum 1). |
| `item` | Opens the item submenu (consumables only); `execute` calls `inventory.use(item, target.stats)`. |
| `skill` | A placeholder that is disabled (`can_use` returns false) until skills are added. The label shows "Skills (none)". |
| `run` | Escape chance `clamp(0.5 + (party_avg_speed - enemy_avg_speed) * 0.05, 0.1, 0.95)`. Not allowed when `can_escape` is false. |

**Damage formula** (in `battle_math.gd`, a pure static function, so it is unit-tested):
```text
base   = max(1, attacker.attack * 2 - defender.defense)
spread = rng.randf_range(0.9, 1.1)
crit   = rng.randf() < 0.05  → ×1.5
dmg    = max(1, floor(base * spread * (1.5 if crit else 1)))
if defender.defending: dmg = max(1, floor(dmg * 0.5))
```

```gdscript
class_name RpgBattleActor extends RefCounted
var id: StringName
var display_name: String
var stats: RpgStats               # copy for enemies; the live GameState stats for the player
var is_player_side: bool
var defending := false
var sprite_frames: SpriteFrames
var portrait: Texture2D
var alive: bool: get: return stats.hp > 0
```

**Tests:** damage table tests with a fixed seed (assert the exact values for 5 cases); escape chance clamping.

---

## T7.02 — Turn manager and battle controller

**Depends on:** T7.01
**Files:** `turn_manager.gd`, `battle_controller.gd`, tests

**Turn order** for each round: all living actors sorted by `(chosen command priority desc, speed desc, is_player_side desc, id asc)`. Speed ties are broken deterministically, never randomly.

**State machine** (`battle_controller.gd`, `enum State { INIT, ROUND_START, PLAYER_CHOOSE, ENEMY_CHOOSE, EXECUTE, CHECK, VICTORY, DEFEAT, ESCAPED, END }`):

```text
INIT          → build actors from EncounterData + GameState → ROUND_START
ROUND_START   → clear defending flags of actors whose turn starts → PLAYER_CHOOSE
PLAYER_CHOOSE → for each living player-side actor: UI requests command + targets
                (await ui.command_chosen) → ENEMY_CHOOSE
ENEMY_CHOOSE  → AI picks for each living enemy → EXECUTE
EXECUTE       → for actor in turn order: skip dead; execute; append log; await ui.log_shown
                after each action → if outcome decided → CHECK (early exit)
CHECK         → all enemies dead → VICTORY; all players dead → DEFEAT; escaped → ESCAPED;
                else → ROUND_START
VICTORY       → compute rewards → show → END
DEFEAT        → show "Defeated" → END (result DEFEAT)
ESCAPED       → END
END           → emit finished(result)
```

* Every transition goes through `_set_state(s)`, which emits `state_changed(s)` (used by tests and smoke).
* **Enemy AI** (default): if hp < 25% and the enemy has a `heal`-capable item in `behavior.items` → use it; else `attack` a random living player-side target via `GameState.rng`. The weights come from `behavior.turn_based = {"attack": 1.0, "defend": 0.0}` and are rolled with the seeded RNG.
* **Rewards:** XP = sum of enemy `xp_reward`; gold = sum of `gold_reward`; items = loot table rolls. Apply them: `stats.add_experience` (emit `level_up` per level), `GameState.gold +=`, `inventory.add`.
* **Defeat:** the result is DEFEAT. The overworld handler (T7.04) restores HP to 1 and returns the player to the last save if one exists, otherwise to the map's default spawn with full HP. This is a simple, documented policy.
* **Headless/test hook:** `battle_controller.auto_choose: Callable`. When it is set (smoke mode), it is called instead of waiting for the UI, returning `{command_id, target_index}`.

**Tests:** a scripted battle with fixed stats and seed → an exact sequence of states and final HP values; defending halves damage; early exit when the last enemy dies mid-round (remaining actions are skipped).

---

## T7.03 — Battle scene and UI

**Depends on:** T7.02
**Files:** `builder/recipes/turn_based/battle_scene_recipe.gd`, `archetypes/turn_based/ui/*.gd`

`generated/scenes/battle/battle.tscn`, built in code:
```text
Battle (Node2D, battle_scene.gd)
├── Background (TextureRect full-rect: a BACKGROUND-role asset if one exists, else a ColorRect gradient made of two ColorRects)
├── EnemySlots (Node2D) → up to 4 Marker2D in a row in the upper half
├── PartySlots (Node2D) → up to 4 Marker2D lower right
├── Controller (Node, battle_controller.gd)
└── UI (CanvasLayer)
    ├── CommandPanel (PanelContainer → VBox of Buttons: one per command .tres, in order attack/defend/item/skill/run)
    ├── TargetCursor (Control drawing a blinking arrow over the selected enemy)
    ├── ItemSubmenu (PanelContainer, hidden)
    ├── BattleLog (PanelContainer → Label, shows one entry at a time; confirm or 0.8 s auto-advance)
    ├── PartyStatus (VBox: name, HP bar, HP text per party member)
    └── EnemyStatus (VBox: name + HP bar per enemy)
```

* Enemy visuals: an AnimatedSprite2D using the enemy's sprite frames, playing `idle_down` (or the first available animation), scaled ×2 if the frame is 32 px or smaller.
* Hit feedback: a 0.1 s white flash (shader-free: tween `modulate` to (3,3,3) and back), a damage number Label that floats up and fades, and a short shake for a crit.
* Player side: the hero sprite facing up (`idle_up`) or `idle_left` if available.
* UI focus follows the M6 rules. Targets cycle with `move_left`/`move_right`, plus `confirm` and `cancel`.
* Music: the first AUDIO_MUSIC asset whose name contains `battle` (if any).

---

## T7.04 — Encounters on the overworld

**Depends on:** T7.03
**Files:** `archetypes/turn_based/turn_based_mode.gd` (extends RpgCombatMode), `archetypes/turn_based/overworld_enemy.gd`, `builder/recipes/turn_based/enemy_recipes.gd`

* `overworld_enemy.gd` is attached to enemy scenes (`generated/scenes/enemies/<slug>.tscn`, inheriting `actor_base`). It has:
  * `@export var entity_id`, `@export var definition: RpgEnemyDefinition`, `@export var group: Array[RpgEnemyDefinition]` (default: just the definition), and wander behavior (move to a random point within 2 tiles of home every 2–4 s, using the seeded RNG).
  * A contact area on layer triggers(6) with mask player(2). On contact (or on interact when `encounter_on_interact` is true), it builds `RpgEncounterData` and calls `SceneRouter.combat.start_encounter(data)`.
  * An `RpgPersistent` child, so a defeated enemy is freed on map load.
* `turn_based_mode.start_encounter(data)`: freezes player input, sets `GameState.pending_encounter`, calls `SceneRouter.push_scene("res://generated/scenes/battle/battle.tscn", data)`. When the battle finishes → `SceneRouter.pop_scene(result)`. Then `_on_finished(result)`: VICTORY → `GameState.set_flag(entity_id, "defeated", true)`, emit `entity_defeated`, and remove the enemy node if it is still present after pop. ESCAPED → give the player 1.5 s of invulnerability (the enemy contact area is disabled for that long). DEFEAT → the T7.02 policy.
* Enemy data recipe: for each ENEMY-role asset, create `game/data/enemies/<slug>.tres` (user_seed) with stats scaled by an index (`hp 12 + 4i`, `atk 4 + i`, `def 1 + i/2`, `xp 5 + 2i`, `gold 3 + i`) and loot `[{potion, 0.3, 1, 1}]`.
* The starter map recipe places one enemy at `enemy_spot` (`entity_id = starter_map_enemy_001`) if the map is being created.
* Encounter zones (random encounters in areas) are **deferred**. Document them as a future extension point: `RpgEncounterZone` Area2D with a step counter.

---

## T7.05 — Turn-based smoke steps

**Depends on:** T7.04
**Files:** `builder/smoke/smoke_steps_turn_based.gd`

Appended after the M6 sequence:
1. `encounter_start` — teleport next to the enemy and step into it; expect a scene change to Battle within 3 s.
2. `battle_victory` — set `auto_choose` to always attack enemy 0; to keep the test deterministic, set the player's stats to a smoke profile (`attack 99`) via `GameState.player_stats` before the encounter; await `encounter_finished` with VICTORY within 20 s.
3. `rewards_granted` — XP and gold increased by the enemy's rewards.
4. `returned_to_map` — the current map is `starter_map`; the player is within 1 px of the pre-battle position.
5. `enemy_stays_defeated` — the enemy node is gone; save slot 2; leave the map and come back (go to the interior and back); the enemy is still absent; load slot 2; the enemy is still absent.
6. `defeat_policy` — a fresh encounter via the debug `encounter` command with player `hp = 1` and `defense 0`, against an enemy with `attack 99`; expect a DEFEAT result and the player back on a map with hp > 0.

---

## T7.06 — Milestone Gate M7

- [ ] The full turn-based smoke test (M1 + M4 + M6 + M7 steps) passes on the sample pack, on `rpgmaker_like` and on `lpc_like`.
- [ ] Battle math and controller unit tests pass.
- [ ] Manual check: play a battle with the keyboard and with a gamepad; use a potion; run away; win; level up (the notification shows).
- [ ] Generated projects contain only the `turn_based` archetype folder.
- [ ] The Definition-of-Done checklist from ARCHITECTURE §50 holds for the turn-based archetype (minus the dock and terrain items, which come in M8).
