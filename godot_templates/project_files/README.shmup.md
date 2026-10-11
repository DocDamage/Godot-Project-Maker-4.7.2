## 22. Stages, enemies and bosses (shoot 'em up)

The game is a run through stages. Your ship flies over a scrolling background, shoots waves of
enemies, picks up power-ups and beats a boss at the end of every stage. You have lives and a
score; there is no village, no inventory and no party, so the sections above about maps, doors,
shops and quests do not apply to it.

| Action | Keyboard | Gamepad |
|--------|----------|---------|
| Fly | W A S D, arrow keys | D-pad, left stick |
| Shoot (hold) | Z, J, left mouse button | A (cross) |
| Bomb | X, K | B (circle) |
| Fly slowly (focus) | Shift | left trigger |
| Pause | Escape, Tab | Start |

(The bindings are in the Project Settings under **Input Map**.)

- Only **one point** in the middle of your ship can be hit: its picture is much larger than that.
- A hit costs a **life**; the ship comes back blinking and cannot be hit for three seconds. Its
  weapon is back at level 1 and its bombs are refilled.
- A **bomb** takes every enemy bullet off the screen and hurts everything on it.
- **Power-ups** drift toward you: a weapon level (up to 3), another weapon (spread, laser,
  homing), a bomb, a life, a shield that takes one hit, or points.
- The **multiplier** grows with every five kills without being hit and is back at x1 after a
  hit. A formation shot whole pays a bonus.
- After the last life you may **continue**: the stage starts again and your score stays.
- The game **saves by itself** when a stage begins; *Continue* on the title screen starts that
  stage again. The ten best runs are kept in the **High scores** of the title screen.

### Where things are

| What | Where |
|------|-------|
| The stages of the run, with their waves and bosses | `game/data/stages.json` (yours) |
| The same list as rpggen planned it | `generated/data/stages.json` (rewritten on every build) |
| The plan the stages come from | `rpggen/world_plan.json`, the section `stages` |
| The scene of each stage | `generated/scenes/stages/stage_01.tscn`, … |
| The ship, the explosion, the power-up, the boss | `generated/scenes/shmup/` |
| The enemies | `generated/scenes/shmup/enemies/` (`popcorn_01.tscn`, `turret.tscn`, `asteroid.tscn`, `carrier.tscn`) |

Everything under `generated/` is made again when you regenerate. `game/data/stages.json` is
written once and then left alone: change it freely.

### Adding or changing a wave

Open `game/data/stages.json`. Every stage has a list `waves`; a wave looks like this:

```json
{
  "id": "w03",
  "enemy": "popcorn",
  "scene": "res://generated/scenes/shmup/enemies/popcorn_01.tscn",
  "formation": "v",
  "count": 5,
  "gap": 28,
  "trigger": "progress",
  "at": 500,
  "position": [0, -204],
  "shoots": true,
  "bonus": 500
}
```

- `scene` is the enemy that comes, `count` how many, `formation` how they stand (`line`,
  `column`, `v`, `circle`, `sine`) and `gap` the px between two of them.
- `at` is how far the stage has scrolled, in px, when the wave appears (`trigger` may also be
  `time`, with `at` in seconds, or `after`, with `after` naming the wave that has to be cleared
  first). Add `"blocking": true` and the stage stops scrolling until the wave is cleared.
- `position` is where the middle of the formation appears, in px from the middle of the screen;
  a place just beyond the edge the enemies come from looks best. With `"anchor": "stage"` it is
  a place in the stage instead, which is what turrets and rocks use.
- Small enemies fly a `path`: `straight`, `sine`, `swoop`, `sweep`, `dive` or `close`; without
  one a line sweeps, a V dives and a circle closes. `shoots` lets each fire one shot at you.
- `drop` makes the last enemy of the wave leave a power-up: `weapon_up`, `weapon:spread`,
  `weapon:laser`, `weapon:homing`, `bomb`, `life`, `shield` or `points`.
- `fast` and `tough` make a wave harder: a factor for the speed of its bullets and for the
  health of its enemies. A turret's `fan` is how many bullets it fires at once.

To add a wave, copy one, give it a new `id` and another `at`. Keep the waves in the order of
their `at`, and the last one at least half a screen before the end of the stage (`length`).

A **boss** is the entry `boss` of a stage: `health`, `points` and its `phases`. Each phase lasts
until the boss's health has fallen to the fraction `until` and has one of the attacks `ring`,
`fan`, `spiral`, `aimed` or `sweep`, an `interval` between attacks in seconds, a `count` of
bullets and their speed `fast`.

### More stages

A new stage is one row of **Added stages** in the options (`starter_map.added_stages` in
`rpggen/generator_config.json`: `[{ "name": "Asteroid Belt" }]`) and another generation. The
stages you have stay as they are, and the new one
follows the last, a little harder. rpggen puts it into `generated/data/stages.json`; the game
plays every stage of that list that your own list does not have. To change the new stage, copy
its entry into `game/data/stages.json`.

To use your own enemy, make a scene whose root has the script
`res://addons/rpg_runtime/archetypes/shmup/enemies/popcorn.gd` (or `turret.gd`, `asteroid.gd`,
`carrier.gd`), save it under `game/`, and name it as the `scene` of a wave.
