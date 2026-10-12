
## 22. Stages, weapons and bosses (run and gun)

The game is a run through stages, seen from the side. Your soldier runs to the right, jumps,
aims in eight directions, picks up weapons and beats a boss at the end of every stage. You have
lives and a score; there is no village, no inventory and no party, so the sections above about
maps, doors, shops and quests do not apply to it.

| Action | Keyboard | Gamepad |
|--------|----------|---------|
| Run, aim | W A S D, arrow keys | D-pad, left stick |
| Jump | Space, Z | A (cross) |
| Shoot (hold) | J, X, left mouse button | X (square) |
| Grenade | K, C | Y (triangle) |
| Aim without moving | Shift | left trigger |
| Grapple arm (when the game has it) | L, V | B (circle) |
| Crouch | Down (on the ground) | D-pad down |
| Drop through a plank | Down, then jump | D-pad down, then A |
| Pause | Escape, Tab | Start |

(The bindings are in the Project Settings under **Input Map**.)

- You **aim** with the directions you hold: up, the diagonals, forward, and straight down while
  in the air. Hold the aim button and the soldier stands still while you aim.
- **One hit is a death** unless the option *Health* gave the soldier more. A death costs a
  life; the soldier drops back in at the top of the screen, blinking and safe for two seconds,
  with the machine gun again (the option *Keep the weapon* changes that).
- The camera follows you to the right and **never goes back**. The left edge of the screen
  kills, or is a wall with the option turned off. A fall into a pit is a death; spikes are a hit.
- **Weapons** fly in on a carrier. Shoot it, and the weapon falls and lies there to be taken:
  the spread (five bullets in a fan), the laser (goes through what it hits) and the flame
  (short and fast). You start with the machine gun and three **grenades**.
- Some enemies hold the camera: the stage goes on when they are destroyed. The **boss** waits
  in the arena at the end of the stage.
- After the last life you may **continue**: the stage starts again and your score stays.
- The game **saves by itself** when a stage begins; *Continue* on the title screen starts that
  stage again. The ten best runs are kept in the **High scores** of the title screen.

### The grapple arm

With **Grapple arm** in the options the soldier has an arm that throws a hook along the aim
(up, the two upper diagonals, forward). A hook that holds to the side makes the soldier
**swing**: left and right push the swing, the button again (or jump) lets go, and the soldier
flies on with the speed it had. A hook that holds straight above **hoists** the soldier up to
the plank or ledge it hangs from.

With **Jump** switched off as well (the preset *Bionic*) the arm is the only way up and across:
the stages are then planned with a block over every pit and bed of spikes to swing from, and
with planks beside every step and wall to be hoisted on to. Down with the jump button still
drops through a plank.

### Where things are

| What | Where |
|------|-------|
| The stages of the run, with their enemies and bosses | `game/data/stages.json` (yours) |
| The same list as rpggen planned it | `generated/data/stages.json` (rewritten on every build) |
| The plan the stages come from | `rpggen/world_plan.json`, the section `stages` |
| The scene of each stage | `generated/scenes/stages/stage_01.tscn`, … |
| The soldier, the grenade, the explosion, the weapon pickup, the bosses | `generated/scenes/run_and_gun/` (`soldier.tscn`, `boss_wall.tscn`, `boss_walker.tscn`, `boss_flyer.tscn`, …) |
| The enemies | `generated/scenes/run_and_gun/enemies/` (`runner.tscn`, `sniper.tscn`, `turret.tscn`, `jumper.tscn`, `wall_cannon.tscn`) |

Everything under `generated/` is made again when you regenerate. `game/data/stages.json` is
written once and then left alone: change it freely.

The ground of a stage is painted into its scene (the layers *Ground*, *Platforms* and
*Hazards*, as in a room of a metroidvania); it is not read from `stages.json`. The scene is
made again when you regenerate, so to keep a stage you have painted on, save it under `game/`
and name it as the `scene` of its stage in `game/data/stages.json`.

### Adding or changing a group of enemies

Open `game/data/stages.json`. Every stage has a list `waves`; a group of enemies looks like
this:

```json
{
  "id": "w06",
  "enemy": "jumper",
  "formation": "line",
  "count": 2,
  "gap": 32,
  "trigger": "progress",
  "at": 1760,
  "anchor": "stage",
  "position": [2312, 320]
}
```

- `enemy` is who comes: `runner` (charges and jumps at you), `sniper` (stands, flashes and
  fires one aimed shot), `turret` (fires a fan; `fan` is how many bullets), `jumper` (hops) or
  `wall_cannon` (shut, and opens to fire). `count` is how many and `gap` the px between them.
- `position` is where they stand, in px from the top-left corner of the stage (`anchor` is
  always `stage`); `at` is how far the camera has come, in px, when they appear. A place just
  beyond the right edge of the screen at that moment looks best.
- `"blocking": true` holds the camera until the group is destroyed.
- `"enemy": "pickup"` with `"weapon": "spread"` (or `laser`, `flame`) is a weapon on its
  carrier.
- `fast` and `tough` make a group harder: a factor for the speed of its bullets and for its
  health.

A **boss** is the entry `boss` of a stage: its `kind` (`wall`, `walker` or `flyer`), `health`,
`points` and its `phases`. Each phase lasts until the boss's health has fallen to the fraction
`until` and has its `attacks`, an `interval` between them in seconds, a `count` of bullets and
their speed `fast`.

### More stages

A new stage is one row of **Added stages** in the options (`starter_map.added_stages` in
`rpggen/generator_config.json`: `[{ "name": "Canyon" }]`) and another generation. The stages
you have stay as they are, and the new one follows the last, a little harder. rpggen puts it
into `generated/data/stages.json`; the game plays every stage of that list that your own list
does not have. To change the new stage, copy its entry into `game/data/stages.json`.

Switching **Jump** off for a game whose stages were planned for jumping keeps those stages (a
plan is never made again); the report then says where the arm has nothing to hold on to
(VAL-030).
