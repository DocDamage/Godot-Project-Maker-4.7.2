
## 11. Combat and enemies (action RPG)

Fighting happens on the map, in real time.

| Action | Keyboard | Gamepad |
|--------|----------|---------|
| Attack | J, left mouse button | X (square) |
| Heavy attack | K, right mouse button | Y (triangle) |
| Dodge | Shift | B (circle) |
| Quick item | Q | left shoulder button |

(The bindings are in the Project Settings under **Input Map**.)

- **Attack** swings in the direction you face. The hit area is switched on only on the attack
  frames, so a swing that has finished does not hurt anything. Pressing attack again near the end
  of a swing queues the next one.
- **Heavy attack** (`secondary_attack`) is a slower swing that deals 1.75 times the damage and
  pushes the enemy back 1.5 times as far. It cannot be chained into another attack, so use it when
  the enemy is open.
- **Dodge** is a short dash in the facing direction (about 44 pixels) during which you cannot be
  hurt. It needs 0.6 seconds to recharge.
- Being hit gives about 0.6 seconds of invulnerability and a little knockback. At 0 HP you fall;
  after a moment the game-over screen offers to continue from your newest save, to try the map
  again with full health, or to quit to the title (see "Saving, autosave and game over" above).
- The **HUD** (top left) shows your HP, experience, level, gold and the **quick item**. The first
  consumable you own is the quick item until you pick another one: open the inventory, select an
  item and press **Set quick item**.
- Enemies see you inside their vision radius when no wall is in between, show a `!`, run after you
  and tint themselves before they strike, so there is time to step aside. A defeated enemy gives
  experience and gold, may drop items you pick up by walking over them, and stays gone after saving
  and loading.

### Damage

`damage = max(1, attack - defense / 2)`, times 1.5 on a critical hit (5 % unless the attacker's
stats have `crit_chance` under **Extra**). All random numbers come from the game's seeded generator.

### Adding an enemy

1. Duplicate an enemy data file in `game/data/enemies/` and change its name, stats, rewards and
   loot. **Behavior** holds the tuning (pixel values are for the tile size of the project):
   `vision_px`, `lose_px`, `attack_range_px`, `attack_cooldown_s`, `windup_s`, `active_s`,
   `move_speed`, `chase_speed`, `wander_radius_px`, `wander_pause_s`, `knockback_resist` and
   `nav_mode` (`"direct"` or `"agent"`).
2. Open `game/maps/starter_map.tscn` and drag an enemy scene from `generated/scenes/enemies/` under
   `YSorted/Entities`. Give it its own **Entity Id** (for example `starter_map_enemy_003`) and your
   enemy data as its **Definition**.

### Attack animations and the swing

If the character has `attack_<direction>` animations they are played, and the hit area is live on
the animation's **active frames** (set in the animation editor of the audit; without them the middle
third of the animation is used). Characters without attack animations show a generated swing arc
(`generated/effects/swing_frames.tres`; a pack effect named or tagged `slash` or `swing` is used
instead) and hit between 0.08 and 0.2 seconds after the press.

### Navigation

Enemies walk straight at you and slide along walls. Turn on the **navigation** feature in the
wizard and the TileSet gets a navigation layer (every ground tile without collision is walkable) and
the enemies follow `NavigationAgent2D` paths around obstacles. For large maps bake a
`NavigationRegion2D` instead and keep `nav_mode` on `"agent"`.
