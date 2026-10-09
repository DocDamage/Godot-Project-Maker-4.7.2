
## 22. Battles and enemies (turn-based)

Walk into an enemy on the map and a battle starts. Pick **Attack**, **Defend**, **Item**, **Skill**
or **Run** with the arrow keys (or a gamepad) and confirm; when you attack, move the arrow over an
enemy with left and right, then confirm. **Cancel** steps back. **Skill** lists the skills the
character knows and has the MP for (it is grey when there are none).

- A victory gives experience, gold and loot; a level up shows a message. The enemy is gone for
  good (it stays gone after saving, loading and changing maps).
- **Run** can fail: the chance depends on the speed of both sides. After a successful escape the
  enemy ignores you for about a second and a half.
- If you lose, the game returns to your newest save. Without a save you wake up at the map's
  default spawn point with full health.
- Attacks can miss: the faster side hits more often, and **Evade** (an extra stat that equipment
  can raise with a modifier such as `{"stat": "evade", "add": 0.1}`) makes a character harder to
  hit. A sleeping target is always hit.

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

### The party

Up to four characters fight together, the player included. A character who can join is a file in
`game/data/actors/<id>.tres` (name, picture, stats, skills); a dialogue line brings them in with the
event `join_party:<id>` and sends them away with `leave_party:<id>`, and the condition
`party:<id>` asks whether they are there. Everyone in the party acts in battle and shares the
experience; a member who falls stands up again after the battle. On the map the members walk
behind the player. The demo villager's companion joins when you ask (and leaves when you ask
again).

### Random encounters

Battles can also start while you walk through tall grass or a dark forest: an **encounter zone**.
The field map behind the east exit has one over its east half. To make your own, open a map and
press **Add encounter zone (over the selection)** in the Assets dock (Project tab): select some
nodes and the zone covers them, select a TileMapLayer and its painted cells become the zone (paint
a layer called `Encounters` and it is hidden in the game), or select nothing for a 6x6-tile square.
The zone's **Table** (`game/data/encounters/`) lists the enemy groups and how often each comes
(**Weight**); **Steps Per Encounter** is the average number of tiles between two battles; set
**Disabled Flag** (for example `bridge.repaired`) to stop the battles once that flag is true. After
every battle you can walk six tiles in peace.

### Skills, MP, elements and statuses

Skills live in `game/data/skills/` (the game starts with **Fire**, **Cure**, **Sleep** and the
enemies' **Venom**). A skill has a **Kind** (physical: the attack plus **Power**; magic: Power +
Magic x 2 - Resistance, never misses; heal: Power + Magic x 2; status: only the status), whom it
aims at (**Targets**: one or all enemies, one or all allies, self), an **MP Cost**, an
**Element**, a **Status** it inflicts with a **Status Chance**, and the statuses it **Cures**.

- A character's skills are in its actor data (`game/data/actors/`): **Skills** maps a skill to the
  level it is learned at, `{"cure": 1, "fire": 3}`. MP is in **Base Stats** (**Max Mp**). Every
  level adds 2 max MP to a character who has some; a level up and the `heal_full` dialogue event
  refill it.
- **Element Rates** (on enemies, characters, and worn armor and accessories) make an element hit
  harder or softer: `{"fire": 2.0}` is a weakness, `0.5` resists, `0` is immune, `-1` absorbs it
  as healing. A weapon's **Element** gives its attacks that element.
- Statuses: **Poison** (loses an eighth of max HP each round, the whole battle), **Regen** (heals
  a tenth), **Sleep** (loses its turns; a hit wakes it), **Silence** (no skills), **Blind** (hits
  half as often), **Haste** and **Slow** (speed x 1.5 / x 0.5). They last a few rounds and end
  with the battle. **Status Immune** lists the ones that never take hold; **Attack Status** with
  **Attack Status Chance** makes plain attacks poison or blind. The **Antidote** cures poison and
  the **Ether** restores 10 MP (the village shop sells both).

### Enemy tactics

An enemy rolls its `turn_based` weights each turn; a key may also be a skill
(`{"attack": 1.0, "fire": 0.5}`). For a planned fight, add rules: the first one that holds is used.

```
"turn_based_rules": [
	{"when": "hp<30", "use": "cure", "target": "weakest", "once": true},
	{"when": "every:3", "use": "fire"},
	{"when": "foe_lacks:poison", "use": "venom", "chance": 0.5}
]
```

`when` joins conditions with `and`: `hp<50` (its own HP in percent), `foe_hp<30` (the weakest
opponent), `mp>=4`, `round>=3`, `every:3`, `alone`, `ally_down`, `has:poison`, `foe_has:sleep`,
`foe_lacks:poison`, and the dialogue conditions (`flag:boss.angry`, `var:alarm>=1`, ...).
`target` is `random` (the default), `weakest`, `strongest` or `self`; a status skill picks someone
who does not have the status yet. An enemy whose **Max Mp** is 0 casts for free; give it MP to
limit its spells. The validator (VAL-026) reports unknown skills, statuses and rule words.

The battle commands (`game/data/battle_commands/`) can be retuned too, for example the order in
which they act (`Priority`). The battle scene itself is `generated/scenes/battle/battle.tscn`.
