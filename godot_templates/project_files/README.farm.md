
## 22. Days, crops, the shop and the people (farm)

The game is a farm: you till the ground, plant seeds, water them and harvest what has grown,
sell it, and buy more seeds, through days and seasons. It is a top-down game like the one the
sections above describe, with maps, doors, a shop and people to talk to; what is different is
below. There is nothing to fight: a farm has no battles and no enemies.

A new game begins in your **farmhouse**, by the bed. The farm is the map outside its door
(`game/maps/farm.tscn`, with the house and the animal houses as rooms of their own beside it),
and the way out at its edge leads to the **village** (`game/maps/starter_map.tscn`), where the
shop and the people are.

| Action | Keyboard | Gamepad |
|--------|----------|---------|
| Walk | W A S D, the arrow keys | D-pad, left stick |
| Use what you hold on the tile ahead | Space, J, left mouse button | A (cross) |
| Talk, read, open, pick a ripe crop, the bed, the shipping bin | E | X (square) |
| Next thing of the hotbar | R | Right shoulder |
| Previous thing of the hotbar | Q | Left shoulder |
| Hold slot 1 to 10 of the hotbar | 1 to 9, 0 | |
| Menu, pause | Escape, Tab | Start |

(The bindings are in the Project Settings under **Input Map**.)

The **tile ahead** is the square in front of you with the white frame around it: what you hold
is used there. A tool works, a seed is planted in tilled soil, food is eaten. A ripe crop ahead
is picked whatever you hold. The frame is shown on the farm, where there is a field; the
village has none.

The **hotbar** is the first ten stacks of your bag: what lies further back in the bag cannot be
held until it moves up.

### A day

- A day runs from **6:00** to **2:00** of the night; a minute of the game is 0.7 seconds, so a
  day is about 14 minutes (`starter_map.day_length` in `rpggen/generator_config.json`:
  `short` is 10 minutes, `long` 20). Time stands still in menus and while somebody talks.
- A season has **28 days**, a week seven (`starter_map.days_per_season`: 14 or 7 make a
  shorter year). The seasons are spring, summer, autumn and winter.
- **Sleep** in your bed (`interact`) to end the day: the game is **saved** (into the autosave
  slot, and into the slot you saved or loaded by hand last; a game that has none yet is
  offered the save screen in the morning), and you wake at 6:00 with all your energy.
- If you are still up at **2:00** you pass out: you wake at your bed with half your energy and
  a tenth of your money gone. With **`starter_map.pass_out_loss`: false** in
  `rpggen/generator_config.json` the money stays. Passing out saves the game as sleeping does,
  so the loss cannot be taken back by loading.
- Sleeping is how a farm saves: these saves are made whatever *Settings → Autosave* says.
- **The light** outdoors follows the clock of the game (dawn at 6:00, dark at night), whatever
  the *Day and night* setting says; that setting is for the other kinds of game.
- A new game starts with a hoe, a watering can, fifteen seeds of the first crop and a little
  money (`starter_map.starting_money`, 100).

### Energy

The yellow bar over the hotbar is your energy, 100 when you are rested. A tool costs energy
when it does something (the hoe, the can and the sickle 2, the axe 4, a cast of the rod 3)
and none when it does not. At zero you walk at half your speed and no tool works. Eating
restores it: hold what you harvested and `use` it (away from a ripe crop, which would be picked
instead; when you are rested nothing is eaten). Sleeping fills it.

### The tools

| Tool | What it does |
|------|--------------|
| Hoe | Tills ground into soil. Only the ground of your plot can be tilled. |
| Watering can | Waters tilled soil. It holds water for 20 squares; `use` it at water, or `interact` with the pond or the well, to fill it (that costs no energy). |
| Sickle | Cuts a ripe crop, a withered one and grass. Sold at the shop. |
| Axe | Clears stumps and branches. Sold at the shop. |
| Fishing rod | Casts a line into the pond (see *Fishing and foraging*). Sold at the shop of a farm that has a pond. |

A tool is not for sale again once you have it, and cannot be sold or shipped.

### Crops

- A seed goes into **tilled soil**, in a season the crop grows in (the game tells you when it
  does not).
- Every **night**, a crop whose soil was **watered** that day grows by a day; one that was not
  watered waits. In the morning the soil is dry again.
- After its days a crop is **ripe**: pick it with `interact` or `use`. Some crops grow again
  after the harvest and are ripe again a few days later.
- When the season changes, a crop that does not grow in the new season **withers**, a ripe one
  that was not picked too. Cut it away with the sickle.
- A harvest is refused while your bag has no room for it; the crop stays standing.
- Tilled soil with nothing on it that is not watered for three nights is ground again.

The crops of the game are in **`game/data/crops.json`**, written once and then yours. One
entry is one crop:

```json
{
  "id": "berry",
  "name": "Berry",
  "seed": "seed_berry",
  "produce": "crop_berry",
  "seasons": ["spring", "summer", "autumn"],
  "days": 4,
  "stages": 5,
  "regrow": 0,
  "seed_price": 20,
  "price": 40,
  "energy": 16,
  "scene": "res://generated/scenes/farm/crops/berry.tscn"
}
```

- `seed` and `produce` are item ids: the items are `game/data/items/seed_berry.tres` and
  `crop_berry.tres`, where their names, icons and prices are. `seed_price` and `price` are
  what rpggen gave those two items when it made them: to change a price, change the item's
  **Value**.
- `seasons` is when it can be planted and does not wither; `days` is how many watered nights
  it takes; `regrow` is after how many days it is ripe again (0: it is gone when picked).
- `stages` is how many pictures its scene has; they are spread evenly over its days.
- `energy` is what eating one restores. `yield` (optional) is how many a harvest gives.

**To change a crop**, change its entry: a berry that takes two days is `"days": 2`. **To add
one**, copy an entry, give it a new `id`, `seed` and `produce`, make the two items (copy
`seed_berry.tres` and `crop_berry.tres` in the editor and change their `id`), and point
`scene` at the scene of a crop you have (the pictures of another crop will do until you have
drawn your own). A crop your packs gain later is added to `generated/data/crops.json` by the
next generation; the game grows every crop of that list that your own list does not have. So
a crop is not removed by deleting its entry: it comes back from that list. **To remove one**,
put this in the place of its entry:

```json
{ "id": "berry", "removed": true }
```

The shop then sells no seed of it, and a seed that is still in a bag can no longer be planted.
(Pick what is standing in a saved game first: a crop the game no longer knows stays where it
is, does not grow and cannot be picked.)

### Animals

A farm made with the option **Animals** (`starter_map.animals`: `coop`, or `coop_and_barn`) has
a coop, or a coop and a barn, on the farm: a building with a room inside and a fenced yard
before it. The default is `none`: such a farm has no animal house, and nothing of this part is
in its game.

- **Buying.** In its hours the shop lists a row for every kind of animal whose house has a free
  stall (a coop and a barn have four each), and **hay**. An animal you buy is not in your bag:
  it moves into its house. It gets the next name of a list and the next colour of its kind.
- **Where they are.** From 6:00 to 18:00 on a fair day the animals are out in the yard of their
  house and wander about in it. From 18:00 on, and all day when it rains, storms or snows, each
  is in its stall in the house; at night it sleeps.
- **Feeding.** Hold hay and `interact` with the **trough** in the house: one portion feeds
  every animal of that house for the day. Grass you cut with the sickle gives one hay (on a
  farm with an animal house).
- **Petting.** `interact` with an animal pets it, once a day (15 points of friendship).
- **In the morning** an animal that was fed has its product. A hen's **egg lies in the coop**,
  a square below her stall: `interact` picks it up. A cow gives her **milk** when you
  `interact` with her; no pail is needed. A product that is not taken stays, and the animal
  makes no second one until it is. A fed night also gives 5 points; an animal that was not fed
  gives nothing and loses 20. Animals never die and never leave.
- **Friendship** is counted in points, ten hearts of 100 each. From five hearts on an animal
  gives the **large** product: an item of its own (`egg_large`) that sells for half as much
  again. `interact` with an animal you have petted already tells you its hearts.

The animals of the game are in **`game/data/animals.json`**, written once and then yours:

- `animals`: one entry a kind, with its `house` (`coop` or `barn`), what the shop asks for it
  (`cost`; the item `ticket` is the row the shop lists, and never reaches your bag), what it
  gives (`product`, and `large` from five
  hearts on; their prices are the `value` of those two items in `game/data/items/`), how the
  product is taken (`collect`: `floor`, it lies in the house; `hand`, `interact` with the
  animal) and its pictures (`variants`: a `scene` for each colour).
- `feed`: its `item`, what goes into a trough, and its `price`, what the shop asks for it.
  `names`: what the animals are called, in turn.
- `houses`: for each house the scene of its room (`map`), the map its yard is on (`yard_map`)
  and its `stalls`. A room has the markers `Markers/Trough` and `Markers/Stall1` and so on;
  the yard is the node `Yards/Coop` (or `Barn`) of the farm's map, whose metadata `yard` is its
  ground in squares.

A kind or a colour your packs gain later is added to `generated/data/animals.json` by the next
generation; the game has every kind and house of that list that your own list does not have.
So a kind is not removed by deleting its entry; write `{ "id": "duck", "removed": true }` in its
place among the `animals`, and the shop no longer sells it. (The houses cannot be removed this
way: they are rooms of the map.)
Whether a farm has a coop or a barn is decided when it is first generated, with its map.

### Money: the shipping bin and the shop

- **The shipping bin.** With something you can sell in your hand, `interact` puts the whole
  stack into the bin. With a tool or nothing in your hand, `interact` takes the last stack
  back out. What is in the bin at night is **sold overnight** at its price, and the morning
  begins with a list of what it earned.
- **The shop** in the village is open from **9:00 to 17:00** and closed on **Sunday**; its
  keeper says so when you come at another time. It sells the seeds of the crops that grow in
  the season, the sickle and the axe (and the fishing rod, on a farm with a pond), and buys
  what you bring at its price. Its file is
  `game/data/shops/village_shop.tres` (**Opens**, **Closes**, **Closed Weekday**, and
  **Seasonal** for the seeds).

### The weather and the seasons

- Every day is **sunny** or **rainy**; summer also has **storms**, and in winter it **snows**
  and never rains. The first day of a game is always fair. The weather of a day follows from
  the game's seed and the date, so loading a save does not change it.
- On a rainy or stormy day the **rain waters your fields**: every tilled square is wet in the
  morning, and what you till that day is wet at once. Leave the can at home.
- Outdoors rain and snow fall over the screen and the light is duller; indoors you see
  neither. People with a rainy-day entry in their schedule keep to it.
- The **sign** beside the door of your house tells tomorrow's weather: `interact` with it.
- When the packs have a sheet of ground or trees once a season, the outdoor maps change with
  the season. The table of those sheets is `generated/data/seasons.json`.
- The **music** follows the season on outdoor maps when the sound slots *Spring music* to
  *Winter music* are filled (a season without its own plays the first that is), and after
  20:00 the *Night music* when that slot is filled.

### Fishing and foraging

- **Foraging.** Every morning a few things lie at the edges of the farm: what lies there
  depends on the season. Walk onto one and pick it up with `interact`. What you do not pick up
  is gone the next morning, when other things lie in other places. Where and what follows from
  the game's seed and the date, so loading a save does not change a morning.
- The places are the markers **`Forage/Spot1`, `Spot2`, ...** of `game/maps/farm.tscn`: move
  them, delete them or add more (`Spot9`, ...) in the editor. Any map with such markers has
  things to forage.
- **Fishing.** A farm with a **pond**, or with a **beach** among its added maps, sells a
  **fishing rod** at the shop (a well has no fish: the game says so when you cast into it).
  Hold the rod, face the water and `use`
  it: the line is out and you stand still. After **one to four seconds** a fish **bites** (a
  mark over your head; `use` again before that pulls the line in). Then a bar opens: the pale
  line is the fish, the green zone is yours. **Hold `use`** and the zone rises, let go and it
  sinks. While the zone is over the fish the meter beside the bar fills; when it is full the
  fish is yours, and when it runs empty the fish got away.
- A cast costs 3 energy and ten minutes of the day; landing or losing a fish another twenty.
  A fish that is landed while your bag is full is lost.
- Which fish bites depends on the **season** and the **time of day**: the morning (before
  12:00), the day (before 18:00) and the evening.
- Fish and what you forage are items like your harvest: sell them (the bin, the shop), eat
  them (`use`) or give them away.
- With **`starter_map.fishing`: false** in `rpggen/generator_config.json` the shop does not
  sell the rod. (The shop's file is written once: in a project that has it already, add or
  remove the row `fishing_rod` in `game/data/shops/village_shop.tres` yourself.)

The fish and the things to forage are in **`game/data/forage.json`**, written once and then
yours: a list `forage` and a list `fish`.

```json
{
  "id": "fish_carp",
  "name": "Carp",
  "item": "fish_carp",
  "seasons": ["spring", "summer", "winter"],
  "times": ["day", "evening"],
  "water": ["pond"],
  "price": 45,
  "energy": 12,
  "speed": 1.2
}
```

- `item` is the id of the item you get: `game/data/items/fish_carp.tres`, where its name, its
  icon and its price are (`price` here is what rpggen gave that item when it made it).
- `seasons` is when it is there; a fish also has `times` (`morning`, `day`, `evening`),
  `water` (`pond`, or `sea` for a fish that bites at a beach) and `speed` (how fast it moves
  along the bar: 1 is easy, 1.4 is lively).
- `energy` is what eating one restores.
- An entry of `forage` has `id`, `name`, `item`, `seasons`, `price` and `energy`, and may have
  `maps`: the kinds of map it lies on (`["beach"]`). On a map whose kind has things of its own
  only those lie; everywhere else the things that name no kind.

**To add a fish or a thing to forage**, copy an entry, give it a new `id` and `item`, and make
the item (copy `fish_carp.tres` in the editor and change its `id`, name and icon). What your
packs gain later is added to `generated/data/forage.json` by the next generation; the game
knows every entry of that list that your own list does not have. So a fish or a thing is not
removed by deleting its entry; write `{ "id": "fish_eel", "removed": true }` in its place (in
`fish` or in `forage`), and it no longer bites or lies anywhere.

### Added maps: a forest, a beach

Every row of *Added maps* (the wizard's Options page, or `starter_map.added_maps` in
`rpggen/generator_config.json`: `{ "name": "Old woods", "kind": "forest" }`) is a map of its
own beside the farm: `game/maps/farm_map_1.tscn`, `farm_map_2.tscn`, ... in the order of the
rows. A row without a `kind` is a beach when its name has a word like *beach*, *shore* or
*coast*, else a forest.

- **A forest** is thick with trees, with a path to a clearing, bushes, rocks, flowers, and
  branches, stumps and grass to clear with the axe and the sickle.
- **A beach** has sand, the sea along one side, driftwood and beach grass, and a few trees on
  the far side. Stand at the water, hold the rod and `use` it: the fish whose `water` is `sea`
  bite there. What lies on a beach in the morning are the things whose `maps` say `beach`
  (shells, seaweed), not the farm's.
- Things to forage lie at the markers `Forage/Spot<n>` of each, as on the farm. The weather,
  the seasons and the light of the day are the farm's.
- **The way there** is a worn patch of ground with an arrow at the edge of the farm, one for
  every added map: walk onto it. The way back is the gap in the edge of the added map.
- **Each map is built once and is then yours.** To add another, add a row and generate again:
  the new map is built, and neither the farm nor a map that was added before is touched. A
  row that is removed takes nothing away. The kind of a map that exists is fixed.
- The farm's side of the doors (the patch, the door `to_farm_map_<n>` and the spawn
  `from_farm_map_<n>`) is **not** in `game/maps/farm.tscn`: the farm shows the scene
  `generated/scenes/farm/trails.tscn` (its node `Trails`), which rpggen writes on every build.
  That is how a map added later gets its door without your farm being written again. Do not
  edit that scene (your changes would be lost), and keep the node `Trails` if you want the
  doors. To move a door, turn the node `Trails` into your own (*Make Local*) and move its
  children; rpggen then no longer adds doors for later maps, and you add them yourself.
- A farm has room for as many added maps as it has free places at its edge (eight at most;
  the wizard says so when a row is one too many).
- A farm that was generated before added maps were built has no node `Trails`: its rows stay
  names, and the report says so.

### The cave (Combat)

With the feature *Combat* on, the farm has a **cave** among its added maps (a row of the kind
`cave`, or one called *Cave* that rpggen adds by itself). Without *Combat* there is no cave,
no sword and nothing to fight, and a cave row is refused.

- The cave is rock with chambers hollowed out of it and tunnels between them, dim and dry (its
  root is an interior: no rain falls there). The rock is the shapes `Rock` and the body
  `RockWall` of `game/maps/farm_map_<n>.tscn`.
- **The enemies** are the action RPG's (`addons/rpg_runtime/archetypes/arpg/`, which only a farm
  that fights has): the scenes under `generated/scenes/enemies/` with their definitions in
  `game/data/enemies/` (hit points, attack, how far they see, how they fight). Each in the
  cave is remembered as `farm_map_<n>_enemy_<m>`: a defeated one stays away for the rest of the
  day and is back the next morning. Move them, add more (a copy of one, with an `entity_id` of
  that form) or take them away in the editor.
- **The sword** (`game/data/items/farm_sword.tres`) is sold at the shop for 200. Hold it in the
  hotbar and press `use` to swing it: it hits what stands ahead, and adds the `attack` of its
  `modifiers` (4) to the farmer's own. A swing costs no energy.
- **Health** is the red bar over the energy bar. The farmer's hit points are the hero's
  (`game/data/actors/hero.tres`), full again every morning.
- **What an enemy leaves**: one of the things of the cave (the entries of `forage.json` whose
  `maps` say `cave`: ore, a crystal, a mushroom), where it fell; walk over it. The same things
  lie at the cave's places in the morning. Sell them in the bin or at the counter; the mushroom
  can be eaten.
- **Being defeated is passing out**: the day ends at once, and you wake at the bed as after
  2:00 (half the energy, and with `pass_out_loss` a tenth of the money gone).
- Switching *Combat* off later keeps the cave, its enemies and the sword: a map that is
  planned is not taken away (the report says so). To empty the cave, take its enemies out of
  its map in the editor.

### The screen

In the top-left corner: the time (in steps of ten minutes), the weekday, the day and the
season, the weather, and your money. At the bottom: the energy bar and the ten slots of the
hotbar, the held one bright. Top right: a note when you harvest something, and in the morning
what the shipping bin paid.

### People

The people of the village are in **`game/data/people.json`**, written once and then yours. One
entry is one person: an `id` and a `name`, the `home` (which house), a `job`, a `schedule`,
and what they love, like and dislike (`loves`, `likes`, `dislikes`: lists of item ids).

- A **schedule** is a list of entries, each with the `hour` from which it holds and where the
  person is then. An entry may name the `days`
  of the week it holds on (0 is Monday) and a `weather` (`"rain"`: on a rainy or stormy day).
  Of the entries of the day, the last whose hour has come is in force; a rainy-day entry wins
  over one that names no weather.
- **Friendship** is counted in points, shown as hearts: ten hearts of 250 points each.
  Talking to somebody gives 20 points, once a day. A **gift** gives 80 points when it is
  loved, 45 when it is liked, 20 when the person does not care, and takes 20 when it is
  disliked; a person takes two gifts a week, counted from Monday.
- **To give a gift**, hold it and `interact` with the person: one of what you hold is given
  instead of a talk. Tools and seeds are never given, so hold one of those to talk.
- The pause menu has a **People** page: who you have met, their hearts, and what you know of
  their taste.
- A person whose schedule has them on another map is away from this one. This file is read
  as it is: a person you delete from it is gone. (No list of rpggen's fills it in, so it needs
  no `"removed": true`; an entry that has the mark is nobody.) Their NPC still stands in the
  village until you delete it from the map.

### Festivals and birthdays

A farm made with the option **Festivals and birthdays** (`starter_map.festivals`, on unless
you switch it off) has a festival in every season and a birthday for everybody. A farm made
with it off has neither, and nothing of this part is shown in its game.

**A festival** is one day: the shop is closed all day and says why, everybody stands on the
village square from 9:00 to 20:00 whatever their schedules and the weather say, and there is
one small thing to do. The day before, the weather's sign by your house says that it is
coming, and so do the people. In a season of 28 days the festivals are on spring 12, summer
12, autumn 26 and winter 26 (in one of 14 days: 5, 5, 12 and 12; in one of 7: the 5th of
every season). They are always a Friday.

- **Spring, the egg hunt**: five eggs lie in the village for the day. `interact` with one
  finds it and pays 20; the last one pays the prize of 150 as well.
- **Summer, the fishing day** (on a farm whose shop sells the rod): every fish you land that
  day is counted, wherever you fish, and the third wins 200. A farm that cannot fish has a
  **summer fair** instead: a contest on how many things your shipping bin sold this season.
- **Autumn, the harvest fair**: `interact` with the judges' table on the square. It judges
  the dearest thing your shipping bin sold this season (a thing counts from the morning
  after you put it in), once; from a price that the plan chose on, it wins 300.
- **Winter, the feast**: hold any food and `interact` with the table. One of it is shared,
  and everybody's friendship grows by 60 points.

The festivals are in **`game/data/events.json`**, written once and then yours. One entry is
one event:

```json
{
  "id": "egg_hunt",
  "kind": "egg_hunt",
  "name": "Egg hunt",
  "season": "spring",
  "day": 12,
  "from": 9,
  "to": 20,
  "map": "starter_map",
  "place": "square",
  "spots": ["festival_egg_1", "festival_egg_2", "festival_egg_3", "festival_egg_4", "festival_egg_5"],
  "each": 20,
  "goal": 5,
  "prize": { "gold": 150 }
}
```

- `kind` is what there is to do: `egg_hunt`, `fishing_count`, `produce_contest`, `feast`, or
  `gathering` (nothing: the people stand on the square and the shop is closed). `name` is
  what the calendar, the sign and the shop call it.
- `season` and `day` say when; with a `year` it happens in that year only. A day your seasons
  do not have (26 in a season of 14 days) is folded into the season week by week, so it stays
  on its day of the week. `from` and `to` are the hours the people stand at `place`.
- `map` and `place` name the map and the marker the people gather at (a `Marker2D` in the
  group `rpg_place`, as the places of the schedules are); each person takes the spot of it
  their own schedule names (`square_3`), else the place itself. `"shop_closed": false` lets
  the shop keep its hours.
- `spots` are the markers the eggs lie at, `each` what one pays. `table` is the marker the
  table of a contest or a feast stands at. Move a marker in `game/maps/starter_map.tscn` to
  move what stands there.
- `goal` is the number from which the prize is won (eggs, fish, things shipped), or for a
  contest with `"judge": "price"` the price the dearest thing must have; `"judge": "count"`
  counts the things instead. `prize` is `{ "gold": 150 }`, `{ "item": "seed_corn", "qty": 5 }`
  or both. `points` is the friendship a feast gives everybody.
- **To add an event**, add an entry with an `id` of its own. **To change one**, change its
  entry. An event you delete comes back from `generated/data/events.json`, the list rpggen
  planned, since the game reads from there what your list does not have; **to remove one**,
  put `{ "id": "egg_hunt", "removed": true }` in the place of its entry.
- A village that was built before your project had festivals has no markers `festival_egg_<n>`
  and `festival_table`: the eggs and the table are then put a few cells round the marker
  `square`, wherever that is, and one may end up where you cannot walk. Add the markers to
  the map (copy `square`, rename it) to say where they belong.

**A birthday** is the `birthday` of a person's entry of `game/data/people.json`:

```json
"birthday": { "season": "summer", "day": 20 }
```

The first gift you give somebody on that day counts **five times** when it is loved, liked or
taken politely (400, 225 or 100 points) and is not one of the week's two; a disliked gift
takes its 20 points as on any day. A second gift on the same day is a gift like any other.
The person has a line for the day, the morning begins with a note, and the **People** page
names the day of everybody you have met. Change the entry to move a birthday; `"birthday": {}`
is no birthday. A person whose entry has no `birthday` at all (a file from before your project
had festivals) has the one rpggen planned, which is in `generated/data/people.json`.

**The calendar** shows a season as its weeks: today, the festival and the birthdays, with a
list of what each marked day is; *Earlier* and *Later* turn to the other seasons. It hangs on
the wall of your farmhouse (`interact` with it), and the pause menu has it as **Calendar**. A
farmhouse that was built before your project had festivals has none on its wall, since a room
that exists is never built again: copy the node `WallCalendar` from a newer project's
`game/maps/farm_house.tscn`, or use the pause menu. In the isometric view the calendar is a
board on a post that stands on a cell of the room.

**What a person says** on such a day is a line of their dialogue
(`game/data/dialogue/person_<id>.tres`) with one of these as its condition: `festival` (today
is one), `festival_tomorrow`, `birthday:<id>` (today is that person's), `event:<kind>` (today
has an event of that kind, such as `event:egg_hunt`). A line whose condition does not hold is
passed over. The dialogues of a project from before it had festivals have no such lines: add
them in the dialogue tab of the dock.

### Marriage

A farm made with **People to court** above 0 (`starter_map.courtable`, 2 unless you change
it; 0 turns marriage off) has that many people who can be courted and married. Who they are
is chosen once, when the people are planned, and kept: `"courtable": true` in their entry of
`game/data/people.json`. Change it there to court somebody else (a person whose entry has no
`courtable` at all, a file from before your project had marriage, has the one rpggen planned,
in `generated/data/people.json`).

- **Eight hearts, then a bouquet.** Somebody you can court has at most **eight hearts** until
  you court them. From eight, give them a **bouquet** from the shop (hold it and `interact`):
  the courting begins and the two last hearts open. Below eight hearts, or to somebody who
  cannot be courted, the bouquet is not taken and stays in your bag.
- **Ten hearts, then a pendant.** At ten hearts a **pendant** from the shop, given to the one
  you court, is a yes. The **wedding** is three days later (the next day that is no festival,
  if that one is): a day for everybody on the village square, on the calendar, the shop
  closed. At the end of that day you are married, whether you went or not. Only one pendant is
  ever taken.
- **The spouse** lives in your farmhouse: in the morning beside the place you wake, on two
  afternoons a week (Tuesday and Thursday, when it is dry) on their own spot of the square,
  home again from 17:00, and asleep (not seen) from 22:00. On a festival they are on the
  square with everybody. In the farmhouse they say what they did that morning.
- **They help** on some mornings: they **water** part of the plot (the dry cells with a crop
  first, at most eight, about half), **feed** the animals (every empty trough), or **leave
  something on the table** of the farmhouse (a crop of the season; `interact` with the table).
  The first morning after the wedding is always a watering one. A rainy morning needs no
  watering, and a farm without animals no feeding: such a morning is a quiet one.
- **Neglect.** Every night, everybody you have met and did not talk to that day loses 2
  points. Nothing worse happens: a courting, an engagement or a marriage is never undone.
  There are no children.

The bouquet (200) and the pendant (2000) are `game/data/items/bouquet.tres` and `pendant.tres`
(yours; change their price there). The shop sells them until you are married. A person you
can court has three more lines in their dialogue, each said at one stage only: `courting:<id>`,
`engaged:<id>` and `spouse:<id>` (conditions you can use in any dialogue). The dialogue of a
person from a project made before it had marriage has no such lines.

**The bed is for two.** A farmhouse planned with marriage has two beds side by side, both
of which end the day. A farmhouse that was built before your project had marriage keeps its
one bed, since a room that exists is never built again: the spouse sleeps there all the same
(at night they are not seen) and stands beside it in the morning. The save keeps everything in
the flags of the game (`farm_marriage`).

### The isometric view

A farm made with **`projection: isometric`** is the same game on diamonds: the same plan of
the farm, the same crops, people and saves. What is different:

- The **tile ahead** is the diamond in front of you with the white frame around it. A diamond
  has four neighbours: up and to the right (north), down and to the right (east), down and to
  the left (south), up and to the left (west). The one you face is the one you last walked
  towards; standing still after a map change it is the one your facing names (up is north,
  right east, down south, left west). Watch the frame: what you hold is used there.
- With the default controls **up is up on the screen**, so walking straight up crosses the
  corners of the diamonds; walk up and to the right to go along a row of the field. With
  `iso_controls: grid` in the config the four directions follow the rows instead.
- **Talking, the bed, the bin, the trough** (`interact`) reach where you look on the screen
  (with `grid` controls: towards the diamond you face), as in every isometric game rpggen
  makes. A ripe crop on the tile ahead is always picked with `use`.
- Tilled and watered soil are the flat isometric tile your packs tagged `soil` or `watered`
  when they have one; else they are drawn as diamonds, as the plot and a pond without a water
  tile of the packs always are (the `Soil` layer, `generated/tilesets/farm_soil.tres`). That
  tile set is made again when you regenerate, so tiles added to it are lost. To use tiles of
  your own, tag them `soil` or `watered` in the audit and regenerate; or give the `Soil` layer
  of `game/maps/farm.tscn` a tile set of your own under `game/` (a copy of that one, with its
  custom data `tillable` and `water`) and the `Field` node the source and the cell of your
  tiles (`tilled_source`, `tilled_tile`, `watered_source`, `watered_tile`).
- A plant an isometric pack drew on a diamond and called a crop (`cornDouble_N.png`) is a
  crop: its picture is the ripe one, and the stages before it are drawn.
- What your packs did not draw for this view is a stand-in made of boxes on its diamond: the
  buildings, fences and gates, the well, trees, bushes, rocks, flowers, stumps, branches and
  grass, the bin, the bed, the trough. All but the last three are ordinary nodes of the maps
  (`Polygon2D` under a body): replace them with your own sprites, keeping the body and its
  shape. The bin and the bed are the scenes `generated/scenes/farm/shipping_bin.tscn` and
  `bed.tscn`, made again when you regenerate (put a scene of your own in their place on the
  map), and the trough is drawn by the game at the marker `Markers/Trough` of an animal
  house. The tools, the crops, the hen and the things to
  forage of the drawn farm kit are pictures seen from the front and stand on the middle of
  their diamond, as the people do.
- A crop, a fence, a tree and everything else that stands on the map stands on the **middle
  of its diamond** and is sorted by it: you are drawn behind what is south or east of you and
  in front of what is north or west.
- A room (the farmhouse, the coop, the barn) has walls only when your packs have isometric
  wall pieces; without them it is a floor whose edge cannot be crossed.
- The **RPG Project Tools** dock places what you drag from it on a grid of squares: on an
  isometric map, move the thing onto its diamond by hand afterwards.

### Where things are

| What | Where |
|------|-------|
| The crops | `game/data/crops.json` (yours) |
| The same list as rpggen planned it | `generated/data/crops.json` (rewritten on every build) |
| The people, each with their birthday | `game/data/people.json` (yours) |
| The festivals | `game/data/events.json` (yours) |
| The same list as rpggen planned it | `generated/data/events.json` (rewritten on every build) |
| Where the eggs lie and the table stands on a festival | the markers `festival_egg_<n>` and `festival_table` under `Places` of `game/maps/starter_map.tscn` (yours) |
| The calendar on the wall | the node `WallCalendar` of `game/maps/farm_house.tscn` (yours) |
| Who can be courted | `courtable` of a person in `game/data/people.json` (yours) |
| The bouquet and the pendant | `game/data/items/bouquet.tres` and `pendant.tres` (yours) |
| The bed for two | the nodes `Bed` and `Bed2` of `game/maps/farm_house.tscn` (yours) |
| The animals, the feed and the animal houses | `game/data/animals.json` (yours) |
| The same list as rpggen planned it | `generated/data/animals.json` (rewritten on every build) |
| The scenes of the animals | `generated/scenes/farm/animals/` |
| The fish and the things to forage | `game/data/forage.json` (yours) |
| The same list as rpggen planned it, with the forage places of the plan | `generated/data/forage.json` (rewritten on every build) |
| The places where things to forage lie | the markers `Forage/Spot<n>` of `game/maps/farm.tscn` and of every added map (yours) |
| The maps added to the farm | `game/maps/farm_map_<n>.tscn` (yours) |
| The farm's doors to them | `generated/scenes/farm/trails.tscn` (rewritten on every build), shown by the farm's node `Trails` |
| The enemies of the cave (Combat) | `game/data/enemies/` (yours) and `generated/scenes/enemies/` |
| The sword (Combat) | `game/data/items/farm_sword.tres` (yours) |
| The shop | `game/data/shops/village_shop.tres` (yours) |
| What a new game starts with | `game/data/new_game.tres` (yours) |
| The seeds, the produce, the fish, the forage and the tools as items | `game/data/items/` (yours) |
| The plan the crops, the farm and the people come from | `rpggen/world_plan.json`, the section `farm` |
| The scenes of the crops, the shipping bin, the bed, the weather sign | `generated/scenes/farm/` |
| The sheets that change with the season | `generated/data/seasons.json` |
| The farm's mode with its HUD and its weather | `generated/scenes/combat/combat_mode.tscn` |

Everything under `generated/` is made again when you regenerate. The files under `game/` are
written once and then left alone: change them freely.
