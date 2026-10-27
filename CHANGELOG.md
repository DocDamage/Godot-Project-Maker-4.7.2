# Changelog

All notable changes to the rpggen application. The generated game's runtime has its own
changelog in `godot_templates/addons/rpg_runtime/CHANGELOG.md`.

## 1.5.0 (in work)

A seventh kind of game and a second way of seeing four of them. Nothing changes for a project
of the six older kinds: a 1.0 to 1.4 project regenerates without a prompt, and a project that
does not ask for the isometric view is built as it was.

* **A farm and life sim**, the seventh kind of game: a farmer with tools, a hotbar and energy;
  soil that is tilled and watered and crops that grow by the night and the season; a farm of
  its own with a house, a plot, a pond or a well, a shipping bin and, if you want them, a coop
  and a barn; a village with a shop that keeps hours and people who keep schedules and can be
  befriended; animals, fishing, foraging, weather and seasons. The game reads
  `game/data/crops.json`, `people.json`, `animals.json` and `forage.json`, each written once
  and then yours.
* **Maps added to a farm are built**: every row of *Added maps* is a map of its own beside
  the farm, a **forest** (thick with trees, a clearing, things to clear and to forage) or a
  **beach** (sand, the sea along one side to fish in, shells and seaweed of its own), chosen
  in the row or by the words of its name. Each is planned and built once; a row added to a
  farm that exists builds one more map and touches neither the farm nor the maps before it.
  The way there is a marked patch of ground at the edge of the farm. A farm with a beach sells
  the rod even when it has a well.
* **The cave: combat on a farm.** The feature *Combat* is shown for a farm and, switched on,
  gives it a **cave** among its added maps: rock with chambers and tunnels, the action RPG's
  enemies (the packs' `ENEMY` pictures, else a drawn slime), and ore, crystals and mushrooms
  to find and sell. The shop sells a sword, swung with *Use*; the HUD shows the farmer's health;
  a defeated enemy leaves a thing of the cave and is back the next morning. Being defeated is
  passing out: the day ends and the farmer wakes at the bed as after 2:00. A cave row needs
  *Combat*; *Combat* without a cave row adds one called *Cave*. With *Combat* off a farm is
  what it was: no cave, no sword, nothing to fight, and the action RPG's runtime is not
  installed.
* **Festivals and birthdays** on a farm (the option *Festivals and birthdays*, on): a festival
  in every season, always a Friday, with the shop closed, everybody on the village square and
  one small thing to do for a prize: an egg hunt in spring, a fishing count in summer (a
  second contest on a farm that cannot fish), a produce contest on what the shipping bin sold
  that season in autumn, a feast in winter. Everybody has a birthday, on which the first gift
  counts five times and is none of the week's two. A calendar hangs on the wall of the
  farmhouse and is in the pause menu; the day before a festival the sign by the house and the
  people say so. The festivals are data (`game/data/events.json`, written once and then
  yours). Switched on for a farm that exists, no map and none of your files is written again.
* **Marriage** on a farm (the option *People to court*, 2; 0 turns it off): that many people
  of the village, chosen once, can be courted. They stop at eight hearts until given a
  bouquet from the shop; at ten a pendant is a yes, and three days later the wedding is a day
  on the square. The spouse lives in the farmhouse (planned now with a bed for two), keeps a
  day of their own, says other things, and on some mornings waters part of the plot, feeds
  the animals or leaves something on the table. Neglected friendship falls slowly; nothing
  worse happens. Switched on for a farm that exists, its people are chosen and no map and none
  of your files is written again (the old farmhouse keeps its one bed).
* **An isometric view** for the turn-based game, the action RPG, the farm and the racing game,
  from packs that ship one picture a tile: the diamond a pack stands on is read from its own
  text file or measured, a tile turned four ways is one tile, pieces whose names say which
  sides join are laid along roads, shores and walls, and cars drawn in eight headings are
  driven. The same planned map is painted as diamonds; a top-down project is what it was. The
  view needs isometric ground tiles (none is drawn), and a project keeps the view it was first
  generated with.
* **Isometric Tiled maps are imported** into an isometric project (the Tiled sample of
  Kenney's *Isometric Miniature* packs is one): each tile is the picture its Tiled tile shows,
  read as the pack's pictures are wherever it lies and put into the project's tile set for that
  map alone; the first layer is the ground and the others stand among the people, a layer
  drawn higher in Tiled is drawn higher; a picture of a wall blocks its diamond; spawns, doors
  and signs stand on the middle of their diamonds. A map of squares is not imported into an
  isometric project, nor an isometric map into one seen from above: the run says so
  (TILE-013). Staggered and hexagonal maps are still not read, and TILE-009 now names the
  shape. A map of squares is imported as it was.
* **Every pack makes a farm.** What a pack lacks is drawn in its tile size (crops in five
  stages, tilled and watered soil, the tools, a seed bag, a hen and an egg, a shipping bin, a
  bed, rain, a rod, fish and things to forage) and reported as a note (ASSET-031). For the
  isometric view a hero, a villager and an enemy are drawn when no pack of the project has
  them.
* **Detection for farming packs**: growth strips (a crop's stages in a row), the roles *Crop*,
  *Farm animal* and *Tool*, seasonal variants of a sheet as one card, fence sheets and drawn
  2 x 2 corner sheets as terrains, and a farmer's tool strips kept apart from the villagers.
  Tilled and watered soil are a field's ground and never the ground a map is laid with while
  the packs have another.
* **Real farming packs** (Kenney's *Tiny Farm*, EmanuelleDev's *Farm RPG*, LimeZu's *Modern
  Farm*): pictures that are **the same tiles in several forms** (a sheet with spacing, a packed
  sheet, single files; strips and the sheet of the season that repeats them) are found by
  their content, and one form is used; a pack **in several sizes** is used in one (the other
  packs' size, else the smallest; the Audit page's *Packs* tab chooses another), and no tile
  set is made in a size a pack does not draw; **crops by their pictures** (cells that grow, in
  a folder of crops or named after a crop, or a run of growing cells in a tile
  sheet), named after their produce, with food icons as items; **farm animals** in sheets of
  rows with their animations; **characters drawn in pieces** (a body, eyes, hair, clothes and
  accessories, a file an action or a sheet a piece) as one character whose parts are its
  choices, and a character drawn a file an action as one character; a GIF beside the sheet it
  shows set aside. Licences are read from documentation files too, a credit the licence asks
  for is written into the generated README, and a `.rar` is opened with Windows' own `tar`
  when 7-Zip is not installed (T17.29).
* **Packs of other shapes** (Screaming Brain's isometric packs, *Lords Of Pain*, SakPix's
  stage packs and characters, CuteSCKR's tile sets): **isometric sheets named by their cell**
  (`Floor_Dry_01-256x128.png`, wall faces `-SE-128x192`) are cut cell by cell, the background
  colour made see-through, wall faces put together into pieces for the four sides of a diamond
  with their doors and windows, a *Small* and a *Large* copy one pack in two sizes; a **large
  ground picture** of an isometric pack that names no diamond is cut on one at its characters'
  scale; **characters in a folder of facings** (`rotations/east.png`; sixteen facings a folder
  each, of which the eight the game turns by are used: ADAPT-008) are one character with their
  animations; **object sheets** are cut into their things, each an asset with an id from its
  place and a role from the sheet's name; **mixed tile sheets** are sorted cell by cell into
  ground, objects and decorations; and on the Audit page's *Packs* tab a pack with no licence
  file can be given its **licence and a credit line by hand**, kept in the pack's profile and
  written into the README as your own statement (ASSET-036); a pack can be **marked as
  AI-generated art** there too, and the README of a game that uses it has a section
  *AI-generated content* naming it for the store page's declaration, with a word on cleaning
  the art up in Aseprite. New notes TILE-014, ADAPT-008,
  ASSET-036. The analysis of such sheets runs in parallel and stops on a cancel (T17.30).
* **Corners and roofs of isometric houses** (after T17.30): Screaming Brain's thick walls
  (each face with the end of the wall beside it), its corner posts, and the walls and roofs of
  its *Town Pack* (a sheet whose corner is painted, a sheet a few pixels wider than its cells)
  are read; a roof piece of an isometric pack is read by its shape and turn (a slope, the
  quarter of a hipped roof, a gable over one cell, a pyramid, an inner corner) and a post by
  the corner it stands on. The edge of a map laid from wall segments gets a post where two of
  its sides meet, and a house of pieces a post at each corner and one roof: on *Miniature
  Farm* slopes up to a ridge with hips at its ends; on *Medieval Town*, whose slopes and hips
  cover half a cell, a gable along every row; a roof tile a cell only where a pack has nothing
  better. Screaming Brain's paths and roads are left to T17.31 (terrains).
* **Autotiling: terrains read from real sheets and maps painted with them** (T17.31). Terrain
  blocks inside larger sheets are found by matching the edges of their cells: Godot's 47-tile
  template and the blob in the masks' order anywhere in a sheet, 16-tile corner and edge sets,
  a block of 3 x 3 with its inner corners wherever they lie near it (or without them), RPG
  Maker's block of 2 x 3 (composed into its 47 tiles), beds of soil one cell wide; over
  transparency or over another ground; plain cells that tile with a terrain's middle are its
  variants, laid less often, and plain tiles of one tone that tile with each other vary a
  ground. On diamonds, pieces whose surface goes on across some sides of their diamond are a
  terrain of the isometric tile set, read from the pictures and from the names that give
  their joins (`roadES`, `waterE`): Kenney's road, river and shore pieces and Screaming Brain's
  *Pathways* and *Roads*. Maps are painted with Godot's terrains: a ground that varies,
  patches of another ground with soft edges, roads and paths with their kerbs, ponds and a
  beach's sea with their shores, a farm's field edged where it meets the grass, whose tilled
  and watered soil join the soil round them as the farmer hoes, and an isometric track. The
  variants are chosen by the project's seed (Godot's own choice changes from run to run). A
  map that exists is never painted again and the run says so (TILE-015, new); a project
  without terrains is built as it was.
* **Real side-view packs** (T17.32), for the metroidvania and the run and gun. A tile sheet
  whose tiles nothing names is read from its pictures: the ground as a side-view terrain (its
  surface on top, its ends, its inside, the faces under it), planks to jump through, ladders,
  spikes, water and coins; the tiles left in doubt are counted (TILE-016, new). Ground pieces
  named by their place (`grassLeft`, `grassMid`, `grassCenter`, `grassHalf_left`,
  `grassCliff_right`, `grassHill_left`) are put together into a sheet a surface. Rooms and
  stages are painted with that terrain (the terrain shape `side`). A character drawn as a
  folder of frames an action (`Sprites/Idle/frame1.png`), as files named by actions
  (`alienBeige_walk1.png`) or as a sheet whose name gives its frame size (`Character
  160x160.png`) is one character; its strips, previews and Aseprite files are set aside. A
  character sheet beside the tiles is cut into characters. Background layers in a folder are
  one parallax set, ordered far to near, and a room uses the set nearest its ground. Props
  are no characters; a sign, a door or a ledge's decoration is no ground; a pack has one tile
  size; a licence file one folder above a pack added on its own is found; a pack that calls
  itself a platformer or a beat 'em up is seen from the side. Done on *Gothicvania*, *Warped*,
  Kenney's *Pixel Platformer* and *Platformer Pack Remastered*.
* **Assets only: build your own levels** (T17.33). A new kind of project, `assets`
  (`rpggen generate --pack ... --archetype assets`, and `--view top` or `side`, else as the
  packs are drawn): the packs' tile sets, the scenes of the RPG Project Tools dock and the
  catalog, with the runtime the scenes need, and no game (no maps, menus, main scene, smoke
  run or export check). Its README says how to make a level with the Terrain tool and the dock.
* **Terrains paint without holes** (T17.33). Godot's Terrain tool left a cell empty where no
  tile of a terrain fitted the cells around it, and few packs draw every piece: for each way a
  terrain meets others that its pack draws no piece for, the nearest piece it draws is added as
  an alternative tile. A plain ground matches by its sides, so a patch of it keeps its border.
  It is done for a source the build makes: a project made before 1.5.0 keeps the TileSets its
  version built when it is regenerated (the test of a project made by 1.1 found the ground of
  one gaining 46 alternatives). The same test found a TileSet's patterns saved again with new
  ids on each rebuild: patterns that come out the same are kept.
  Terrain names say their surface and their sheet (`dirt · tileset grass spring 2`).
* **The things of a sheet of tiles are in the dock** (T17.33): the trees, rocks, crops, sacks
  and tools beside a sheet's ground (*Tiny Farm*'s one sheet gave none), joined where their art
  goes on over the line between cells; a font's glyphs, a background's shapes and tiles of a
  kind (a ladder) are not. In an assets-only project every thing cut from a sheet is placed,
  with a collision at its foot.
* **Reading** (T17.33): a ladder tiles by its rails; a plank's ends with posts under them are
  the plank; a side-view ground's middle is its plainest fill, its other fills of the same tone
  variants laid now and then, one of another tone (a cave's dark wall) only where nothing else
  fits; a plain ground's middle is its plainest seamless tile; an icon is an item, never an
  animal; a person drawn again much larger beside its sprite is its portrait; Kenney's trimmed
  copies of a player (`Variable sizes`) are set aside; a fence in a folder of props stays a
  prop; a farmer's tool strip stays an animation of the farmer; strips that name their frames
  are each read as they were.
* **Gridwright's isometric kits, and stacking.** All thirteen kits (*Tiles*, *City*,
  *Interiors*, *Dungeon & Caves*, *Graveyard & Crypt*, *Castle & Siege*, *Wasteland*,
  *Characters*, *Monsters*, *Animals*, *Army* and the two creators) are read by the JSON they
  ship. Nothing they draw is set aside but copies (other sizes, sheets of the single pictures,
  single frames of sheets):
  * **Stacking.** Blocks, half blocks, ramps and stairs, the storeys of a building, its roof,
    things for a roof, awnings and signs on a storey's front, lanterns and pictures on a wall,
    and pieces laid over other tiles are tiles that say where they go in a stack and how high
    they lift what stands on them. The dock's *World tools* add **height layers**: tile layers
    drawn higher that sort with the people as their ground does, at the height the dock
    suggests. A thing placed on a cell with a stack stands on its top.
  * **What moves:** tiles that move play (water, lava, foam, waterfalls, mist, flames), and
    things that move play their animation in the dock's scenes (a fountain, a campfire, a
    police car's lights). A door, a gate or a portcullis is a tile in each of its poses, and a
    catapult plays its swing once.
  * **Shadows:** things and characters whose pack draws a shadow have it under them.
  * **Characters, effects and creators:** each character's 8 directions and animations are
    read from its own JSON. Its role is its side, an animal's group (farm animals; pets and
    deer as moving decorations; bears, wolves and boars as enemies), or whether an army's unit
    fights. Arrows, bolts and impacts are projectiles and effects that play. A creator's layers
    are a layered character whose parts you choose, standing on the pack's feet point.
  * **Names:** a zip whose long name an id cuts short and that holds one folder is named by
    that folder (*Gridwright Isometric Tiles*, not thirteen times
    *isometric_map_builder_pixel_art_godot_ti*).
  * **Copies out of Godot's import:** a folder of a pack that holds only copies (other sizes,
    single frames of sheets, sheets of single pictures) gets a `.gdignore`, so Godot does not
    import it. The files stay in the project, and deleting the marker brings a folder back. The
    nine character and tile kits hold about ninety thousand such pictures, and importing them
    took over ten minutes. A picture set aside (a pack's preview read as a sheet of tiles) is no
    longer a source of a tile set in a new project (one was cut into 30,000 tiles), and the
    things cut from a pack's preview are no objects (nine kits' previews gave 19,600).
  * **Still missing:** characters do not climb a stack in the game (it is drawn, not walked).
    The vehicles are placed, not driven: they face the diagonals, and a race turns by up,
    right, down and left.
* **Quests, shops, the bag, skill trees and achievements** in every game made with the runtime
  (the runtime's CHANGELOG has the details): quests that wait for others, start by themselves,
  fail and are turned in, with live counts and a tracker under the minimap; shops whose stock
  runs out and refills, with their own gold, rolled wares and **Buy back**; rewards that wait
  for room in a full bag instead of being lost; gear that wears and breaks, and sets of gear;
  skill trees (*Pause → Skills*) and achievements (*Pause → Achievements*).
  * **The option *Skills and achievements*** (on for a new turn-based game, action RPG,
    metroidvania or farm; not offered for the arcade kinds) seeds a starter skill tree (the
    adventurer's: vigor, strength and guard, then healing or toughness, fury and swift), the
    achievements the game has the parts for (the errand, ten enemies, level 5, gold saved, a
    secret chest) and the traveler's set for a starter weapon and armour worn together. A
    project made before 1.5.0 has no such key in its config and regenerates without them.
  * **The editor dock** has three more tabs, **Skills**, **Achievements** and **Item sets**:
    forms with undo, a picture of the tree's grid, a test of an achievement against a pretend
    state, the items of a set (with their durability), and JSON export and import.
  * **The validator** reports a quest, a skill tree, an achievement or an item set that does
    not add up (VAL-034).
* **Detection for isometric packs**: a pack of single tiles with its diamond and how far each
  picture rises above it, turns by number or by compass letter as one tile (never as frames of
  an animation), sides in a name (`pathES`, `waterNW`), a folder `Isometric` beside `Angle`, a
  zip inside the pack's folder, a sprite atlas beside the same loose pictures.
* **The wizard**: seven cards on the Archetype page (rows of four in a wide window, rows of
  three below that, one column in a narrow one) with the **Farm** card; a line that says a
  pack looks like a farming pack or is isometric, with its diamond; on the Options page,
  when a pack has isometric pictures, a **View** choice (*From above*, *Isometric*) in the
  box of each kind that has the view and, for the isometric view of a kind whose player
  walks, a **Pad** choice (a race has its *Steering*): chosen for the packs, refused with the
  reason when they have no isometric ground, and fixed once the project exists; the **Farm** box with
  the planned farm as a picture (on squares or on diamonds), the days of a season and the
  length of a day; the presets *Cosy* and *Short year*.
* **Two more samples** under *Choose a sample*, which lists seven: *Green acre* (a farm) and
  *Stone isle* (an isometric village, as a turn-based game).
* **The audit** says *Turns* for a tile turned several ways and *Seasons* for a sheet that
  comes once a season, where it says *Variants* for colours; *Edit grid…* on a picture of an
  isometric pack draws its diamond and lets you change it (a tile) or how many diamonds an
  object stands on. The pack card says *Looks like a farming pack* and *Isometric tiles,
  40 x 22*; the Mapping page says when a car drawn from above will look flat on an isometric
  track.
* **The command line** takes `--archetype farm` and `--projection isometric`, and a dry run
  says what would be planned (*a farm of 40 x 30 with a plot of 96 cells, a pond, 4 crops, 3
  people*).
* **New notes and errors**: ASSET-034 (a crop of one picture: its stages are drawn), TILE-010
  (an isometric pack whose diamond could not be read), TILE-011 (isometric and square ground
  in one project), TILE-012 (tiles on another diamond are left out), TILE-013 (an imported map
  of the other view is not built), VAL-031 (a farm that
  cannot be worked), SMOKE-013 (a step of the farm's own sequence), ASSET-035 (a picture among
  the crops whose cells do not grow), ARCH-010 (files of a rar whose names the system's `tar`
  cannot read).
* **Mended while the milestone was tested**: two generations of projects with one name, run at
  the same time, failed each other's save checks (each check run now saves into a folder of
  its own); a dark kerb along isometric paths and a footing under far walls; a pack read
  through its profile lost its diamond; a farm's planner did not see a pack's coop and barn
  when another building was chosen for the village; the rooms of a farm were floored with
  grass; the cells an isometric building left free of its planned footprint could be walked
  into; small diamonds were measured too coarsely; a farm whose villager stood where a
  check of the generation put its gate failed that check; and the farm's sound slots (hoe,
  watering, plant, harvest, animal, rooster) were offered on the Mapping page and never played.
* **Mended after the milestone's documentation was written**:
  * **A dialogue's choices are on the screen.** The dialogue box grew downward when a line had
    choices, so the second choice was cut off at the bottom of the window. This was so in
    every kind of game since 1.0; the box now grows upward. The generated scenes are what they
    were (the fix is in the runtime's script).
  * A monster or a boss in a folder that only says *characters* (`characters/slime.png`) is
    read as an enemy, not as a villager: its own name counts for more than the folder's.
  * The first paragraph of a generated README says what the project is for every kind (a race
    was "a **racing** RPG starter" with "a talking NPC, a chest"). The README of a turn-based
    game and of an action RPG is unchanged; a metroidvania's no longer says *a small map*.
  * On a farm, a crop, an animal, a fish or a thing to forage can be removed for good with
    `{ "id": "berry", "removed": true }` in `game/data/crops.json`, `animals.json` or
    `forage.json` (a deleted entry comes back from rpggen's own list, as before).
  * The axe is heard: it plays the **Hoe** sound.
  * The Options page shows no **View** row for packs that have nothing isometric (it was
    shown, disabled, for every turn-based, action, farm and racing project), says in its own
    words why packs with isometric pictures and no isometric ground stay *From above*, and
    offers no **Pad** for a race, whose config no longer carries `iso_controls`.
  * A track's README says that the nodes `Road`, `Marks`, `Walls` and `Scenery` are there only
    when the track has something for them.
  * **A farm's ground is plain ground.** Every map of a farm was laid with the first tile of its
    ground sheet, which on real farming packs is the corner of a bed of soil (*Tiny Farm*) or
    of a blob of grass (*Farm RPG*). The farm, its village and its added maps are now laid with
    the most even tile of grass or earth of the sheet that repeats without a seam, measured
    from the pictures (`farm.ground` in the plan file); a sheet without one gets a plain ground
    drawn in its own green (*Tiny Farm*). One tile everywhere: varying the ground and joining
    it to soil, water and paths is painting with terrains, a step of its own. The village of a
    farm no longer has patches of the sheet's next tiles (its edges and corners).
  * **A pond of water, not of fish.** A picture in a folder of icons of a farming pack is an
    item and never water or ground (*Farm RPG*'s sheet of fish icons filled the pond), and a
    single picture of one tile named or tagged water is a tile of water (*Farm RPG*'s
    `Water tile.png`).
  * **The cave reads as a cave.** Its rock is the packs' own where they have a picture of it
    (a cell of a picture named rock, cave, cliff or stone, or of a cliff or wall tile sheet,
    that is opaque and repeats; on diamonds a tile so named; else the packs' boulders), drawn
    shapes only when they have none; its light is darker than a room's; and an enemy drawn
    much smaller than the farmer (the kit's slime: half the farmer's height) is scaled to
    seven tenths of the farmer's height.
  * **Crops of a mixed tile sheet.** In a farming pack, a row of growth stages on a mixed sheet
    (a plant on its mound of soil in each cell, each covering more of its cell than the one
    before) is a crop: CuteSCKR's *Farm Tileset* grows ten crops of its own.

**Known limits.** Nobody has played either the farm or an isometric game by hand yet: what is
known is what their tests and check runs assert. A farm's ground is one tile, and its soil,
water and paths meet it with hard edges (no map is painted with terrains yet), and the door to an
added map is a mark on the ground beside the farm's edge, which a tree before it can hide. An imported isometric map has no height: the stairs of a sample are pictures walked across, and a second floor is only drawn higher. A
room of an isometric project has walls only when the packs have isometric wall pieces. An
isometric race is shown from above on the Options page. The French file has the new texts
unfinished.

## 1.4.0 (in work)

Three more kinds of game, and what real packs needed to be read. Nothing changes for a project
of the three older kinds: a 1.0 to 1.3 project regenerates without a prompt (but see the two
fixes in the runtime's changelog: its minimap and two of its screens are now where they were
meant to be).

* **Shoot 'em up.** A ship over a scrolling background, vertical or horizontal: waves in
  formations, four kinds of enemy, power-ups and weapons in three levels, bombs, a boss at the
  end of every stage. The stages are planned from the seed and shown as a wave chart on the
  Options page.
* **Run and gun.** A soldier seen from the side who runs, jumps, aims in eight directions and
  throws grenades; four weapons on carriers, five kinds of enemy, three kinds of boss, stages
  planned in chunks that are checked to be passable. With the **grapple arm** the soldier
  swings and hoists; the preset *Bionic* switches jumping off and plans every stage for the arm.
* **Racing.** A car seen from above against up to five rivals who drive on the same physics:
  tracks planned as closed loops with checkpoints, surfaces (road, dirt, grass, oil, boost
  arrows), pickups (boost, missile, bomb, shield, parts that stay), laps, a results screen and
  a championship table, a map of the track; relative or absolute steering.
* **The arcade framework** the three share: stages in order, lives, a score with a multiplier,
  a *Continue?* screen, the ten best runs on the title screen, a save between stages.
* **Every pack makes a game.** What a pack lacks for the kind is drawn in its tile size (a
  bullet, an explosion, a capsule, a ship, a car in sixteen headings, a road, a hook) and
  reported as a note (ASSET-031).
* **The wizard**: six cards on the Archetype page (two rows of three, or one column in a narrow
  window), a hint that names the kind a pack looks made for, each kind's options with a picture
  of its plan, the presets *Arcade classic*, *Bionic* and *Sunday drive*, and three more
  samples under *Choose a sample*: *Star lane*, *Jungle line* and *Dirt cup*.
* **Rotation sheets**: a picture of one object turned step by step (8 to 32 headings, as
  top-down car packs ship them) is recognized and used as a vehicle.
* **The command line** takes `--archetype shmup`, `run_and_gun` and `racing`, and a dry run
  says what would be planned.
* **What real packs needed.** Numbered frames without an action word are split into animations
  at blank frames (ADAPT-005) and can be named in *Animations…*; binary `.aseprite` files give
  the names and ranges of the animations; `_32x32_4frames` and `_9split` in a name are read;
  a pack that ships its art for several engines is read from Godot's folder and the copies are
  set aside; `__MACOSX`, previews, links and guide pictures are left out; names with number
  prefixes, ampersands, emoji and small typos are read; sheets named only by a number take
  their words from their folder; RPG Maker's sheet names are read wherever they lie; the list
  a sprite cutter left in a pack gives its sheets their objects (ADAPT-007); colour variants a
  pack ships as files are grouped; the 47-tile terrain sheet in the order packs ship it
  (Godot's 3x3 minimal template) is a terrain.
* **A bundle of packs.** An archive that holds many packs (a folder each, or a zip each) opens
  *Choose packs*: tick the ones to add, search them, and see what the choice comes to. Each
  becomes a pack of its own, only those are unpacked, and *Choose packs…* on the bundle's row
  changes the choice later. On the command line: `--pack <archive> --pack-folder <name>`.
* **Aseprite files without an export** are drawn from the file itself and their tags are the
  animations (layers, opacity, indexed colour; blend modes other than *normal* are drawn as
  normal and the asset is marked for review).
* **Colour variants a pack ships** are one card in the audit, with a *Variants* row to see and
  select them, and are offered together on the Mapping page.
* **The pack card** says what a pack looks like: a shooter pack, a racing pack, art for several
  engines. The grid editor shows a rotation sheet's views in a ring.
* **LPC characters**: the universal sheet is read whole (cast, thrust, shoot, and the
  generator's climb, idle, jump, sit, emote, run and the other rows, where they are drawn), and
  the LPC collection's files are read: a picture per animation, or a folder per animation with
  a picture per colour, are read as the parts of a character: its body, and the hair, clothes
  and weapons that are drawn over it. An LPC project made with an earlier version gets the
  added animations when it is regenerated.
* **LPC characters put together**: a pack with one body and one layer of each kind gets its
  character by itself; with *Compose LPC character…* on the Audit page you choose the layers
  of a body, see the result and name it. The character is one sheet with every animation of
  its body, and can be the player.
* **Four more roles** in the audit and on the Mapping page: *Vehicle*, *Explosion*,
  *Power-up* and *Hazard*. A car's rotation sheet is a vehicle; in a shooter or racing pack
  asteroids, oil and tyres are hazards and capsules and boosts are power-ups.

## 1.3.0

The look, the feel and the ease of use of the wizard. Nothing was taken away and nothing moved
out of reach: every control, menu entry and shortcut of 1.2 is there. The generated game is
unchanged (the runtime's changelog has no entry), and a project made with 1.0, 1.1 or 1.2
regenerates without a prompt.

* **A designed look, in both themes.** One set of colours, sizes and radii for the whole
  program; every button, field, list, tab, scroll bar and menu is drawn to it. Buttons say how
  much they matter (one main action per view, quiet ones beside it, red for what deletes),
  there are icons, groups are cards, and a keyboard user sees a clear focus ring. Pages fade in
  (not with *Reduce motion*).
* **The steps on the left** show what is done, what needs a look and what is not open yet, and
  shrink to their circles in a narrow window. Every page starts the same way: its name, what it
  is for, its own controls and help.
* **Welcome**: three cards of one height, *Choose a sample* on the sample card, how the wizard
  works while there are no recent projects, and the Godot that was found (or *Download*) in one
  line at the bottom.
* **Project**: a small drop zone that holds the Add buttons; hints inside the fields.
  **Audit**: one filter row with *Profile* at its end (it was three rows, and *Profile* was cut
  off in the default window), the review count in the header, a footer with the keys.
  **Mapping**: compact rows with icon buttons. **Options**: two columns in a wide window,
  *Reset to defaults* beside the presets. **Generate**: a checklist of plain-language steps and
  the percentage. **Results**: a banner, the counts as tiles.
* **Try the sample in two clicks**: the welcome card goes all the way to the Generate page and
  starts; *Back* returns to the options while nothing was written.
* **Failures that say what to do**: the Results page shows what Godot reported, with the file
  and line, the end of the failed step's log, and buttons that open the log, show the asset in
  the audit or open the failed folder.
* **A regeneration that changed nothing takes seconds**: when the packs, the audit, the options,
  rpggen and Godot are what they were and no file of the project was touched since the last
  run (a generated one, or one of your own under `game/`), the import, the build and the
  checks are not repeated (REGEN-011). `--full` on the command line, or *Run every
  check again on every regeneration* in the preview of changes, runs them all.
* The window's title names the project, the page and the progress.
* Fixed: colour codes of the terminal showed as `[0m` and the like in the Generate log.
* Fixed: a project that uses a placeholder for a missing role, or the generated side-view tiles
  of a metroidvania, got a *file is missing* warning (CAT-004) for it on every regeneration,
  and a second copy of the placeholder in its catalog each time.
* Fixed: `Alt+N` stopped working once the Next button read *Generate*.
* For contributors: pictures of every page are compared on each change
  (`python -m rpggen.dev update-ui-goldens`), and CONTRIBUTING has a *Look and feel* section.

## 1.2.0

A third kind of game: the **metroidvania**. A project made with 1.0 or 1.1 regenerates with 1.2
without a prompt: the config and save versions are the same, every new key is optional, maps and
everything under `game/` are never rewritten, and the TileSets of top-down projects are what
they were. The real-time combat scripts of the action RPG moved to a shared folder; the old
paths keep working until 2.0 (see the runtime's changelog).

* **Metroidvania** (the third card on the Archetype page): a side-view hero that runs, jumps
  with a variable height, drops through one-way platforms, climbs ladders and attacks; a world of
  joined **rooms** that change without a fade; **abilities** (double jump, dash, wall jump, high
  jump, break blocks) that open ledges, gaps, shafts and walls; a **guardian** that gives the
  first one; patrolling, flying and shooting enemies; **save stations**, a room map and a HUD of
  health pips and abilities; a hermit in the last room who ends the game.

* **Side-view detection**: platform, ladder, spike and breakable tiles, parallax background
  layers and left/right characters are recognised from folder and file words. A pack that looks
  side-view says so on its card and suggests the Metroidvania card; a top-down pack can still
  be used, with a note. New collision values for tiles: *One-way* and *Ladder*. A player without
  a jump or fall animation shows its idle frame in the air (ASSET-030, a note).

* **Starter world** (Options, for a metroidvania): rooms, room size, abilities, enemies and
  pickups, with a side-view picture of the plan. The plan is planned in advance so that every
  room can be reached and every ability is found before the way that needs it, stored in the
  project, and never planned again; *Added rooms* grows a world that exists, and the world
  repair gives the neighbour its exit. An exit that leads nowhere is VAL-028, as for doors.

* **A second sample**: *Try the sample* is a split button, *Top-down village* (as before) or
  *Side-view cave*, a small CC0 pack made for the metroidvania.

* What a pack lacks is drawn: plain one-way platforms, ladders, spikes and breakable blocks in
  the pack's tile size, an orb for an ability, a bench for the save station.

* Mapping: the roles of the archetype (Background, Decoration and Boss among them), and four
  more sound slots for it (Jump, Land, Dash, Ability).

* The Archetype page fits three cards in the minimum window: the flow of a card wraps, and the
  controls line is shown when the card is wide enough for it.

* `rpggen generate --archetype metroidvania`; a dry run describes the world ("6 rooms, 2
  abilities, a guardian"); the report's World section names the rooms.

* The integration tests run as one CI job per archetype.

* Fixed: the JSON result of a run that mended a metroidvania's exit did not fit its schema.

## 1.1.0

Polish for the wizard, seven improvements and three additions to the generated game. A project
made with 1.0 regenerates with 1.1 without a prompt: the config and save versions are the same,
every new key is optional, no generated script moved, and maps and everything under `game/` are
never rewritten. Music now loops (in 1.0 a track played once), and the dependency `soundfile`
(libsndfile) is new.

* Tiled map layers saved with **Zstandard** compression are imported (TILE-009 is now only for a
  compression rpggen does not know).

* The validator and the Dialogue tab check the **shop, quest and party member ids** a dialogue
  names (`open_shop:`, `quest_start:`, `quest_stage:`, `quest_complete:`, `join_party:`); a typo
  is marked on its line while you type.

* **Shops**: left / right on a row sets how many to buy or sell (the row shows the total), and
  the Sell tab has **Sell all**. A shop can list the item categories it buys.

* **Audit review mode** (View → Review mode, `F7`, or the button beside the progress line): one
  asset at a time with a large preview and the same panel and keys; `Esc` returns to the grid.

* **Audit: Group by folder** (on the filter bar, remembered): a header per folder with its counts
  and **Confirm all**, **Select all** and **Make rule…**; click a header to fold its folder.

* **Audit: live preview**: the picture shows an object's footprint and origin and the frames
  where an attack hits; a sprite with animations has a small transport (animation, Play, frame)
  that plays it in the preview, in the panel or large in review mode.

* **Audit: Select similar** (right-click, `Ctrl+Shift+S`): selects the assets that look like the
  selected one, so one bulk edit covers them. A file that repeats another one says so in its
  *Why* line.

* **Mapping**: *More…* opens a gallery of the candidates (thumbnails grouped by pack, best first,
  with search), and each row has **Show in audit**, which opens the Audit page on that asset;
  *Back* returns to the row.

* **Options**: three built-in presets (**Everything**, **Minimal**, **Just the tilesets**) head
  the preset list; *Navigation* needs *Combat* and the demo scene needs *Tilesets*, and a box
  whose requirement is off says what it needs.

* **Generate**: from the second run on, the running phase and the top line say about how long
  is left, from how long the last ten runs took on this computer (and `taking longer than
  usual` instead of counting below zero). The CLI prints the usual time after each phase line.

* **Welcome view**: recent projects are cards with the picture of the starter map, the kind of
  game, the date of the last generation and the packs. A pack that changed since gives the card
  a line and **Regenerate**; a folder that is gone offers *Remove from the list*.

* **A tour of the Audit page** the first time you open it: five short callouts (the cards, the
  queue, the detail panel, the keys, profiles). *Skip* or `Esc` closes it for good;
  *Help → Show the tour again* brings it back.

* **Display scaling**: thumbnails, previews and the archetype drawings are made for the screen's
  scaling, so pixel art stays sharp at 150 % and 200 %. **Screen readers** get a name for every
  card of the audit grid. **View → Reduce motion**. On Windows the taskbar button shows the
  progress of a generation (the dock icon on macOS counts the steps left).

* **One interior per house**: every house of the starter map leads to its own `interior_<n>`,
  as wide as the house, and leaving it returns to that house's door. A project from 1.0 gets
  the interiors its map is missing; its map is not changed (the project's README says how to
  point a house at its interior).

* **Followers in the action RPG**: `join_party:` works there too. Party members walk behind the
  player, and the first two help in a fight: they walk to an enemy within three tiles of the
  player and swing every 1.2 s with their own attack, stay within six tiles, and are only
  "down" for five seconds at 0 HP. The HUD shows their HP bars, and the demo villager offers
  the companion in both archetypes.

* **Custom sound slots**: **Add slot…** in Mapping → Sound makes a slot of your own
  (`sfx_<name>` or `music_<name>`), played by `play_sound:<slot>` in a dialogue, the
  `play_sound` step of a cutscene or `SceneRouter.audio.play`. `sfx_step_<surface>` is the
  footstep on ground tagged `surface:<name>` (read from folder and file names: grass, stone,
  wood, sand, water, snow), filled from files like `step_grass.wav`. A bad slot name in a
  config file is `CAT-006`.

* **Waveforms and loop points**: an audio card shows the waveform of the decoded file (WAV, OGG
  Vorbis, FLAC, MP3, through libsndfile) and the detail panel shows it large with a play head.
  Music gets a **Loop** row: start and end in milliseconds, draggable markers, **Guess** and
  **Whole track**. Music now loops in the game, between the chosen points (a WAV between both;
  OGG and MP3 play to their end and come back to the start point). New dependency:
  `soundfile`.

* **Recolour variants**: right-click a sprite on the Audit page → **Make variant…** to get a
  second slime from the one a pack ships: a hue wheel with saturation and brightness, or a
  palette table with an eyedropper, a name, and for an enemy the HP, attack, XP and gold
  multipliers. The variant is an asset of its own (⧉ in the grid), rendered again from its
  source on every generation, and an enemy variant gets its own definition in
  `game/data/enemies/`. Nothing is placed on the demo maps. A variant whose source left the
  pack is `ASSET-029`.

* **Quests and Cutscenes tabs** in the Godot dock. Quests: a stage list with a form (id, title,
  description, condition with the inline checker, where it leads, the target entity with a
  picker from the open map, rewards), a read-only graph of the stages, and a test against a
  pretend game state. Cutscenes: a step list with a form per kind of step (move, face, say,
  wait, camera, flag, give, play sound, fade), the actors checked against the open map, and
  **Test**, which plays the cutscene in the game when one runs from the editor. Both export
  and import JSON, and every change is one undo step. A quest stage may now name its `next`
  stage and have `rewards` of its own.

* **A world of connected maps**: *Options → Starter map → Make a world of several areas* is a
  table of areas (name, biome, size, enemies, chests; village, field, forest, cave, shore).
  rpggen lays them on a grid around the village, joins neighbours with door pairs, places
  chests, enemies and decorations, and puts one key in an area before the gate that closes the
  first cave. The preview shows the world as one tile per area. The plan is stored in
  `rpggen/world_plan.json` and reused: once an area's map exists, a new seed or table changes
  nothing; a new row adds an area. The validator warns about a map the starter map cannot
  reach (`VAL-027`) and a door of the world that leads nowhere (`VAL-028`). The game's world
  map starts with an overview of the areas.

* **World repair**: rpggen mends the maps it made; yours it mends when you ask. After a
  generation a door that leads nowhere or a map that cannot be reached is mended in the area
  maps nobody changed (a missing spawn point, a door back, a door pair), after a backup, so
  **Restore previous** takes it back; the report lists it under *World repairs*. A map you
  changed is only offered the repair: **Repair the world…** on the Results page (with a
  preview), `rpggen-cli repair-world --target X [--dry-run]`, and **Fix** / **Fix all** in the
  dock's Validate tab (Ctrl+Z undoes). *Options → Advanced → Repair generated maps after a
  build* and `--no-repair-world` turn the automatic part off.

* Documentation for all of the above: the user guide (with pictures of review mode, the variant
  dialog, the areas table and the dock's Quests tab), the regeneration guide (the stored world
  plan and the repair rule), the project's README and the runtime's README and changelog.
  The version is 1.1.0.

## 1.0.0

The first release. It turns a 2D RPG asset pack into a Godot 4.7.2 project (tile sets with
collision and terrain, animated characters, a starter map with a house and a second area, dialogue,
inventory, saving, menus, and a turn-based or action-RPG combat system), checks the result by
loading and playing it headless, and regenerates it later without touching your work.

### The wizard

* A **welcome view**: try the sample, start with your own pack, or open an existing project;
  recent projects; the Godot that was found, or a **Download Godot** button that fetches the
  official 4.7.2 after you confirm the source, size and destination and verifies its checksum.
* A menu bar (File, Edit, View, Help): recent projects, undo and redo, a dark and a light theme,
  the thumbnail size, the user guide at the page you are on (F1), an error-code lookup, the
  keyboard shortcuts, *Report a problem…*, *Check for updates…* (only when you click) and *About*.
* **Project page**: the output folder is checked as you type, with a plain explanation of what
  is wrong; Next stays enabled and shows the missing fields instead of leaving you stuck.
* **Archetype page**: two large cards with a drawn preview of each game, what is generated and
  the controls.
* **Audit page**: a queue of the assets that need attention (`N` / `Shift+N`), a corner glyph on
  every thumbnail so status is not colour-only, bulk actions, folder rules, the grid editor,
  the animation editor, the object cutter, terrain proposals, and profiles.
* **Mapping page**: roles and, new, **sound slots** (map, battle and title music; menu, hit,
  attack, pick-up, chest, door, footstep, save and level-up sounds) filled from the audio of your
  packs by file name, with a preview and the length of every file.
* **Options page**: presets, and the starter map's size, counts and seed with a **live preview**
  of the real plan drawn from your assets.
* **Generate and Results pages**: each phase with its time and an estimate of the time left,
  cancel, a desktop notification when the window is in the background, and a results page that
  leads with a picture of the generated starter map and a *What next* list.
* **Resolve conflicts**: generated files you changed and rpggen remade (`.rpggen-new`) side by
  side with the version rpggen last wrote; keep yours, take the new one or merge them line by
  line, each backed up first (also `rpggen conflicts`).
* **Project page** pack cards (licence, size, what was found); **Archetype cards** drawn with
  your pack's own art; a **sidebar** with each step's status and jumps forward to any step that
  is ready; the Mapping page's candidates inline; an Options **summary panel**; the map preview's
  legend.
* **Audit**: the detail panel opens as wide as its form needs (it no longer scrolls sideways at
  the default window size), audio and font cards with playback, role badges, a filter bar that fits, a **change
  history**, frame sequences (one numbered image per frame) read as animations, eight-direction
  characters, **learned rules** (rpggen remembers your fixes and proposes them for the next pack;
  *Edit → Learned rules…*), and a printable **contact sheet** (PDF or PNG).
* **Options**: **imported Tiled and LDtk maps** (any of them can be the starter map), **export
  targets** (Windows, Web, Linux, macOS), and what git does with the purchased **pack art**
  (commit, leave out, Git LFS).
* **Before a regeneration** the changes are listed for you to confirm; **Results** has *Play*,
  *Open starter map*, warnings grouped with **one-click fixes**, and the checks that were
  skipped, with the reason.
* The wizard **follows the system theme**, fits laptop screens, and can be shown in **French**
  (*View → Language*; more languages can be added).
* **Storage** (*Edit → Storage…*): settings, your data and a size-limited cache in the system's
  usual folders.
* Tooltips and accessible names on every control, `Alt+N` / `Alt+B`, a tab order, and status
  colours that keep a 3:1 contrast on both themes.

### The generated game

* **Equipment** (weapon, armor, accessory, with a preview of the stat change), **shops**, a
  **quest journal**, **party members** who fight together and walk behind you (turn-based), and a
  **credits** screen built from the packs' licences.
* **Random-encounter zones** and deeper turn-based battles: **skills, MP, elements, statuses**,
  hit and evade, and enemy tactics.
* Action RPG: **bows and projectiles**, and **shooter, turret and charger** enemies.
* **Cutscenes** (an event sequencer started from trigger areas or dialogue), **keys, switches and
  gates**, locked doors.
* **Lighting** (ambient day and interior light, torches and lamps, an optional day/night cycle),
  a **minimap** and a **world map** with fog of war.
* **Save and load screens**, safe save rotation, key prompts that follow the device (keyboard,
  Xbox, PlayStation, Nintendo), and an in-game **language** setting.
* In the Godot editor: a **Dialogue** tab to write and test conversations, and **your own build
  steps** (`game/builder_recipes/`), which rpggen runs on every build.
* Music and sound effects wired to the slots; autosave (slot 0); a game-over screen with
  continue, try again and quit; the action-RPG heavy attack with screen shake and hit-stop; a
  second outdoor map behind the east wall; chests that show their open picture; a key prompt over
  what you can interact with.

### Under the hood

* A **scriptable CLI**: `--json`, documented exit codes, `--dry-run`, `--confirm`, `--tile-size`,
  and `conflicts`; unknown arguments are an error.
* Faster and safer analysis: each pack is hashed once, images are analysed in parallel with real
  progress and a Cancel that cancels, folder inventories are cached, archives are extracted with
  one size budget and no links; the base tile size is read from the packs.
* Generation shows Godot's live output and build progress; a failed run keeps a lean folder;
  logs live in one place, rotated, with run ids; unexpected errors get a report.
* A Godot download with a pinned checksum, resume and retry; git commits only the files rpggen
  wrote; the editor-open check matches exact project paths.
* The template project's GDScript is strict (typed), and a test that logs a script error fails.

* The targeted Godot version lives in one file (`rpggen/godot_target.py`); `tools/bump_godot.py`
  moves the app, the workflows and the texts to a new release.
* A deterministic starter-map planner shared by the preview (Python) and the builder (GDScript),
  checked against one fixture.
* Diagnostic bundles, export presets for Windows, Web, Linux and macOS with a test export per
  target, the community profile registry client,
  and packaging for Windows (installer and portable zip), Linux (AppImage and tar.gz) and macOS
  (an unsigned `.app`), each smoke-tested frozen, with one `SHA256SUMS.txt`.
