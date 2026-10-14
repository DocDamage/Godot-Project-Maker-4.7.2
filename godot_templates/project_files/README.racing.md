## 22. Tracks, rivals and the championship (racing)

The game is a championship: a race on each track, one after the other. Your car is seen from
above (or at an angle in an isometric project: see *A race seen at an angle* below); you race
the rivals for a number of laps, and your place in each race is worth points. There is no
village, no inventory and no party, so the sections above about maps, doors, shops and quests
do not apply to it.

| Action | Keyboard | Gamepad |
|--------|----------|---------|
| Accelerate | Up, W | A (cross), right trigger |
| Brake, then reverse | Down, S | B (circle), left trigger |
| Steer | Left and Right, A and D | D-pad, left stick |
| Boost | Shift, Space | X (square) |
| Use the weapon | X, K | Y (triangle) |
| Pause | Escape, Tab | Start |

(The bindings are in the Project Settings under **Input Map**. With **Steering: absolute** in
the options the stick is the way the car points, and the four directions steer.)

- A race begins with a **countdown**; nobody can move until it is over.
- A **lap** counts at the start line, and only when you have passed every checkpoint of the
  track in its order. Cutting across the grass does not count.
- The road is fastest. **Dirt** and **grass** slow the car and let it slide, **oil** takes the
  grip away, an **arrow** on the road is a boost for free.
- On the road lie **pickups**: a boost, a missile (fires ahead and spins the car it hits), a
  bomb (drops behind you), a shield (takes one hit). They come back after a few seconds.
- Each track has one **part**: speed, tyres or acceleration. A part stays on your car for the
  rest of the championship, up to three of each.
- The race is over when **you** have driven its laps. Rivals still on their way are placed by
  how far they got.

### The championship

After each race a screen shows who came in where, in what time and for how many points, the
part you won, and the table of the championship.

| Place | 1 | 2 | 3 | 4 | 5 | 6 |
|-------|---|---|---|---|---|---|
| Points | 10 | 6 | 4 | 3 | 2 | 1 |

Of two drivers with the same points, the one who was better in the last race is ahead. After
the last race the screen names the champion, and the credits follow. Your place also pays into
the **score** of the run, which is what the **High scores** of the title screen keep.

With **Elimination** in the options (`starter_map.elimination` in
`rpggen/generator_config.json`) a player who comes in last twice is out. The game then asks:
*Continue* drives that race again as if it had not been driven, *Quit* ends the championship.

The game **saves by itself** when a race begins, with the table and your parts; *Continue* on
the title screen starts that race again.

### The screen

In the top-left corner: the track, the lap, your place, the speed, your boosts, the weapon you
carry, and your points once a race has been driven. In the bottom-right corner: a map of the
whole track with a dot for every car (yours is the red one); the **Minimap** setting turns it
off. In the middle of the screen: the countdown, *Go!*, *Wrong way!* when you drive against
the track, and your place at the finish.

### A race seen at an angle

If the game was generated with the **isometric** projection, the tracks are painted on the
diamonds of your isometric pack and everything is seen at an angle, as in RC Pro-Am. The game
is the same race:

- The cars drive on the flat plan of the track, exactly as in a race seen from above; only
  their pictures are put where that is on the screen. So the numbers in
  `game/data/stages.json` (`start`, `checkpoints`, `waypoints`, `pickups`) are **places of
  the plan**, in px with x to the east and y to the south, not places of the screen.
- East in the plan runs down and to the right of the screen, south down and to the left. With
  **Steering: absolute** the stick is a direction of the screen: hold it down and the car
  ends up driving down the screen.
- A car drawn for this view has four or eight pictures (north is up on the screen) and turns
  in steps of 90 or 45 degrees; it still steers smoothly underneath. A car drawn from straight above is
  used too and looks flat.
- The map in the corner stays the plan from above, so a turn to the right on the map is a
  turn to the right for the car.
- In the scene of a track, the node **View** says how the plan is seen (the diamond, and how
  many px of the plan one diamond is wide). **Barriers**, **Surfaces**, the cars and the
  **Pickups** are where the plan has them, which is not where you see them in the editor;
  **Ground**, **Road**, **Marks**, **Walls** and **Scenery** are what is seen. Of these only
  **Ground** is in every track: **Road**, **Marks**, **Walls** and **Scenery** are there only
  when the track has something for them (a track without scenery has no **Scenery** node).
- When your pack has road pieces that name their sides (`roadNS`, `roadES`, …), the road is
  laid from them, one piece for each cell of the loop, and the corners of the track are its
  corner pieces. The car still drives the square corner of the plan, so at the outside of a
  round corner it can be seen on the verge. Without such pieces the road is drawn.

### Where things are

| What | Where |
|------|-------|
| The tracks of the championship | `game/data/stages.json` (yours) |
| The same list as rpggen planned it | `generated/data/stages.json` (rewritten on every build) |
| The plan the tracks come from | `rpggen/world_plan.json`, the section `stages` |
| The scene of each track | `generated/scenes/stages/stage_01.tscn`, … |
| Your car, the rivals, the pickup | `generated/scenes/racing/` (`car.tscn`, `rival_1.tscn`, …, `pickup.tscn`) |
| A picture of all tracks | `rpggen/results/starter_map.png` |

Everything under `generated/` is made again when you regenerate. `game/data/stages.json` is
written once and then left alone: change it freely.

### Changing a race

Open `game/data/stages.json`. Every track has these entries, among others:

- `title` is the name the HUD and the results show.
- `laps` is how many laps the race has.
- `checkpoints` are the lines a car has to cross, in their order: a `position` in px, the
  `heading` the track has there (in radians, 0 is to the right) and a `width`.
- `waypoints` are what the rivals drive along: a `position` and the `speed` (in tiles a second)
  they slow down to there. A lower speed in a corner makes every rival more careful in it.
- `start` is where the grid is (`position`, `heading`) and where the start line is (`line`).

The road itself, the barriers and what lies on the road are painted into the scene of the
track; they are not read from this file.

How good the rivals are is in their scenes: open `generated/scenes/racing/rival_1.tscn`, pick
the node **Input** and change **Skill** (0 to 1). The scene is made again when you regenerate,
so the change has to be made again then. How many rivals there are (0 to 5) and whether those far ahead of you ease off (**Rubber band**) are
options (`starter_map.rivals`, `starter_map.rubber_band`).

### More tracks

A new track is one row of **Added tracks** in the options (`starter_map.added_tracks` in
`rpggen/generator_config.json`: `[{ "name": "Harbour Ring" }]`) and another generation. The
tracks you have stay as they are, and the new one follows the last, a little longer. rpggen
puts it into `generated/data/stages.json`; the game drives every track of that list that your
own list does not have. To change the new track, copy its entry into `game/data/stages.json`.
