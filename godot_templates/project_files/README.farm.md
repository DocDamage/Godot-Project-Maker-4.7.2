
## 22. Days, crops, the shop and the people (farm)

The game is a farm: you till the ground, plant seeds, water them and harvest what has grown,
sell it, and buy more seeds, through days and seasons. It is a top-down game like the one the
sections above describe, with maps, doors, a shop and people to talk to; what is different is
below. There is nothing to fight unless you switch **Combat** on in the options.

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
is picked whatever you hold.

### A day

- A day runs from **6:00** to **2:00** of the night; a minute of the game is 0.7 seconds, so a
  day is about 14 minutes. Time stands still in menus and while somebody talks.
- A season has **28 days**, a week seven. The seasons are spring, summer, autumn and winter.
- **Sleep** in your bed (`interact`) to end the day: the game is **saved** (into the autosave
  slot, and into the slot you saved or loaded by hand last; a game that has none yet is
  offered the save screen in the morning), and you wake at 6:00 with all your energy.
- If you are still up at **2:00** you pass out: you wake at your bed with half your energy and
  a tenth of your money gone. With **`starter_map.pass_out_loss`: false** in
  `rpggen/generator_config.json` the money stays.
- A new game starts with a hoe, a watering can, fifteen seeds of the first crop and a little
  money (`starter_map.starting_money`, 100).

### Energy

The yellow bar over the hotbar is your energy, 100 when you are rested. A tool costs energy
when it does something (the hoe, the can and the sickle 2, the axe 4, a cast of the rod 3)
and none when it does not. At zero you walk at half your speed and no tool works. Eating restores it: hold what you
harvested and `use` it. Sleeping fills it.

### The tools

| Tool | What it does |
|------|--------------|
| Hoe | Tills ground into soil. Only the ground of your plot can be tilled. |
| Watering can | Waters tilled soil. It holds water for 20 squares; `use` it at water to fill it. |
| Sickle | Cuts a ripe crop, a withered one and grass. Sold at the shop. |
| Axe | Clears stumps and branches. Sold at the shop. |
| Fishing rod | Casts a line into the pond (see *Fishing and foraging*). Sold at the shop of a farm that has a pond. |

### Crops

- A seed goes into **tilled soil**, in a season the crop grows in (the game tells you when it
  does not).
- Every **night**, a crop whose soil was **watered** that day grows by a day; one that was not
  watered waits. In the morning the soil is dry again.
- After its days a crop is **ripe**: pick it with `interact` or `use`. Some crops grow again
  after the harvest and are ripe again a few days later.
- When the season changes, a crop that does not grow in the new season **withers**. Cut it
  away with the sickle.
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
  `crop_berry.tres`, where their names, icons and prices are.
- `seasons` is when it can be planted and does not wither; `days` is how many watered nights
  it takes; `regrow` is after how many days it is ripe again (0: it is gone when picked).
- `stages` is how many pictures its scene has; they are spread evenly over its days.
- `energy` is what eating one restores. `yield` (optional) is how many a harvest gives.

**To change a crop**, change its entry: a berry that takes two days is `"days": 2`. **To add
one**, copy an entry, give it a new `id`, `seed` and `produce`, make the two items (copy
`seed_berry.tres` and `crop_berry.tres` in the editor and change their `id`), and point
`scene` at the scene of a crop you have (the pictures of another crop will do until you have
drawn your own). A crop your packs gain later is added to `generated/data/crops.json` by the
next generation; the game grows every crop of that list that your own list does not have.

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
  every animal of that house for the day. Grass you cut with the sickle gives one hay.
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
  (`cost`, the `value` of the item `ticket`), what it gives (`product`, and `large` from five
  hearts on; their prices are the `value` of those two items in `game/data/items/`), how the
  product is taken (`collect`: `floor`, it lies in the house; `hand`, `interact` with the
  animal) and its pictures (`variants`: a `scene` for each colour).
- `feed`: the item that goes into a trough. `names`: what the animals are called, in turn.
- `houses`: for each house the scene of its room (`map`), the map its yard is on (`yard_map`)
  and its `stalls`. A room has the markers `Markers/Trough` and `Markers/Stall1` and so on;
  the yard is the node `Yards/Coop` (or `Barn`) of the farm's map, whose metadata `yard` is its
  ground in squares.

A kind or a colour your packs gain later is added to `generated/data/animals.json` by the next
generation; the game has every kind and house of that list that your own list does not have.
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
- **Fishing.** A farm with a **pond** sells a **fishing rod** at the shop (a farm with a well
  has no fish: the game says so when you cast into it). Hold the rod, face the water and `use`
  it: the line is out and you stand still. After **one to four seconds** a fish **bites** (a
  mark over your head; `use` again before that pulls the line in). Then a bar opens: the pale
  line is the fish, the green zone is yours. **Hold `use`** and the zone rises, let go and it
  sinks. While the zone is over the fish the meter beside the bar fills; when it is full the
  fish is yours, and when it runs empty the fish got away.
- A cast costs 3 energy and ten minutes of the day; landing or losing a fish another twenty.
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
  `water` (`pond`) and `speed` (how fast it moves along the bar: 1 is easy, 1.4 is lively).
- `energy` is what eating one restores.
- An entry of `forage` has `id`, `name`, `item`, `seasons`, `price` and `energy`.

**To add a fish or a thing to forage**, copy an entry, give it a new `id` and `item`, and make
the item (copy `fish_carp.tres` in the editor and change its `id`, name and icon). What your
packs gain later is added to `generated/data/forage.json` by the next generation; the game
knows every entry of that list that your own list does not have.

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
  disliked; a person takes two gifts a week.

### Where things are

| What | Where |
|------|-------|
| The crops | `game/data/crops.json` (yours) |
| The same list as rpggen planned it | `generated/data/crops.json` (rewritten on every build) |
| The people | `game/data/people.json` (yours) |
| The animals, the feed and the animal houses | `game/data/animals.json` (yours) |
| The same list as rpggen planned it | `generated/data/animals.json` (rewritten on every build) |
| The scenes of the animals | `generated/scenes/farm/animals/` |
| The fish and the things to forage | `game/data/forage.json` (yours) |
| The same list as rpggen planned it, with the forage places of the plan | `generated/data/forage.json` (rewritten on every build) |
| The places where things to forage lie | the markers `Forage/Spot<n>` of `game/maps/farm.tscn` (yours) |
| The shop | `game/data/shops/village_shop.tres` (yours) |
| What a new game starts with | `game/data/new_game.tres` (yours) |
| The seeds, the produce, the fish, the forage and the tools as items | `game/data/items/` (yours) |
| The plan the crops, the farm and the people come from | `rpggen/world_plan.json`, the section `farm` |
| The scenes of the crops, the shipping bin, the bed, the weather sign | `generated/scenes/farm/` |
| The sheets that change with the season | `generated/data/seasons.json` |
| The farm's mode with its HUD and its weather | `generated/scenes/combat/combat_mode.tscn` |

Everything under `generated/` is made again when you regenerate. The files under `game/` are
written once and then left alone: change them freely.
