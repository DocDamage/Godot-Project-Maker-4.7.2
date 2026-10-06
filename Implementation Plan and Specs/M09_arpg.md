# M9 — Action RPG Archetype

**Goal:** real-time combat on the overworld. The player attacks with hitboxes that are active only on attack frames, enemies run a component-based state machine, damage and knockback work, a HUD exists, and an ARPG smoke test passes. When this milestone is done, the wizard's ARPG card is enabled (`ARPG_AVAILABLE = True`).

**Files live in** `addons/rpg_runtime/archetypes/arpg/` and `builder/recipes/arpg/`.

---

## T9.01 — Damage primitives

**Depends on:** M8 gate
**Files:** `damage_info.gd`, `hitbox.gd`, `hurtbox.gd`, `health.gd`, tests

```gdscript
class_name RpgDamageInfo extends RefCounted
var amount: int
var source: Node                 # the attacker actor
var knockback: Vector2           # direction * strength (px/s impulse)
var stun_s: float = 0.0
var crit := false

class_name RpgHitbox extends Area2D
@export var damage: int = 1
@export var knockback_strength: float = 160.0
@export var team: StringName = &"player"   # "player" | "enemy"
var active := false : set = set_active      # toggles monitoring + CollisionShape disabled (set_deferred)
var _hit_this_swing: Dictionary = {}        # hurtbox instance_id -> true; cleared when activated
signal hit(hurtbox: RpgHurtbox)
# area_entered(area): if area is RpgHurtbox and area.team != team and not already hit this swing:
#     build RpgDamageInfo (amount from owner's stats via damage_formula), area.receive(info), emit hit

class_name RpgHurtbox extends Area2D
@export var team: StringName = &"player"
@export var health_path: NodePath
var invulnerable_until_ms := 0
signal damaged(info: RpgDamageInfo)
func receive(info: RpgDamageInfo) -> void   # ignore if Time.get_ticks_msec() < invulnerable_until_ms; else health.take(info); emit damaged

class_name RpgHealth extends Node
@export var stats_path: NodePath   # RpgStats source
signal died
signal changed(hp: int, max_hp: int)
func take(info: RpgDamageInfo) -> void   # hp -= amount (min 0); emits; died when 0
func heal(n: int) -> void
```

* Collision layers (ARCHITECTURE §17): a player hitbox is on layer 7 with mask 10; an enemy hitbox on 8 with mask 9; the player hurtbox on 9; enemy hurtboxes on 10.
* Real-time damage formula (`arpg_math.gd`): `max(1, attack - defense / 2)`, × 1.5 on a crit (`crit_chance` from `stats.extra`, default 0.05), using `GameState.rng`.
* Invulnerability: the player gets 0.6 s after being hit; enemies get 0.15 s.

**Tests:** a hitbox hits the same hurtbox once per activation; team filtering; invulnerability window; health reaches zero → `died` is emitted exactly once.

---

## T9.02 — Player combat state machine

**Depends on:** T9.01
**Files:** `player_combat.gd`, `state_machine.gd`, the player recipe variant

`state_machine.gd` is a generic, tiny FSM:
```gdscript
class_name RpgStateMachine extends Node
var state: StringName
var states: Dictionary = {}        # name -> {enter: Callable, update: Callable, exit: Callable}
signal changed(from: StringName, to: StringName)
func add(name, enter, update, exit) / func go(name) / func _physics_process(d): states[state].update.call(d)
```

**Player states:** IDLE, MOVE, ATTACK, HURT, DODGE, DEAD.

| State | Enter | Update | Exit to |
|-------|-------|--------|---------|
| IDLE/MOVE | — | Movement from input. `attack` pressed → ATTACK; `dodge` pressed and the cooldown is ready → DODGE. | — |
| ATTACK | Stop movement (or 20% speed). Play `attack_<facing>`; if it is missing, play the generic swing effect (T9.05) and keep `idle_<facing>`. Reset the frame counter. | Activate the hitbox exactly on `active_frames` (indices into the attack animation, read on `frame_changed`). For the generic swing: active from 0.08 s to 0.2 s. **Input buffer:** an `attack` press in the last 30% of the animation queues the next attack. | When the animation finishes (or 0.35 s for the generic swing) → IDLE |
| HURT | Play `hurt_<facing>`, or `hurt`, or flash the sprite. Apply knockback to `Movement.external_velocity`. | Lasts 0.25 s. | IDLE |
| DODGE | Invulnerable for the duration. Velocity = facing × 220 px/s for 0.2 s. Cooldown 0.6 s. | — | IDLE |
| DEAD | Disable input. Play `death`, or fade out. After 1.5 s → the defeat policy (same as turn-based: load the last save, or respawn at the default spawn with full HP). | — | — |

* The hitbox node `AttackHitbox` is positioned toward the facing direction: offset = facing vector × (frame size × 0.5), with shape size `tile × 0.9`. The position updates when facing changes and is never updated during an active swing.
* The scene recipe adds `Hurtbox`, `AttackHitbox`, `Health` and `PlayerCombat` to the player when the archetype is `arpg`. This is decided at build time from the config.

---

## T9.03 — Enemy AI components

**Depends on:** T9.01
**Files:** `enemy_ai.gd`, `components/detection.gd`, `components/chase.gd`, `components/wander.gd`, `components/enemy_attack.gd`, `components/loot_drop.gd`, `pickup.gd`, `builder/recipes/arpg/enemy_recipes.gd`, tests

`RpgEnemyDefinition.behavior` keys for the ARPG, with these defaults:
```json
{ "vision_px": 96, "lose_px": 160, "attack_range_px": 18, "attack_cooldown_s": 1.2,
  "windup_s": 0.35, "active_s": 0.15, "move_speed": 45, "chase_speed": 60,
  "wander_radius_px": 32, "wander_pause_s": [1.0, 2.5], "knockback_resist": 0.0,
  "nav_mode": "direct" }
```

**States:** IDLE, WANDER, ALERT, CHASE, ATTACK, HURT, STUNNED, DEAD.
* **Detection:** the player is within `vision_px`, **and** a line-of-sight raycast from the enemy to the player (mask world(1)) hits nothing → ALERT (0.3 s, play `idle_<facing>` facing the player, show a "!" Label briefly) → CHASE.
* **CHASE:** move toward the player at chase speed. `nav_mode == "direct"` uses the direction vector plus `move_and_slide`. `"agent"` uses `NavigationAgent2D.target_position` and `get_next_path_position()` (T9.06). If the distance exceeds `lose_px` for 2 s → WANDER (returning toward home first). If the distance is within `attack_range_px` and the cooldown is ready → ATTACK.
* **ATTACK:** windup (stop; telegraph with a modulate tint pulse) → the hitbox is active for `active_s` → cooldown. The hitbox is placed toward the facing direction, like the player's.
* **HURT:** knockback × (1 − `knockback_resist`), 0.2 s. Then return to CHASE.
* **STUNNED:** when `info.stun_s > 0`.
* **DEAD:** disable collisions; play `death` or fade out; `LootDrop.drop()`; `GameState.set_flag(entity_id, "defeated", true)`; emit `entity_defeated`; give XP (`stats.add_experience`) and gold; free after 0.6 s.
* `LootDrop` spawns `pickup.tscn` instances for item loot. A pickup is an Area2D on layer interactables, with mask player, that auto-collects on overlap and bobs with a tween. Gold is added immediately with a notify toast.
* **Component separation:** `enemy_ai.gd` holds only the FSM. Each component exposes small methods (`detection.can_see_player()`, `chase.step(delta)`, `attack.try_start()`), so behaviors can be swapped.
* Enemy scenes: `generated/scenes/enemies/<slug>.tscn` inherits `actor_base`. It adds Hurtbox, Health, Hitbox, the components, an `RpgPersistent`, a `RayCast2D` for line of sight and a `NavigationAgent2D` (disabled when the mode is direct).
* **Spawns:** the starter map recipe places 2 enemies (`enemy_spot` and +4 tiles) when the archetype is `arpg`.

**Tests:** a scripted detection test with a fake player position (in range but behind a wall → no detection); chase gives up after `lose_px` for 2 s; the attack cooldown is respected.

---

## T9.04 — HUD

**Depends on:** T9.02
**Files:** `builder/recipes/arpg/hud_recipe.gd`, `archetypes/arpg/ui/hud.gd`

* `generated/scenes/ui/hud_arpg.tscn`: a CanvasLayer (layer 20) with the top-left HP bar (a `TextureProgressBar` using UI assets if present, otherwise a `ProgressBar` styled by the theme), an HP text, a gold counter (coin ITEM icon if one exists), a quick-item slot (icon + quantity; `quick_item` uses it), and a level/XP thin bar under the HP bar.
* It updates through Events (`player_damaged`, `player_healed`, `gold_changed`, `experience_gained`, `level_up`, `item_*`). It never polls every frame.
* The quick-item selection is the first consumable by default. It can be changed in the inventory menu with a "Set quick item" button. That button exists only in arpg mode; the archetype decides whether the inventory menu shows it.

---

## T9.05 — Generic swing effect

**Depends on:** T9.02
**Files:** `builder/recipes/arpg/swing_recipe.gd`, `archetypes/arpg/swing_effect.gd`

For characters without attack animations: a generated `SpriteFrames` resource with 4 frames of an arc, drawn **in code** into an `Image` (anti-aliasing off; white arc with a 1 px dark outline; sized `tile × 1.5`), saved to `generated/effects/swing_frames.tres`. It is played at the hitbox position and rotated to the facing direction. If the pack has an EFFECT asset tagged or named `slash` or `swing` with a strip, that asset is used instead.

---

## T9.06 — Optional navigation

**Depends on:** T9.03
**Files:** `tileset_recipe.gd` (navigation layer), `builder/recipes/arpg/navigation_recipe.gd`

* When `config.features.navigation` is true:
  * The TileSet gets navigation layer 0. Every GROUND-role tile **without** collision gets a full-tile navigation polygon (`td.set_navigation_polygon(0, poly)`) ⚠ VERIFY the API.
  * Enemies use `nav_mode = "agent"`.
* Document in the generated README that, for large maps, the user should bake a `NavigationRegion2D` instead. Tile-based navigation is the simple default.

---

## T9.07 — ARPG smoke steps

**Depends on:** T9.02–T9.05
**Files:** `builder/smoke/smoke_steps_arpg.gd`

Appended after the M6 sequence:
1. `enemy_detects` — teleport 3 tiles from enemy 1 with a clear line of sight; within 2 s the enemy state is CHASE.
2. `player_attack_hits` — face the enemy at 1 tile; press `attack`; within 0.5 s the enemy's `Health.changed` fires.
3. `no_damage_outside_active_frames` — start an attack while the enemy is outside the hitbox, then teleport the enemy into the hitbox's area **after** the active window; expect no damage.
4. `enemy_dies` — boost the player's attack to 99 and attack until `died` fires (timeout 5 s); expect XP and gold gained, plus the flag `defeated`.
5. `player_hurt_invuln` — let enemy 2 hit the player; expect HP to drop once; a second hit within 0.6 s does nothing.
6. `dodge` — press `dodge`; expect the position to change by about 44 px (±8) and invulnerability during the dodge.
7. `persist` — save, reload; the dead enemy is still absent.
8. `death_policy` — set HP to 1 and let an enemy hit; expect a respawn with HP > 0.

---

## T9.08 — Milestone Gate M9

- [ ] The ARPG smoke test passes on the sample pack, `lpc_like` (which has attack animations) and basic16 (generic swing).
- [ ] Manual check: combat feels responsive. Attack buffering works, knockback is visible, enemies telegraph before hitting, and controller play works.
- [ ] `ARPG_AVAILABLE = True`; the wizard's ARPG path is covered by an automated GUI integration test.
- [ ] Generated ARPG projects contain only the `arpg` archetype folder, and the turn-based tests still pass.
