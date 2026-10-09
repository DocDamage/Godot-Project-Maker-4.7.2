
## 22. Rooms, abilities and enemies (metroidvania)

The game is seen from the side. You run and jump through rooms that are joined into one world;
some ways are closed until you have found the ability that opens them.

| Action | Keyboard | Gamepad |
|--------|----------|---------|
| Run | A / D, Left / Right | D-pad, left stick |
| Jump | Space, Z | A (cross) |
| Drop through a platform | S or Down, then jump | D-pad down, then A |
| Climb a ladder | W / S, Up / Down | D-pad, left stick |
| Attack | J, X, left mouse button | X (square) |
| Dash (once you have it) | Shift, C | right stick button |
| Talk, read, use | E, Up | Y (triangle) |

(The bindings are in the Project Settings under **Input Map**. Space jumps, so it does not
interact as in the other kinds of game.)

- A **jump** is as high as you hold the button: let go early for a short hop. You can still jump
  for a moment after walking off an edge, and a press just before landing is remembered.
- **Platforms** drawn as planks are one-way: jump up through them, stand on them, and press down
  and jump to drop through. **Ladders** are climbed with up and down; jump to let go.
- **Spikes** cost 1 hit point and put you back on the last safe ground you stood on.
- Being hit gives a moment of invulnerability and a push back. At 0 HP you return to the last
  save station you used, with full health and with everything you had.

### The rooms

Every room is a scene of its own in `game/maps/rooms/` (`room_01.tscn`, …). A room has:

- the layers `Background` (the parallax pictures), `Ground`, `Platforms`, `Hazards`,
  `Decoration` and `Foreground`. Paint on them with the TileMap editor: tiles of the ground set
  are solid, planks are one-way (collision value `ONE_WAY`), ladders are `LADDER`;
- `Entities`: the player (in the first room), signs, the save station, pickups, chests, enemies
  and gates;
- `Triggers`: one **exit** on every edge that leads on. An exit has a **Target Room** (the scene
  of the next room) and a **Target Exit** (the name of the exit you arrive at there);
- `SpawnPoints`: a marker per exit with the same name, where you appear when you come in;
- `Camera`: the room's camera. It follows the player and stops at the room's edges.

Walking through an exit changes the room at once: you keep your speed, and the camera slides
over.

The plan of the world (which room lies where, and what is in it) is stored in
`rpggen/world_plan.json`. A room that exists is never built again, so what you change in a room
is kept when you regenerate.

### Adding a room

**In the wizard:** open the project, go to **Options → Starter world → Added rooms**, add a row
with a name and the room it lies beside, and generate again. The new room is built, and the room
beside it gets the exit to it.

**By hand:**

1. Duplicate a room scene in `game/maps/rooms/` and give the root a new **Map Id**.
2. In the new room, set each exit's **Target Room** and **Target Exit**, and delete the exits
   (and their spawn points) you do not need.
3. In the neighbouring room, add an exit that leads to the new room: duplicate one of its exits
   and its spawn point, move both to the free edge, name them alike, and set the target.
4. Run **Project → Tools → Validate project** (or the dock's validator): an exit that leads
   nowhere is reported (VAL-028) and can be fixed with one click.

### Abilities

| Ability | Id | What it does |
|---------|----|--------------|
| Double jump | `double_jump` | A second jump in the air |
| Dash | `dash` | A fast dash that crosses wide gaps |
| Wall jump | `wall_jump` | A jump off a wall you slide down |
| High jump | `high_jump` | Every jump goes higher |
| Break blocks | `break_blocks` | Your attack breaks cracked blocks |

An ability is found as a pickup (`generated/scenes/metroidvania/ability_<id>.tscn`) or given by
the guardian when it is defeated. It is part of the saved game. To give one from your own code:
`GameState.grant(&"dash")`; to ask: `GameState.has_ability(&"dash")`.

The picture of a pickup is the pack's item tagged `ability` whose name contains the ability's
name; without one a drawn orb is used. The names and descriptions are in `game/i18n/strings.tsv`
(`MV_ABILITY_<ID>_NAME`, `_DESC`, `_HINT`).

### Gates

The world closes ways in two manners:

- **By its shape.** A ledge too high for one jump needs the double jump, a gap too wide needs the
  dash, a narrow shaft needs the wall jump, a wall of cracked blocks needs break blocks. Nothing
  has to be set: the room is simply built that way.
- **By a gate.** A gate scene (as in "Keys, switches and gates" above) has **Required Ability**:
  it opens for a player who has it, and says what is missing to one who has not. In conditions
  (dialogue choices, gates' **Open When**) the same is written `ability:dash`.

The exits of the guardian's room are closed by gates until the guardian is defeated.

### Enemies

Enemies fight in the rooms, in real time. How an enemy behaves follows from its picture's tags
and name:

- **patrol** (the default): walks back and forth on its platform and turns at edges and walls;
- **flyer** (`fly`, `bat`, `bird`, `ghost`, …): flies, and comes for you when you are near;
- **shooter** (`shoot`, `turret`, `archer`, `mage`, …): stands still and shoots when it sees you.

Touching an enemy hurts. The data of every kind is in `game/data/enemies/` (hit points, attack,
rewards); its scene is in `generated/scenes/enemies/`. To place one, drag its scene under
`Entities` of a room and give it its own **Entity Id** (for example `room_03_enemy_004`).

The **guardian** (`generated/scenes/enemies/guardian.tscn`, the pack's art with the role *Boss*)
is a larger enemy with more phases the weaker it gets. Defeating it gives the first ability and
opens its room.

Defeated enemies come back when you rest at a save station; the guardian does not.

### Save stations and the map

- You save **only at a save station** (the bench in the first room): interact with it to rest
  (full health) and to choose a slot. The pause menu's Save is off. The game also saves by
  itself into the autosave slot on every room change.
- The scene is `generated/scenes/metroidvania/save_station.tscn`; drag it into any room to have
  another one. Its picture is the pack's sprite tagged `save_point`.
- The **minimap** shows the rooms you have been in as boxes, with a mark for a save station and
  for an ability that still lies there. The pause menu's **Map** shows the whole world you have
  seen so far.

### Animations

The player uses `idle`, `run`, `jump`, `fall`, and when the art has them `attack`, `dash`,
`climb` and `hurt`. A character without a `jump` or `fall` animation shows its idle frame in the
air; add the animations on the wizard's Audit page (the report lists this as ASSET-030).
