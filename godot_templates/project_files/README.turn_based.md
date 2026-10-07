
## 11. Battles and enemies (turn-based)

Walk into an enemy on the map and a battle starts. Pick **Attack**, **Defend**, **Item** or **Run**
with the arrow keys (or a gamepad) and confirm; when you attack, move the arrow over an enemy with
left and right, then confirm. **Cancel** steps back. **Skills** stays grey until you add skills.

- A victory gives experience, gold and loot; a level up shows a message. The enemy is gone for
  good (it stays gone after saving, loading and changing maps).
- **Run** can fail: the chance depends on the speed of both sides. After a successful escape the
  enemy ignores you for about a second and a half.
- If you lose, the game returns to your newest save. Without a save you wake up at the map's
  default spawn point with full health.

### Adding an enemy

1. Make the enemy's data: in `game/data/enemies/`, duplicate an enemy and change its name,
   stats, rewards and loot. `Behavior` tunes the fight: `{"turn_based": {"attack": 0.7,
   "defend": 0.3}, "items": ["potion"]}` makes it defend now and then and heal itself with a
   potion when it is low.
2. Open `game/maps/starter_map.tscn` and drag an enemy scene from `generated/scenes/enemies/`
   under `YSorted/Entities`. Give it its own **Entity Id** (for example
   `starter_map_enemy_002`) and, in the Inspector, your enemy data as its **Definition**.
3. To fight several enemies at once, fill the **Group** list. Turn on **Encounter On Interact**
   to start the battle with the interact key instead of by touching.

The battle commands (`game/data/battle_commands/`) can be retuned too, for example the order in
which they act (`Priority`). The battle scene itself is `generated/scenes/battle/battle.tscn`.
