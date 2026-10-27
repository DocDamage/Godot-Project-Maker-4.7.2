# Changelog

## 1.5.0

**Compatibility with 1.0 to 1.4.** The save version stays 1 and older saves load. Two keys are
new and optional, each written only by a game that has the part: `calendar` (a save without
it loads on the first morning) and `friendship`. Everything else a farm keeps is in `flags`,
which every save has. No autoload is new. Three scripts are new in every project and at work
in none that does not ask for them: `world/calendar.gd` (nobody makes a calendar but a farm's
mode), `actors/schedule.gd` (at work only with a calendar) and `world/iso.gd` (answers a map
of squares with the arithmetic of squares). The folder `archetypes/farm/` is installed only in
a farm's project. A turn-based, action, metroidvania or arcade project that is seen from above
or from the side is built byte for byte as before: no `RECIPE_VERSION` moved, and the hashes
of the recipes have new keys (`iso`, `iso_v`, `iso_controls`) only in an isometric project. A
game without a calendar has the light and the saves it had. **Except** what *Quests, shops and
the bag* (at the end of this entry) changes for every project: `ui_recipes.gd` is at
`RECIPE_VERSION` 14 (the settings menu, the shop menu and the pause menu have new controls, so
the UI scenes are written again), `RpgStrings` has new keys (so `strings.csv` gains rows; the
rows a user translated are kept), and a save may have eight more optional keys
(`tracked_quest`, `shops`, `pending_items`, `worn_data`, `skill_ranks`, `skill_points`,
`achievements`, `counters`), each written only when it holds something.

**What an older game can notice**, all of it inert unless a farm or an isometric project uses
it: `RpgInteraction.before` (a Callable, unset by default: asked before a target is interacted
with, and when it answers true the target's own `interact` is not called; only the farmer sets
it); `RpgShopDefinition.closed_reason()` ("" for every shop but a farm's;
`RpgUiController.open_shop` shows a non-empty one as a toast and does not open the shop);
`RpgNpc.schedule()` (null for an NPC without one); `RpgActor.look()`, `map_node()`,
`map_cell()` and `cell_ahead()`; `RpgDayNight.weather_tint` (a static `Color`, white);
`RpgWorldMapMenu` lists no *World* row for a plan file that holds nothing but a farm's plan;
`RpgSchedule.override` (a static Callable, unset by default: who can put a person somewhere
else for a day; `pick` and `resolve` do not ask it, `entry_in_force` does); the condition
atoms `birthday:<id>`, `festival`, `festival_tomorrow` and `event:<kind>` (false, not unknown,
in every game without a farm's festivals: `RpgCondition` finds them through a meta of the game
state that only `RpgFarmEvents` sets); the condition atoms `courting:<id>`, `engaged:<id>` and
`spouse:<id>` (false in every game without a farm's marriage: they read flags only a farm
writes).

**A fix that changes what every game with a dialogue shows.** `ui/dialogue_box.gd`: the panel
of the dialogue box grows **upward** (`grow_vertical = GROW_DIRECTION_BEGIN`, set in `_ready`
on the node `%Panel`). It stands on the bottom edge of the screen with room for a line of text;
a line with choices needs more, and the panel took that room downward, under the screen: the
second choice of a line was cut off, in every kind of game and at every size of text (seen in
the picture of *Stone isle*, whose text is 16 px; with 8 px the second of two choices was cut
too). A line without choices is where it was. The scene `dialogue_box.tscn` is the one the
recipe always wrote: no `RECIPE_VERSION` moved, and a project gets the fix with the runtime.

**A fix of the Credits screen (T17.29).** `ui/credits_menu.gd`, `pack_lines`: a pack whose
author is known was written `tr("UI_CREDITS_BY") % [title, author]`; where no translation has
the key (the validator, a test: `tr` gives the key back) that was a runtime error, *not all
arguments converted*, first met when a real farming pack named its author in its documentation
file. The English text of `RpgStrings` stands in for a missing translation, and a translation
without two `%s` gives "Name — Author". A game whose packs named their authors shows the same
line as before.

**A farm's ground, pond and cave in the builder (after T17.30).** Nothing of the runtime
changes. The builder: `lib/plain_ground.gd` (new, in every project, inert without the plan
file's `farm.ground`, which only a farm seen from above has) gives a farm's maps the plain
ground tile rpggen measured instead of the sheet's first tile (`farm_map_recipe`
`RECIPE_VERSION` 5, `added_maps_recipe` 2; `starter_map_recipe` has the key `plain` in its
hash only in such a farm, so every other project's hash is what it was);
`recipes/farm/cave_rock.gd` (new, a farm's folder) lays the packs' rock over a cave's drawn
rock; a cave's root sets `RpgMapRoot.ambient_override` (darker than an interior's light) and
an enemy of a cave drawn much smaller than the farmer gets a `scale` in the map.

**Packs of other shapes in the builder (T17.30).** Nothing of the runtime changes. The builder:
`MapGeo.tile_unit` measures an isometric project by its diamond whatever tile sets of squares
its packs also have (*Lords Of Pain*'s effects made a tile set of 16 px, and the action RPG's
enemies, its followers' leash and its smoke steps were scaled to 16 px on diamonds of 128);
a project seen from above, or an isometric one without such a set, gets the unit it got. An
enemy of the action RPG stands on its feet where its sheet says how wide they are (the facet
`feet`, as the player since T17.29: a skeleton drawn in a frame as wide as its swing could not
reach the player); `arpg/enemy_recipes.gd` is at `RECIPE_VERSION` 3, so the enemies of every
action RPG are built again once, the same scenes where no enemy has the facet. `error_codes.gd`
has the three new codes.

**A fix of the action RPG's shots: they fly on the ground.** The player's arrows and the
enemies' shots flew at the middle of the shooter's body and hurt a hurtbox they overlapped;
seen from above or on diamonds the screen's y is depth and height at once, so an arrow passed
over an enemy shorter than half the player (*Lords Of Pain*'s slime) and an enemy's shot over
a player taller than it by as much. `RpgProjectile.set_on_ground(lift)`, called by
`RpgPlayerCombat.fire_arrow` and `RpgEnemyShoot.fire`: the shot starts at the shooter's feet and
flies there; it hurts the first body of the other team whose footprint its way crosses
(`RpgHurtbox.ground_rect()`: around the feet of the hurtbox's holder, as wide as its shape and as
deep as it is wide, whatever its height), walked in steps of its radius so a fast arrow does
not jump over a narrow body; its masks 9 and 10 are off (walls, mask 1, still stop it, at the
height of the feet); its picture is drawn `lift` above when it is loosed (the middle of the
shooter's body) and comes down evenly to the ground at the end of its range (`drawn_lift()`),
with a small shadow on the ground. New and inert elsewhere: `RpgHurtbox.GROUP` (every hurtbox
joins `rpg_hurtboxes` in `_ready`), `RpgProjectile.on_ground`, `lift`, `drawn_lift()`,
`targets()` and `first_on_path()`. A shot that nobody puts on the ground (the metroidvania's
shooter and the guardian's rock, seen from the side, where height is height) flies and hits as
before. No recipe changes what it builds and no `RECIPE_VERSION` moved. The smoke step
`player_bow_shoots` shoots a second enemy, made 2/5 of the player's height, and looks at the
arrow every frame while it waits (it read the player's last shot once afterwards, when an
arrow that had hit was already freed, and said the bow fired no arrow).

**Real farming packs in the builder (T17.29).** Nothing of the runtime changes but the line
above. The builder: `ActorBuild.set_feet` makes an actor's feet as wide as the facet `feet`
says, where a sheet says it (a character drawn 14 px wide in frames of 32 walked through no
door of a 16 px map with feet of 0.6 of its frame); every actor without the facet is built
as before. `FarmBuild.bed_asset` and `bin_asset` take a pack's bed or bin only when its frame
is at most three tiles wide and four high (*Farm RPG*'s `Beds.png`, a sheet of thirty beds,
filled the farmhouse). The farm's smoke step `season_turns` passes when every crop grows all
the year (a pack of two crops: nothing can wither). No `RECIPE_VERSION` moved: the inputs of
the recipes that read the facet have it in their hash only where an asset has it.

**The calendar.**

* **`RpgCalendar`** (`world/calendar.gd`): the minute of the day, the day of the season, the
  season and the year. A day runs from 6:00 to 2:00 of the night; a game minute is `minute_s`
  real seconds (0.7: a day is 14 minutes); a season has `days_per_season` days (28, or 14 or
  7). Time stands still while the game is paused (every menu), in a dialogue, in a cutscene, in
  a battle and while the map changes, and indoors with `stops_indoors`. Signals:
  `minute_passed`, `hour_passed`, `day_ended`, `day_began`, `season_changed`. `end_day()` ends
  the day (sleeping; the clock calls it at 2:00). What happens overnight is added with
  `on_night(priority, callable)` and runs in the order of the priorities (`NIGHT_CROPS`,
  `NIGHT_ANIMALS`, `NIGHT_SHOP`, `NIGHT_WEATHER`) before `day_ended` is emitted, so a night is
  the same every time. It is not an autoload: a mode makes it with `RpgCalendar.ensure()` (a
  child of GameState) and everybody finds it with `RpgCalendar.current()`, which is null in
  every game without one.
* `RpgDayNight` takes its hour from the calendar when the game has one whose `drives_light`
  is on (`RpgDayNight.current_hour`), and the outdoor maps follow it whatever the *Day and
  night* setting says. Without a calendar the cycle runs on the play time as before.
* **Schedules** (`actors/schedule.gd`, `RpgSchedule`). A child `Schedule` of an NPC with
  `entries`: from which `hour`, on which `days` of the week, in which `weather`, on which
  `map`, at which `place` (a marker made by `RpgSchedule.make_place`, a `Marker2D` in the group
  `rpg_place`) or `cell`. `resolve(hour, weekday, weather)` gives the entry in force: the last
  whose hour has come among those of the day and the weather, an entry with a weather before
  one without. When its map is entered the NPC is put where the calendar says it is; one whose
  place is on another map is away (hidden, not in the way, not talkable). When an hour passes
  on the map that is shown it walks to its new place along the map's navigation
  (`NavigationServer2D.map_get_path`), to the nearest door when the place is on another map,
  and from the nearest door when it comes back; on a map without navigation it fades out, is
  moved and fades in (`fade_s`). `RpgSchedule.set_weather` tells every schedule the weather of
  the day; `RpgSchedule.source` gives a schedule without entries those of its `person`.

**The farm (`archetypes/farm/`, a seventh kind).**

* **The mode.** `RpgFarmMode` is the farm's mode (`SceneRouter.combat`; it has no encounters):
  it asks for the calendar and gives it `days_per_season` (28) and `minute_s` (0.7), which the
  mode's recipe sets from `starter_map.days_per_season` (7, 14, 28) and `starter_map.day_length`
  (`short`, `normal`, `long`: 0.5, 0.7 or 1.0 seconds a game minute); it makes the farmer's
  `RpgEnergy` and `RpgHotbar`, knows the five tools (`tool_for`) and what an item restores when
  it is eaten (`food_energy`, `eat`), runs the night of the fields (`NIGHT_CROPS`), asks for
  the friendships, and has the parts below as children (`day_end`, `weather`, `seasons`,
  `forage`, `fishing`, `animals`). It gives the pause menu its People page each time the menu
  opens. Neither the energy nor the watering can is filled by the morning: sleeping fills the
  one, water the other.
* **The farmer.** `RpgFarmer` extends `RpgActor`, the top-down player: `cell()`,
  `tile_ahead()` (and the static `ahead_of`, `step_of`), a frame on the ground at the tile
  ahead (the child `TileFrame`, on a map that has a field), and `use_held()`: a ripe crop
  ahead is harvested whatever is held, a tool works, a seed is planted in tilled soil, food is
  eaten. `give_held(target)`: `interact` on a person while an item that can be given is held
  (`is_gift`: not a tool, not a bag of seeds) gives it; when nothing is given the farmer talks.
  New input actions: `use`, `next_item`, `prev_item`, `hotbar_1` to `hotbar_10`. A tool's use
  shows the sheet's animation of its name (`hoe`, `water`, `sickle`, `axe`, `rod`), else
  `attack`, else the tool's icon over the hands (`ToolIcon`). At zero energy the farmer walks
  at half its speed and no tool works. `fishing` keeps the farmer where it stands while a line
  is out.
* **Tools.** `RpgFarmTool` (an item id, an energy cost, a use time, the cell states it acts
  on, what it clears, the sound of a use) and the five in `tools/`: `RpgFarmHoe` (`hoe`: tills
  ground), `RpgFarmWateringCan` (`watering_can`: waters soil, holds 20 cells' worth, is filled
  at a `water` tile for no energy), `RpgFarmSickle` (`sickle`: a ripe crop, a withered one,
  grass), `RpgFarmAxe` (`farm_axe`: a stump, a branch) and `RpgFarmRod` (`fishing_rod`: a
  cast). A use that changes nothing costs nothing.
* `RpgHotbar`: the first ten stacks of the inventory, one of them held (`held`, `select`,
  `next`, `prev`, `item_at`, `qty_at`, `held_item`, `hold_item`; the signal `changed`).
  `RpgEnergy`: `value`, `max_energy` (100), `spend`, `restore`, `fill`, `is_exhausted`; the
  signal `changed`.
* **The field.** `RpgField`, a node of a farm map: the state of every worked cell as data
  (`cells`), painted on the map's `Soil` layer, with the crops as `RpgCrop` scenes among the
  Y-sorted entities. What can be tilled is the bool custom data `tillable` of a tile, and
  `water` fills the can. `till`, `water`, `water_all`, `plant`, `harvest`, `remove_crop`,
  `clear_obstacle`, `state_of` (`ground`, `soil`, `crop`, `ripe`, `withered`), `is_watered`,
  `crop_at`, `grown_at`; the signals `changed`, `harvested` and `cleared(cell, what)`. A night
  (`RpgField.grow`, `night_all`): a watered crop grows a day, an unwatered one does not, soil
  dries, a crop that does not grow in the season that begins withers, and bare soil is ground
  again after three dry nights. A field grows whether its map is shown or not.
* `RpgCropData`: the crops of `game/data/crops.json` (the user's; a crop only
  `generated/data/crops.json` has is added). `crop`, `crop_of_seed`, `crop_of_produce`, `days`,
  `stages`, `regrow`, `grows_in`, `of_season`, and the static `stage_of` and `is_ripe`.
* **Water.** `RpgWaterSource` (`water_source.gd`): the pond or the well of a farm, a solid
  thing that fills the watering can with `interact` (`fill_can`); `use` with the can held fills
  it at a tile whose custom data `water` is true. Its `kind` says whether there are fish.
* **Money.** `RpgShippingBin` (`shipping_bin.gd`, a solid thing of a map): `interact` while a
  thing with a price is held puts the whole held stack into it, `interact` with a tool or
  nothing in the hand takes the last stack back out. What is in it is in the flags, so the
  static `contents`, `count`, `put`, `take_back`, `price_of` and `sell_all` need no node: the
  night sells the bin wherever the farmer is, each thing at its item's `value`.
* **The end of a day.** `RpgDayEnd` (`day_end.gd`, the mode's child `DayEnd`,
  `RpgDayEnd.current()`): its night listener (`NIGHT_SHOP`) sells the bin; `sleep()` ends the
  day once, and the morning after it the energy is full, the game is saved into the autosave
  slot and into the slot the player last saved to or loaded from by hand (`chosen_slot()`; a
  game without one is offered the save screen), whatever the autosave setting says, and the
  farmer stands at the bed. A day the clock ends at 2:00 is passing out: half the energy
  (`PASS_OUT_ENERGY`), a tenth of the money gone (`PASS_OUT_MONEY`) unless `pass_out_loss` is
  off (`RpgFarmMode.pass_out_loss`), awake at the bed of the game on whatever map it is,
  saved. A day ended by `end_day()` from elsewhere is neither: rested, nothing saved. Signals
  `woke(how)` (`slept`, `passed_out`, `ended`) and `summary_opened`.
* `RpgBed` (`bed.gd`): `interact` sleeps. The first bed a game sees and every bed slept in is
  where the farmer wakes (`RpgBed.home`; `wake_offset`, `wake_facing`, `footprint`).
* `RpgDaySummary` (`ui/day_summary.gd`): what the night sold, what each thing earned and the
  total, over the paused game, once, and only after a night that sold something; `confirm`,
  `interact`, `cancel` or its button closes it.
* **The shop.** `RpgFarmShop` (`farm_shop.gd`, an `RpgShopDefinition`): `opens`, `closes`,
  `closed_weekday` and `is_open()`, `open_at`, `hours_text()`; its offer is its `stock`, then
  the seeds of the crops that grow in the season of the day (`seasonal`), then what
  `RpgFarmShop.add_stock_source(callable)` adds (the callable takes the season's name and
  returns rows `{item_id, price}`); a tool the farmer has is not offered again. A row that
  names `deliver` (a callable `func(item_id, qty) -> String`) is paid for and delivered
  instead of being put into the bag (`buy`): the animals' rows are such rows.
* **Friendship** (`friendship.gd`, `RpgFriendship`): points a person, ten hearts of 250.
  `talk(id)` gives 20 once a day; `gift(id, item_id)` gives by taste (80 loved, 45 liked, 20
  otherwise, -20 disliked) and is taken twice a week; the calendar's `day_began` resets both
  counters. It reads `game/data/people.json` (the people, their tastes and their schedules),
  counts a talk when the player interacts with the NPC of a person, and is found with
  `RpgFriendship.current()` (made by `ensure()`, a child of GameState). The dialogue condition
  `friendship:<id>>=N` (hearts) is false in a game without friendships. `RpgPeoplePage`
  (`ui/people_page.gd`): who was met, their hearts, and their taste for the items that were
  given to them.
* **The weather** (`weather.gd`, `RpgFarmWeather`, the mode's child `Weather`): `sun`, `rain`,
  a `storm` in summer, `snow` in winter. The weather of a day follows from the game's seed
  (drawn once a game) and the number of the day (`weather_of(seed, index, days_per_season)`),
  so it is the same before and after a save; the first day is fair. It is decided at
  `NIGHT_WEATHER` and in force from `day_began`; a new game and a loaded game take theirs when
  their map is entered. `today`, `forecast()`, `is_wet()`, `keeps_animals_in()`, the signal
  `changed(kind)`, and the debug hooks `force(kind)` and `force_tomorrow(kind)`. A wet day
  waters every tilled cell of every field in the morning (`water_fields`), what is tilled
  later in the day at once, and once more before the crops grow; it tells the schedules
  `"rain"`. `enabled` is false until the mode's scene sets it: a mode made by code, and the
  smoke run, have fair weather unless a day is forced.
* `RpgWeatherOverlay` (`weather_overlay.gd`): what falls over the screen on an outdoor map, on
  a CanvasLayer (2) of the weather: a strip of cells repeated over the screen (`fall`), twice
  over for a storm without a picture, or drawn snow (`flakes`). The outdoor light is
  multiplied by `RpgDayNight.weather_tint`; interiors and a map's own ambient are not touched.
  `RpgWeatherSign` (`weather_sign.gd`): `interact` shows tomorrow's weather as a toast.
* **The seasons.** `RpgFarmSeasons` (`seasons.gd`, the mode's child `Seasons`): on entering an
  outdoor map and on `season_changed` it replaces the textures that
  `generated/data/seasons.json` names by those of the season: the atlas sources of the tile
  sets, `Sprite2D.texture`, the frames of `AnimatedSprite2D` (`apply(map, season)`). It plays
  the music of the season on outdoor maps (`music_spring` to `music_winter`; a season without
  its own plays the first that is filled) and `music_night` from 20:00, in the place of the
  map's own music; a game with none of the slots keeps that.
* **Foraging.** `RpgForage` (`forage.gd`, the mode's child `Forage`): every morning things of
  the season lie at some of the places of a map (its markers `Forage/Spot<n>`; for a farm map
  without markers the cells `spots` of `generated/data/forage.json`) and are picked up with
  `interact` (`RpgForagePickup`, made by `refresh` among the entities of the map). What lies
  where is not stored: `forage_of(entries, seed, day, season, places)` derives it from the
  seed of the game (the weather's), the map (`map_seed`), the index of the day and the season,
  45 in a hundred places and always at least one. The table is `game/data/forage.json`, then
  what only `generated/data/forage.json` has (`things`, `fish`, `energy_of`).
* **Fishing.** `RpgFarmRod` (3 energy a cast) casts at a tile whose custom data `water` is
  true; `RpgFishing` (`fishing.gd`, the mode's child `Fishing`) does the rest: `cast(field,
  cell)` (false with a toast at a well), a wait of 1 to 4 seconds of the running game that
  follows from the seed and the number of the cast (`wait_of`), the bite (`bit`, the sound
  `sfx_bite` when the game has such a slot), then the bar (`RpgFishingBar`,
  `ui/fishing_bar.gd`, on a layer of its own): `mark`, `zone`, `meter`, the zone rising while
  `use` is held; `caught(item)` when the meter is full, `lost(why)` when it is empty, when the
  line is pulled in, when nothing bites, when the bag is full and when a new day or another
  map ends the cast. A cast passes 10 minutes of the calendar and the bar 20 more. `fish_for`
  chooses among the fish of the table that bite in the season, at the time of day (`time_of`)
  and in the water. `advance(delta)` and `button` are for tests.
* **Maps of a kind** (T17.23: the forest and the beach a farm can add). A map says what kind
  of place it is with the metadata `farm_kind` (`RpgForage.KIND_META`, `map_kind(map)`), and a
  thing to forage may name the kinds it lies on (`maps` in `forage.json`): on a map whose kind
  has things of its own only those lie, elsewhere the things that name no kind
  (`RpgForage.things_for(entries, kind)`). A map without an `RpgWaterSource` says what its
  water is with the metadata `farm_water` (`RpgFishing.WATER_META`: `sea` on a beach), and the
  fish whose `water` names it bite there; only a well takes no cast (it was: only a pond takes
  one). What was picked up is kept by map, as before. Nothing of this is at work on a map that
  has neither metadata: the farm's own map is what it was.
* **Fighting** (T17.24: a farm with *Combat*, or a cave). `RpgFarmFight` (`fight.gd`, the
  mode's child `Fight`; it does nothing unless the mode's `fights` is true, which only the
  recipe of a farm that fights sets): when a map is entered it gives the farmer an
  `RpgHealth` (the hit points of the game's player stats), an `RpgHurtbox` (layer 9) and an
  `RpgFarmBlade` (`blade.gd`, an `RpgHitbox` on layer 7 that adds the `attack` modifiers of
  the item swung), made at run time so that the player scene of a farm that does not fight is
  what it was. `RpgFarmer.use_held` swings the weapon `farm_sword` when it is held
  (`RpgFarmFight.swing`, no energy; `RpgFarmer.show_use` shows it as a tool's use is shown),
  and the shop sells it through a stock source. The enemies of a cave are the action RPG's
  (`archetypes/arpg/`, installed in a farm that fights and in no other); one called
  `farm_map_<n>_enemy_<m>` that is defeated leaves one of the things of a cave (forage entries
  with `maps: ["cave"]`) as an `RpgPickup`, and every morning their flags `defeated` are
  cleared and the farmer's hit points are full. At 0 hit points the farmer lies down
  (`begin_down`) and the day ends as at 2:00: `RpgDayEnd.pass_out()` (new) ends it at any hour,
  the night is `PASSED_OUT`, and `knocked_out` says it was a defeat (its toast says so). The
  HUD has a health bar (`%HealthBar`, only in the scene of a farm that fights;
  `RpgFarmHud.refresh_health`, `RpgFarmFight.health_changed`). Texts in `cave_strings.gd`
  (`RpgFarmCaveStrings`), added to `strings.tsv` only for a farm that fights. Nothing new is
  saved but the flags.
* **Animals.** `RpgAnimalHouse` is a part of the mode (its child `Animals`; it does nothing in
  a farm without an animal house). The herd is data in the flags (a row an animal with its
  kind, name, house, stall, colour variant, friendship, `fed`, `petted` and the product it has
  `ready`; and which troughs are full), so the night works on animals whose map is not shown.
  `herd()`, `animal(id)`, `of_house(house)`, `friendship(id)`, `hearts(id)`,
  `trough_full(house)` are static; `room_in`, `can_buy`, `buy`, `fill_trough`, `feed_with`,
  `pet`, `take_product`, `touch`, `product_for`, `product_price`, `night`, `is_outside`,
  `is_night`, `populate`, `show_room`, `show_yard`, `node_of`, `shown` and the signal `changed`
  are the node's. One portion of the feed in the trough of a house feeds every animal of it
  for the day; petting gives 15 points once a day; in the night (`NIGHT_ANIMALS`) a fed animal
  gets its product and 5 points and an unfed one loses 20; from five hearts (of ten, 100
  points each) the product is the kind's `large` item. Animals are out in their yard from 6:00
  to 18:00 unless `RpgFarmWeather.keeps_animals_in()`, else in their stalls; the nodes of a
  map are made from the data when it is entered and when the hour or the weather changes the
  place. Cut grass is hay in a farm with animals (`RpgField.cleared`).
* `RpgFarmAnimal` extends `RpgActor` (layer 5: found by `interact`, walked through): the node
  of one animal, which wanders a rectangle (`roam`) or cells of a layer of diamonds
  (`roam_cells`), sleeps (the `sleep` animation when the sheet has one) and is petted and
  relieved of its product by `interact`. `RpgFarmTrough` (a `StaticBody2D`, made at
  `Markers/Trough` by `make`) takes the held feed on `interact`; `RpgAnimalProduct` (an
  `Area2D`) is what lies on the floor of a coop. `RpgAnimalData` reads
  `game/data/animals.json`, then `generated/data/animals.json` for the kinds and houses the
  first does not list.
* **The HUD.** `RpgFarmHud` (`ui/farm_hud.gd`): the time (in steps of ten minutes), the
  weekday, the day and the season, the weather (a word, or an icon of `weather_icons`) and the
  money at the top left, the energy and the hotbar at the bottom; it hides the basic HUD's
  line of money, and tells a harvest and what the shipping bin paid by a toast.
* **Sounds.** `RpgFarmSounds` (`sounds.gd`) plays the slots of the kind where the thing
  happens: `sfx_hoe` (a cell is tilled), `sfx_water` (the can waters or is filled; a cast),
  `sfx_plant`, `sfx_harvest` (a crop is picked by hand or with the sickle, the sickle cuts, a
  thing is foraged, a fish is landed), `sfx_animal` (an animal is petted, a trough is filled),
  `sfx_rooster` (a morning) and `sfx_sell` (the morning's summary). The axe has no slot. A
  slot without a sound is silent.
* **What a farm saves.** In `flags`: `farm` (`energy`, `held`, `water`, `save_slot`),
  `farm_field` (one key a field: its worked cells), `farm_bin`, `farm_bed`, `farm_weather`
  (the seed), `farm_forage` (what was picked today), `farm_fishing` (the number of casts) and
  `farm_animals` (`herd`, `trough`). Beside them the two optional keys `calendar` and
  `friendship`.
* **Texts.** The farm's keys begin with `FARM_` (the weather, the forecast, the date of the
  HUD, a harvest, a sale, the can, fishing, foraging, the troughs); the names of its maps are
  `MAP_FARM`, `MAP_FARM_HOUSE`, `MAP_FARM_COOP` and `MAP_FARM_BARN`.
* **The project tools.** The door check counts the farm of a farm's plan (`farm.map` in
  `rpggen/world_plan.json`) among the maps of the world: a door of it that leads to a spawn
  point the village does not have is `VAL-028` (a warning that *Repair the world* mends), not
  `VAL-017`.
* **The builder.** `recipes/farm/room_recipe.gd` draws `generated/tilesets/farm_room.tres`, a
  floor of boards and a plastered wall; the farmhouse and the animal houses of a project
  without interior tiles are painted with it, not with the grass and the hedge of the maps
  outside, and no season changes it. This is for new maps: a map that exists is never built
  again.

* **A thing the user's file takes away stays away.** `RpgCropData`, `RpgAnimalData` (its
  `animals`) and `RpgForage` (`forage` and `fish`) read the user's file and then what only the
  planned file has, so a crop, a kind, a fish or a thing whose entry was deleted came back. An
  entry `{"id": "<id>", "removed": true}` in the user's file now takes the id away: nothing
  is added for it, and no later entry of that id is (`removed`, the ids). `RpgFriendship`
  reads `people.json` alone, so a deleted person was always gone; an entry with the mark is
  nobody there too. The arcade kinds' `stages.json` keeps its rule.
* **Every tool is heard.** `tools/axe.gd` plays `sfx_hoe` when it clears a stump or a branch
  (it was silent: the farm has no slot for an axe alone). The sickle plays `sfx_harvest`
  whatever it cuts, the rod `sfx_water` for its cast and `sfx_harvest` for a fish, as before;
  `sounds.gd` has the rule.
* **Festivals and birthdays** (T17.25). `events.gd`, **`RpgFarmEvents`**: a child `Events` of
  the farm's mode, at work only when the mode's `festivals` is true (the option
  `starter_map.festivals`; the mode's recipe sets it); otherwise `RpgFarmEvents.current()` is
  null and nothing below happens. It reads `game/data/events.json` (`user_path`, which the
  mode names from its `data_dir`) and, for the ids that file does not list,
  `generated/data/events.json`; `{"id": ..., "removed": true}` takes one away.
  * `today()`, `tomorrow()`, `events_on(day, season, year)`, `festival()`, `is_festival()`,
    `festival_tomorrow()`, `has_kind(kind)`, `season_rows(season, year)`. A day a shorter
    season no longer has is folded into it week by week (`day_in`), so a festival stays on
    its day of the week.
  * **A festival day**: `RpgFarmShop.day_off` (a static Callable, unset by default) closes
    every farm shop for the day, and `closed_reason()` says why; `closed_all_day()` is new.
    `RpgSchedule.override` sends everybody to the event's `place` from `from` to `to`, each to
    the spot of it their own schedule names. `festival_began(event)` is emitted in the morning
    and `festival_ended(event)` in the night (`RpgCalendar.NIGHT_SHOP + 50`). The things of
    the day are made on the event's map when it is entered and are in no saved scene
    (`festival_thing.gd`, `RpgFestivalThing`: an egg, a table; drawn, walked over, found by
    `interact`), at the markers the event names, or round its `place` on a map without them.
  * **What there is to do**: `find_egg(spot)`, `count_fish()` (also on `RpgFishing.caught`),
    `use_table(held)` (a contest is judged, a dish is brought), `give_prize(event)`;
    `found()`, `count()`, `is_done()`. A produce contest is judged on what the bin sold this
    season: `RpgShippingBin.shipped()` and `shipped_best()`, kept by `sell_all` under
    `flags.farm_bin.shipped`.
  * **Birthdays**: `birthday_of(id)`, `is_birthday(id)`, `birthdays_on(day, season)`,
    `birthday_text(id)`; from the person's entry of `people.json`, else from
    `generated/data/people.json`. `RpgFriendship.gift` asks `birthday_gift_open(id)`: the
    first gift of the day gives `birthday_points(taste)` (`BIRTHDAY_FACTOR`, 5, times the
    points of a loved, a liked or a politely taken gift; a disliked one takes what it always
    takes) and is none of the week's two. `RpgPeoplePage.detail_text` names the day.
  * **`add_event({kind, season, day, year, ...})`** adds an event at run time, kept in the
    flags and shown on the calendar; the people gather for it and the shop is closed as on a
    festival. `remove_event(id)`, `added()`. This is what a wedding is (T17.26).
  * **The calendar**: `ui/calendar_page.gd`, `RpgCalendarPage` (the weeks of a season, today,
    the festival and the birthdays in their colours, a list of the marked days, *Earlier* and
    *Later*). `RpgCalendarPage.add_to(menu)` gives the pause menu its *Calendar* button, as
    the People page has its own; `RpgFarmEvents.open_calendar()` shows the page over the paused
    game, which is what `wall_calendar.gd` (`RpgWallCalendar`, the calendar on the wall of the
    farmhouse) does on `interact`.
  * `RpgFarmWeather.forecast_text()` has a second line on the day before a festival
    (`tomorrow_text()`). The state is in `flags.farm_events` (`added`, `today`,
    `birthday_gifts`): the save has no new key.
* **Marriage** (T17.26). `marriage.gd`, **`RpgMarriage`**: a child `Marriage` of the mode,
  which does nothing unless `enabled` (the mode's new `courting`, from the option
  `starter_map.courtable` above 0; the mode's recipe sets it); otherwise
  `RpgMarriage.current()` (a meta of the game state) is null.
  * Who can be courted is `courtable` of a person's entry of `people.json` (the planned file's
    for an entry without the key). `RpgFriendship.cap_of`, a new static Callable (unset by
    default: everybody has ten hearts), holds such a person at eight hearts until courted.
    `RpgFriendship.gift` hands a **bouquet** or a **pendant** to `RpgMarriage.give`: from
    eight hearts the bouquet begins the courting; at ten the pendant to the one courted is a
    yes, and the wedding is `RpgFarmEvents.add_event` of kind `wedding` three days on (the
    next day that is no festival). The wedding's night makes the spouse.
  * The spouse's day wins over the person's own (`RpgSchedule.override`, chained after the
    events' own, so a festival wins over both): at home in the farmhouse from 6:00 on the cell
    beside the one the farmer wakes on, on its own spot of the square from 12:00 to 17:00 on
    Tuesday and Thursday when dry, at home again, asleep (on no map) from 22:00. In the
    farmhouse it is an NPC made at run time of the person's scene (`Spouse`, with a schedule
    and a line of its own); its NPC of the village is away while it is at home.
  * The morning's help (`help_on`, `do_help`): water part of the farm's field (`water_part`,
    the dry cells with a crop first, at most 8, about half), fill every empty trough
    (`feed_animals`), or leave a produce of the season on a table of the farmhouse
    (`spouse_table.gd`, **`RpgSpouseTable`**, taken with `interact`). The first morning after
    the wedding waters. The night takes `DECAY_POINTS` (2) from everybody who was met and not
    talked to that day.
  * The shop sells the bouquet and the pendant (a stock source) until the farmer is married.
    The condition atoms `courting:<id>`, `engaged:<id>` and `spouse:<id>` (`RpgCondition`,
    read from `flags.farm_marriage`: false in every game without a farm's marriage).
  * `RpgFarmEvents.with_files` (true by default): false, the events of the files and the
    birthdays are left out, which is how a farm with marriage and without festivals has its
    wedding. The builder: `recipes/farm/marriage_recipe.gd` seeds `game/data/items/bouquet.tres`
    and `pendant.tres` once; a farmhouse planned since T17.26 has two beds (`Bed`, `Bed2`)
    that wake the farmer on one cell. The state is in `flags.farm_marriage` (`courting`,
    `engaged`, `wedding`, `spouse`, `wed`, `home`, `help`, `table`): the save has no new key.

**The isometric view.**

* **The tile set** (the builder only). A project whose config says `projection: isometric`
  gets `generated/tilesets/iso.tres` from the tile set recipe through
  `builder/lib/iso_tileset.gd`: Godot's isometric tile shape with the layout *diamond down* (a
  cell (x, y), x east and y south, has its middle at `((x - y + 1) * w / 2, (x + y + 1) * h /
  2)`), the tile size the diamond of the pack (180 x 104, never assumed 2:1), sources that are
  atlas pictures of single tiles in `generated/iso_atlases/`, and for every tile its texture
  origin (the middle of its diamond from the middle of its atlas cell), the custom data
  `asset_id`, `footstep`, `tillable` and `water`, and a collision polygon that is its diamond
  (a wall) or a profile laid on the diamond. A tile turned four ways is four tiles: an
  alternative tile of Godot cannot show another picture. `IsoTileset.new(catalog)` answers the
  map recipes: `tile_for(asset_id, turn)`, `piece_for(pack | tag | role, joins)`,
  `paint(layer, cell, asset_id, turn)`, `cell_to_local`, `stand(sprite, facets, at)`. The
  merge rules are the ones of every tile set: no source loses its id and no tile its atlas
  coords.
* `CatalogReader.assets()` (and with it `assets_by_role` and every lookup built on them)
  leaves out what was drawn for the other view: nothing whose `projection` is `isometric` in a
  project that is seen from above or from the side, no sheet of square tiles in an isometric
  one. No catalog before 1.5 has such an asset. `asset(id)` still finds any asset by its id.
* **`RpgIso`** (`world/iso.gd`): the arithmetic of the view, the same as
  `rpggen/core/iso_math.py` (one table of cases tests both): `cell_to_screen`,
  `screen_to_cell`, `grid_point`, `depth` (the sort key of a cell: the y of its middle),
  `diamond`, `neighbours` and `step` (n the upper right, e the lower right, s the lower left, w
  the upper left), `unit` (the length of one step in px), `side_of`, `faced_side` and
  `faced_cell`, `pad_vector` and `pad_side`, `bounds`, and `sort_keys` / `in_front` for a thing
  that stands on several cells. And what asks a map, for squares and diamonds alike:
  `footprint_of(map)` (zero on squares), `map_unit`, `cell_at`, `cell_position`, `cell_ahead`,
  `move_vector`, `reach_dir`, `used_rect`, `controls()`.
* On an isometric map `RpgUtil.map_tile_px(map)` is `RpgIso.unit` of its diamond (34 for 60 x
  34), not the width of the diamond: what a reach, a spacing or the step counter of the random
  encounters means by a tile there. On every other map it is what it was.
* **Actors.** On an isometric map the cell ahead of an actor (`RpgActor.cell_ahead()`) is the
  neighbour it last walked towards, else the one its facing names (up n, right e, down s, left
  w). `RpgPlayerInput.pad(input)`: on an isometric map whose project says `iso_controls: grid`
  (the project setting `rpg/iso_controls`, written by the builder for an isometric project
  only) the four directions of the pad follow the axes of the diamond, and `RpgInteraction`
  reaches towards the neighbour the player faces. With the default (`screen`) and on every map
  of squares the pad is the screen. The facing of an actor is still one of four, by where it
  goes on the screen; a sheet with diagonal animations shows them along the axes.
* `RpgMapRoot.used_rect_px()` (the limits of the camera) is the rectangle around the painted
  diamonds of an isometric map. `RpgMinimapData.cell_at` finds the cell of a position by the
  diamond for a minimap whose texture has the metadata `isometric`: the minimap of an
  isometric map is its plan from above, a pixel a cell, like every other.
* **The builder.** `builder/lib/map_geo.gd` (`MapGeo`) is the seam between a plan of cells and
  the px of a map: `center`, `foot`, `bottom`, `step`, `cell_shape`, `cells_outline`,
  `gate_position`, `building_info`, `building_position`, `find_tile`, `tile_of_asset`,
  `nth_tile_with_role`, `other_tiles`, `wall_tile`, `paint_joined` / `paint_runs` /
  `fill_joined`, `paint_sides`, `paint_walls`, `border_collision`, `add_exit_door`, and the
  static `tile_unit(ctx)`. The starter map, the interiors, the field, the areas of a world, the
  doors and gates of a world plan, the actors and the object scenes take every position, shape
  and tile through it; for a project seen from above it calls what they called before, with
  the same numbers. For `projection: isometric` the maps are painted on `iso.tres`: ground from
  the flat `GROUND` tiles (patches of the others by the seed), roads, water and walls from the
  pieces whose `joins` fit (`IsoTileset.nearest_piece`: the piece with the fewest wrong sides
  and one note a map when none fits exactly; the plain tile when none names its sides), a wall
  that rises on the Y-sorted `Props` layer, an invisible diamond a cell where the packs have no
  wall. Roads, and the two far sides of a wall, are laid in the place of the ground of their
  cells (`road_layer`): laid over it, the earth under a tile showed as a dark kerb along every
  path and a footing along the far walls. An isometric object stands on the middle of its
  diamond and blocks the cells it stands on; one of several cells is drawn in two halves that
  sort apart (`Sprite`, `SpriteRight`, the root `y_sort_enabled`); the `Entrance` of a
  building is a band along its south side and its `ExitSpawn` the middle of the door cell.
* The text of the menus of an isometric project follows the config's `base_tile_size`, not the
  diamond (`theme_recipe.gd`), and the player's camera is drawn back when fewer than eight
  diamonds would fit across the screen (`MapGeo.camera_zoom`: 180 px diamonds on a screen of
  640 px are shown at 0.44).
* **The farm on diamonds.** The plan of a farm is a grid of cells in both views and a save has
  the same shape. Nothing of a farm seen from above changes.
  * `RpgField` asks its `Soil` layer for cells and places, so a layer of diamonds carries
    over. `footprint()` (the diamond of its cells, zero on squares) and `foot_of(cell)` (where
    a thing of a cell stands: a px above the lower edge of a square, the middle of a diamond;
    crops are put there). `tile_px` is `RpgIso.unit` of the diamond on an isometric layer.
  * `RpgFarmer.tile_ahead()` is the neighbour the farmer faces on diamonds
    (`RpgIso.faced_cell`), with either setting of `iso_controls`. `diamond()`, and
    `face_cell(cell)`, which turns the farmer to a cell beside its own. The `TileFrame` takes
    the shape of the field's diamond and keeps its width on the screen when the camera is
    drawn back.
  * `RpgAnimalHouse` puts the trough, the animals and what they leave on the middle of their
    cells; `RpgFarmTrough.make`, `RpgForagePickup.make` and `RpgAnimalProduct.make` take the
    diamond of the map as a last, optional argument.
  * `farm_iso.gd` (`RpgFarmIso`): the diamond of a cell as points and as a shape, `box` /
    `box_faces` (a box on a diamond: three `Polygon2D`), `halves` / `add_face` / `add_box` (a
    thing of several cells drawn in two halves that sort apart), `clip_x`, and `grid_of` /
    `world_of`.
  * The builder: `farm_soil.tres` of an isometric farm is an isometric tile set of the
    project's footprint whose five tiles are drawn as diamonds, with the flat isometric tile a
    pack tagged `soil` or `watered` as its source 1 or 2 when it has one; a building of the
    packs stands on the plan's footprint with its door before the plan's door cell, and the
    cells of the footprint it does not stand on are blocked (`<Building>Ground`), else the
    building is a drawn box with a roof; fences join the pieces beside them; the bin, the bed,
    the well, trees and scenery are isometric pictures of the packs (one cell, by the same
    words) or boxes on their diamond; what blocks blocks its diamond.
* **The race on diamonds.** A race is driven on the flat plan of its track whatever the view:
  the position, the heading and the velocity of a car, the barriers, the checkpoints, the
  waypoints, the pickups and the weapons are the plan's, and `RpgCarPhysics`, `RpgRace`,
  `RpgRival`, `RpgRaceCheckpoint` and `RpgTrackSurfaces` are unchanged (a rival drives the
  same lap in both views, step for step). Only what is drawn is elsewhere.
  * `RpgRaceView` (`archetypes/racing/race_view.gd`): the child `View` of a track that is
    painted on diamonds; a track seen from above has none. `footprint`, `cell_px`, `origin`;
    `to_screen`, `to_plan`, `screen_vector`, `plan_vector`, `screen_heading`, `plan_heading`,
    `scale_px`, `depth`, `screen_rect`, `screen_corners`; `RpgRaceView.of(node)` finds it from
    anything of the track (null from above).
  * `RpgCar`: `view()`, `shown_position()`, `shown_heading()`, `shown_forward()`: where the
    car is drawn and which way it points on the screen. On a track with a view its `Visual` is
    moved to that place, takes the row of diamonds as its `z_index`, and shows the heading as
    it is seen; with `absolute_steering` the stick is a direction of the screen.
  * `RpgHeadingSprite` is given the heading on the screen. A car in eight headings as eight
    files (`car_N.png` to `car_NW.png`, N up on the screen, then clockwise) shows `SE` when it
    heads east in the plan; a sheet drawn from straight above is shown the same way and looks
    flat; one picture is turned.
  * `RpgRaceCamera` follows where the car is drawn (`target_position()`) and leads it the way
    it moves on the screen; `base_zoom` (1 by default) is the zoom over a car that stands.
    `RpgRacePickup` and `RpgRaceWeapon` keep their place in the plan and draw themselves where
    the view has it (`shown_position()`).
  * The builder: `recipes/racing/iso_track.gd` builds the track of an isometric project (the
    ground on `iso.tres`, the road from the road pieces of the packs along the loop or drawn,
    the marks, the walls and the scenery on the diamonds; the barriers, the cars, the pickups
    and the race in the plan); `RaceBuild.scale_for` chooses the scale for the picture of the
    car.
* **The editor tools on diamonds** (T17.27; `addons/rpg_project_tools/`, which has no changelog
  of its own). `RpgIso.cell_shape(footprint)` is new: the shape of one cell around its middle,
  a `ConvexPolygonShape2D` of `RpgIso.diamond`, which is the shape the builder gives a cell.
  The tools ask a map through `RpgIso` and do something else only when it answers with a
  diamond; on a map of squares they do what they did.
  * The Assets dock (`dock/placement.gd`): what is dragged or double-clicked into an isometric
    map stands on the middle of the diamond under the mouse (`RpgIso.cell_at`,
    `RpgIso.cell_position`), among the Y-sorted entities and with the entity id a map of squares
    gives. An object of several diamonds stands with its nearest cell there (the `stands_on` of
    its scene). Every *Snap* choice but *Off* means the diamond. Nothing is dropped to a floor.
    The plan of a placement says its `cell` and `cells`; the status line says the diamond.
  * The world tools: a trigger area is its diamond, a gate has a `Shape` child of its diamond
    and a `size` of one step, an encounter zone with nothing selected is the outline of 6 x 6
    diamonds. A tile is `RpgIso.unit` of the map being edited, not 16.
  * The world repair and the validator's *Fix* (`tools/world_repair.gd`): the actions of an
    isometric map carry its diamond (`iso`), and a door added there has the diamond's shape on
    the middle of its cell, as `MapGeo.add_exit_door` builds one.
  * **Three old faults of the Assets dock mended, on every map** (squares and diamonds, seen
    from above, from the side or isometric; `dock/placement.gd` only). Ctrl+Z after a double
    click no longer logs `No path can be resolved between the nodes ... (not inside tree)` for
    each property it sets back: an undo runs its operations in the order they were added, and
    `Placement.apply` now adds the one that takes the node out of the map (or moves a dropped
    one back) after the properties. A double click is saved as an instance of its scene
    (`instance=ExtResource(...)`, only the position and the entity id), as a drop is: it is
    instantiated with `PackedScene.GEN_EDIT_STATE_INSTANCE` (`Placement.instance_for_edit`);
    before, the map kept `type=` and a copy of the scene root's script, collision mask and
    metadata, which a rebuilt object scene did not reach. A second copy of one asset is named
    as the editor names one (`treeoak2`, `house3`; `Placement.free_name`, in the plan as `name`
    and `old_name`) instead of `@StaticBody2D@20523`, and keeps its name through undo and redo.
    A map placed in before keeps what it has: a double-clicked node saved with `type=` stays a
    copy until it is placed again.
* **Imported isometric maps** (T17.28; the builder only, no script of the runtime changed). An
  isometric Tiled map of an isometric project is built by `recipes/imported_maps_recipe.gd` on
  `iso.tres`: its first layer in its place is the `Ground`, every other one a `TileMapLayer`
  with `y_sort_enabled` and `collision_enabled` under `YSorted` before `Entities` (moved by
  Tiled's offset), each cell the tile of its picture at the picture's own turn; the cells of
  the map's walls are blocked by an unseen `ImportedWalls` body of diamonds; spawns, doors and
  signs stand on the middle of their diamonds (doors as `MapGeo.add_exit_door` builds them). A
  map of the other view is not built. `MapGeo.block_cells(root, cells, name)` is new
  (`border_collision` now calls it; its scenes are what they were). The tile set may hold
  pictures with `maps_only` (an object of a pack, a picture of its samples, painted by such a
  map): `IsoTileset.maps_only(id)` is true for them and `pieces` and `plain_tiles` leave them
  out, so no planned map paints them. The runtime finds such a map isometric as it finds any
  (`RpgIso.footprint_of`: its `Ground` has the tile set of diamonds). The hash of the recipe
  has a new key (`iso_v`) only in an isometric project.

**The smoke runner and the smoke steps.**

* `debug/smoke_runner.gd`: a smoke run that is given a name (`--rpg-smoke-run=<id>`, the
  generator's run id) saves into `user://smoke_saves_<id>`, emptied before the first step and
  removed after the last (`save_dir()`, `save_dir_for(args)`, `clear_saves(dir)`). Godot keeps
  `user://` by the project's name, so two smoke runs of projects of one name at one time read
  and replaced each other's saves. A run without a name saves where every run did. Nothing of
  a game that is played changes: the runner is inert without `--rpg-smoke`.
* `builder/smoke/*.gd`: every steps script asks the runner for the folder.
  `builder/smoke/smoke_map.gd` is what a step asks the map instead of the screen (`cells`,
  `pad_toward`, `walk_toward`): the steps `collision_blocks`, `enter_building`,
  `exit_building`, `decor_blocks`, `walk_to_field`, `return_from_field`, `world_doors` and
  `encounter_start` walk to a place through it, and on a map of squares they hold the key they
  always held. The steps that talk to somebody or open something stand as far from it as the
  player's interaction reaches (9 px with tiles of 16 px, as before); the action RPG's steps
  ask the bodies how far a swing reaches, not the tile; the racing steps ask the car where it
  is drawn in the three places that are about the picture.
* `keys_and_switches` puts its locked gate and its lever where nothing else answers
  `interact` (the place it always used, when that is free): in a farm's village somebody may be
  at home exactly there, and the farmer talked to them and the gate stayed shut.
* The farm's own sequence (`smoke_steps_farm.gd`) runs the shared top-down steps in the
  village between its own and ends with `save_and_load`: the game is saved, a night passes and
  the field, the money, the bag, the energy, a friendship and the herd are changed, the game
  is loaded, and the field is compared cell by cell with the date and the rest.
* `builder/validate.gd`: the copy of a map for the round trip carries the process's id.

**Real isometric packs in the builder (T17.22).** Nothing of the runtime changes: these are
the builder's, and what they make is read by the scripts that were there.

* **Walls from segments.** A pack whose walls are pieces along one side of a diamond (the
  facet `edge`) and no whole tiles has the edge of its maps laid from one wall's set
  (`MapGeo.paint_edge_walls`, `IsoTileset.edge_piece(wall set or tag, side)`): on every cell of
  the edge the piece for the side that looks out of the map, the way out left open, the
  lowest plain wall of the packs (a farm: its fence). A corner cell has a piece for each of
  its two sides, on two layers: `Props`, which is sorted with the actors, and `GroundDetails`
  for a far side or `Overhead` for the second near side of the corner nearest the camera. The
  cells block by the tiles' own diamonds. A pack with whole wall tiles is laid as before.
* **A house of pieces** (`builder/lib/iso_house.gd`). When no pack drew a whole building for
  the view and the packs have a wall for all four sides and a wall with a door, the village's
  house is the object `rpggen.iso_house` (`generated/scenes/objects/rpggen__iso_house.tscn`):
  walls along the sides of a footprint of two by two cells, the door above the plan's door
  cell, windows by the seed, a roof tile over every cell a storey up (as far as the wall rises
  above its diamond on a far side). It is a `StaticBody2D` like every building: `Footprint`,
  `Entrance`, `ExitSpawn`, the metadata `iso` and `stands_on`, and `kit`; its pieces are
  sprites under two nodes `Left` and `Right` that sort as the two halves of an isometric
  building do. A farm's house, coop and barn are put together the same way on the footprints
  of its plan, and a yard is fenced with the packs' fence segments.
* **The camera's zoom** of an isometric game with large diamonds is the nearest at which a
  step of the grid is a whole number of screen px each way (`MapGeo.whole_step_zoom`: 0.5
  where it was 0.444 on diamonds of 180 x 104). At another zoom slivers of the tiles' block
  sides showed as thin dark dashes along the diamonds' edges.
* **Round corners in an isometric race.** A race whose corner pieces all turn in a quarter
  circle (the facet `corner`) is planned with round corners (`stages.corners`): the surface
  cells of a corner (`RpgTrackSurfaces`) are a quarter ring and the waypoint of the cell lies
  on the middle of it. `car_math`, `car_physics`, `race.gd` and `rival.gd` are untouched; a
  race seen from above, a race on square pieces and a race that is stored are what they were.

**Maps painted with terrains (T17.31).** One script is new in every project and at work only
where a TileSet has terrains: `world/terrain.gd` (`RpgTerrain`), which paints an area
(`TileMapLayer.set_cells_terrain_connect`) or a path (`set_cells_terrain_path`) with a terrain
and then chooses again among the tiles of the same terrain and peering bits by the cell and a
seed, weighted by `TileData.probability` (Godot's own choice draws from the global random
generator and differs from run to run). `RpgField` has two exported properties,
`soil_terrain` and `watered_terrain` (-1 by default: the field paints its one tile as before),
which a farm's recipe sets when its pack has a terrain of tilled or watered soil: a tilled cell
is then painted with the terrain and joins the soil round it, and a cell that is ground again
is taken out of the terrain and its neighbours painted again; `shows_soil(cell, watered)`
answers whether the `Soil` layer shows soil there (the smoke steps of the farm ask it). A
field without the properties is what it was.

The builder: `lib/terrain_paint.gd` (new: which terrain of a tile set paints roads, water,
sand, patches and the ground of a field, by the `surface`, `over` and `shape` rpggen read, a
sheet that says it is indoors last) and `MapGeo.terrain_for`, `fill_ground`, `paint_patches`,
`plain_others`, `ground_of`, `seed_for`; `paint_joined`, `paint_runs`, `paint_sides` and
`fill_joined` paint with a terrain where the tile set has one (a terrain drawn over nothing on
diamonds goes on `GroundDetails`). The starter map, the second map and the areas, the
interiors, the farm (its plot of a terrain of the ground edged where it meets the grass, its
pond with a shore), its added maps (a beach's sand and sea) and the isometric tracks use them;
each such recipe adds `terrain_v` to its hash only when a tile set of the project has terrain
sets, so the hash of every other project is what it was. A map that exists is never painted
again; the run says so (TILE-015) when it would have been painted otherwise. The tile set
recipe gives the variants of a terrain's middle their probability and the tiles of an
isometric tile set their terrain (`ISO_PEERING_BITS`: the grid's sides and corners as Godot's
neighbours of a diamond). The field's soil tile set (`farm_soil.tres`) has the tiles of the
packs' terrains of soil and a sixth tile of ground that can be tilled and shows nothing, only
in a farm that has them.

**Corners and roofs of a house of pieces (after T17.30).** Nothing of the runtime changes.

* **Posts.** A tile with the facet `post` (`nw`, `ne`, `es`, `sw`: the corner of its diamond
  it stands on) is a post (`IsoTileset.post_sets`, `post_piece`; `post_set_for`: of the sets
  no higher than the wall, the one of the wall's colour). The edge of a map laid from wall segments has one at each corner of the
  map where two of its sides meet, a `Sprite2D` under `YSorted/EdgePosts` sorted a pixel after
  the walls of its cell (the nearest one at `z_index` 11, over the `Overhead` layer); a house
  of pieces has one at each corner of its footprint (parts of kind `post`, the far one after
  the far walls, the others after the near walls).
* **One roof.** A tile with the facet `roof` (`slope:n`, `hip:es`, `ridge:ew`, `peak`,
  `valley:nw`) and `roof_rise` is a piece of a roof; the kit of a house carries `roofs`
  ({shape: asset id}, one family) and `roof_rise`, and `IsoHouse.roof_plan` lays them: slopes
  rising from every side to a ridge, the quarters of a hipped roof at its ends, each ring of
  cells a slope's rise higher, a gable or a pyramid where two or four sides are as near; when
  the packs have no slope or quarter for a cell, a gable along every row of the longer way;
  else a roof tile a cell, as before. A house's kit without posts or roof pieces is what it was.
* `MapGeo.EDGE_VERSION` is 2: the maps of an isometric project with wall segments are built
  again; every other project's hash is what it was.

**The ground of a side-view room as its terrain (T17.32).** Nothing of the runtime changes;
`RpgTerrain` (T17.31) paints it.

* `SideKit.find` gives the kit a `terrain` (`{set, terrain}`): the terrain set of the shape
  `side` read from the ground's sheet (`SideKit.side_terrain`; `TerrainPaint.SIDE_SHAPE`, which
  no map seen from above takes). `RoomsRecipe.paint` paints the `#` cells of a room with it
  (`RpgTerrain.paint_area`, seed `RoomsRecipe.TERRAIN_SEED`) and `StageRecipe.paint_floor` a
  stage's floor; a kit without one paints `top` and `fill` as before. `RECIPE_VERSION` of the
  rooms recipe is 2 and of the stage recipe 4: a room or a stage that exists is never built
  again, so only new ones are painted so.
* `Parallax.layers` takes one parallax set (`parallax_set:<folder>`): of several, the one
  whose folder shares the most with the ground's sheet (in its pack first, else the first by
  name); layers without a set are taken as before.

**Stacking, tiles that move and shadows (Gridwright's kits, 2026-10-26).** Nothing of the
runtime changes. A project whose packs have none of it is built as before. Every new key is
written only for a piece that has it, and the hashes change only where it is.

* The tile set `iso` has two more custom data layers, `lift` (int) and `stack` (string)
  (`IsoTileset.custom_data`). A tile whose definition has `frames` and `fps` is animated
  across the cells after its own (`IsoTileset.animate`, from `tileset_recipe.gd`).
* `tools/height_layers.gd` (rpg_project_tools, new): a level's height layers are TileMapLayers
  drawn `height` px higher (`position.y = -height`) with `y_sort_origin = height` and the meta
  `rpg_height`, under the level's YSorted node. `top_at` is a cell's stack (a layer's height
  and its tile's `lift`), and `suggested` the next layer. The dock's *World tools* add them
  (*Height layer at*, **Suggest**, **Add height layer**, with undo).
* `dock/placement.gd`: `plan` has `raise`, the top of the stack on the cell of an isometric
  map. `apply` puts an instance with a raise into a new Node2D `Raised` (meta `rpg_height`) on
  the cell's middle, and the instance `raise` px higher in it, with undo. With no stack (every
  map before) it is applied as before.
* `ActorBuild.add_shadow`: a Sprite2D `Shadow` (35 % opacity) under the picture of an actor,
  an enemy or an object whose catalog entry has `shadow`. An object's shadow lies at the
  object's offset (it is drawn with the object's anchor), an actor's is centred on its feet.
* `ObjectEntries` in an assets-only project: a thing that moves is an entry with
  `frames_path` and `animation`, and its scene has an AnimatedSprite2D `Sprite` that plays it.
  A PROJECTILE and an EFFECT are entries too. A piece of a stack that is only painted
  (`on_storey`, `on_wall`, `overlay`) is none. A game's entries are as before.
* `CatalogReader.asset` finds an asset through an index by id (made again when the list is
  another or grew; a miss scans the list as before). What it answers is unchanged; a build of a
  catalog of 100,000 assets no longer spends 40 s on each actor scene.
* The validator (VAL-014): a `Shadow` is not checked. An EFFECT or a PROJECTILE stands on its
  middle. In an isometric project a figure's drawn feet may lie up to half a diamond below its
  origin (the ground point under the figure's middle, as Gridwright draws it).

**Quests, shops, the bag, skill trees and achievements (2026-10-26).** Designs taken from the Godot kits the user keeps
beside the packs (ideas only: nothing of theirs is copied or shipped), written for this
runtime. Every quest, shop and item made before behaves as it did unless it uses a new key;
what every game can notice is the quest tracker, the Buy back tab and what a full bag does
with a reward.

* **Quests.** `RpgQuestDefinition` has `requires` (a condition: `quest_start` refuses the
  quest until it holds), `auto_start` (the quest starts by itself when `requires` holds: a
  chain) and `fail_when` (a condition that fails the quest under way). A stage may have
  `turn_in` (it does not move on by itself; while its condition holds the quest is *ready to
  turn in*) and `take` ([{item_id, qty}], taken from the bag when the stage finishes; without
  them it does not finish). `progress_of(condition, state)` counts the atoms that count
  (`item:<id>>=N`, `gold>=N`, `level>=N`, `var:<name>>=N` or `>N`, `friendship:<id>>=N`), live:
  dropping logs lowers the count. `problems()` checks the new keys; `to_dict` writes them only
  when set; `reached()` stops at a stage that waits.
* `GameState.quests[id]` may be `"failed"` (`QUEST_FAILED`): not active, listed with the
  finished ones, never completed or started again, no rewards. New: `quest_is_failed`,
  `quest_available`, `quest_ready`, `quest_current_stage`, `quest_progress`, `quest_fail`,
  `quest_turn_in`, `tracked_quest` and `track_quest`. The first quest started while none is
  tracked is tracked; when it ends the tracker moves to the first quest still under way.
  `quest_complete` refuses a failed quest.
* Conditions `quest_failed:<id>`, `quest_available:<id>`, `quest_ready:<id>`; dialogue events
  `quest_turn_in:<id>`, `quest_fail:<id>`, `track_quest:<id>` (all checked by the dock).
* **The tracker.** `ui/quest_tracker.gd` (`RpgQuestTracker`, drawn in code like the minimap;
  boot adds it on a layer `QuestTrackerLayer` under the minimap): the tracked quest's title,
  what its stage asks with the counts ("Bring logs (Log 5/8)") and *Ready to turn in*. Hidden
  with no quest tracked, no map, or the new setting `RpgSettings.quest_tracker` off (the
  settings menu's *Quest tracker*, a new CheckButton `%QuestTracker`; older scenes have none).
* The journal: a quest's button says *[Tracked]* or *(failed)*; confirming an active quest
  tracks it (again: tracks nothing); the current stage shows its counts and *Ready to turn in*.
* The dock's Quests tab edits `requires`, `auto_start`, `fail_when`, a stage's `turn_in` and
  what it takes (`QuestTab.parse_items`).
* **Shops.** `RpgShopDefinition`: a stock row may have `qty` (how many until the shop
  restocks); `restock_minutes` (of play) and `restock_each_day` (with a calendar) say when it
  does; `funds` is the gold it buys with (-1, the default, never runs out; what you pay adds
  to it); `wares` (an `RpgLootTable`) is rolled at each restock for more rows at the items'
  value; `buyback` (true by default) keeps the last `BUYBACK_MAX` (8) sales, to buy back for
  what the shop paid until it restocks. `status`, `period`, `left_of`, `funds_of`, `is_ware`,
  `offered_now`, `buyback_rows`, `buy_back`; new refusals `SOLD_OUT` and `SHOP_CANNOT_PAY`.
  The state lives in `GameState.shops` (saved as `shops`). `RpgFarmShop` is unchanged.
* The shop menu: rows of limited stock say *2 left* or *Sold out*, the quantity stops at what is
  left, the gold line names the shop's gold when it has a purse, and a **Buy back** tab
  (`%BuybackTab`, hidden for a shop with `buyback` false; a scene without one works as before).
* **The bag.** `RpgInventory`: `transact(giving, taking)` and `fits(giving, taking)` (all or
  nothing, tried on a quiet `trial()` copy first); a slot may carry `data` (`add_with`,
  `take_one`, `data_at`; such a slot holds one and never stacks; `remove` takes plain stacks
  first; `to_array` and `load_array` keep it).
* **Nothing given is lost.** `GameState.give_items(rows)`: what does not fit waits in
  `pending_items` (saved) with a toast, and comes as soon as there is room (`deliver_pending`,
  on `item_removed` and `game_loaded`). Quest rewards, the event `give_item`, chests and the
  turn-based battle's drops use it; before, what did not fit was dropped.
* **Wear.** `RpgItemDefinition.durability` (0, the default: it never wears). A worn weapon
  wears by one with each blow that lands (the turn-based attack and skill hits, the real-time
  hitbox), worn armour and the accessory with each hit taken (`wear_from_hit`). At its
  durability the piece breaks and is gone (a toast). Its wear is the data of its slot in the bag
  and `GameState.worn_data` when worn (saved); `equip` and `unequip` carry it. `wear`,
  `wear_stats`, `wear_of`; the status screen shows *Wear 1/3*.
* **Sets.** `RpgItemDefinition.set_id` and `data/item_set.gd` (`RpgItemSet`,
  `game/data/item_sets/<id>.tres`: `bonuses` = [{pieces, modifiers}]). `equipped_modifiers`
  adds the bonuses of the sets worn (so `equip_preview` counts them); `item_set_of`,
  `worn_sets`; the status screen lists the sets worn.
* New text keys: `UI_QUEST_TRACKER`, `UI_QUEST_FAILED`, `UI_QUEST_READY`,
  `UI_QUEST_FAILED_MARK`, `UI_QUEST_TRACKED`, `UI_BUYBACK`,
  `UI_NOTHING_TO_BUY_BACK`, `UI_SOLD_OUT`, `UI_SHOP_LEFT`, `UI_SHOP_FUNDS`,
  `UI_SHOP_CANNOT_PAY`, `UI_ITEM_WAITING`, `UI_ITEM_DELIVERED`, `UI_ITEM_BROKE`, `UI_WEAR`,
  `UI_SET_BONUS`.
* **Skill trees.** `data/skill_tree.gd` (`RpgSkillTree`, `game/data/skill_trees/<id>.tres`):
  `skills` on a grid (`cell` [column, row]) with `max_rank`, `cost`, `requires` ({skill id:
  rank}), `bonuses` (modifiers, once a rank) and `skill` (a battle skill learned with the first
  rank); `points_per_row` opens row r once r times as many points are spent in the rows above it;
  `reset_gold` (0 free, -1 never). `learn_problem` and `unlearn_problem` say why not (`NO_POINTS`,
  `MAX_RANK`, `NEEDS`, `ROW_LOCKED`, `NOT_LEARNED`, `NEEDED`: a rank another learned skill or a
  learned row needs is never unlearned, so points always add up); `problems()` (repeated ids or
  cells, unknown requirements, a requirement not on an earlier row).
* `GameState`: `skill_trees` (loaded at start), `skill_ranks`, `skill_points` (saved),
  `learn_skill`, `unlearn_skill`, `reset_skill_tree` (pays the gold, gives every point back),
  `give_skill_points`, `learned_modifiers` (added to `equipped_modifiers`, so every stat and the
  equip preview count them), `learned_battle_skills` (the turn-based battle offers them). A
  level gained gives `RpgNewGameData.skill_points_per_level` points (1), only in a game that has
  a tree.
* `ui/skill_tree_menu.gd` (`RpgSkillTreeMenu`, built in code): a tab per tree, the skills on
  their grid with lines from what they require (bright when met), the actor's points, the
  skill in focus (rank, what a rank gives, what it needs), Learn (or confirm the skill),
  Unlearn, Reset (with its price), a pager for the party. The pause menu has **Skills** (a new
  button `%Skills`, shown only in a game with a tree).
* **Achievements.** `data/achievement.gd` (`RpgAchievement`, `game/data/achievements/<id>.tres`):
  `when` (a condition), `secret`, `points`, `rewards` (as a quest's), `icon`. `GameState`:
  `achievement_defs`, `achievements` (unlocked, saved), `counters` (saved), `count(name, by)`,
  `note_defeat(enemy id)` (the action RPG, the metroidvania and a turn-based victory call it),
  `unlock_achievement`, `refresh_achievements` (on the events quests listen to, and when a
  counter moves), `achievement_points`. Counted by themselves in a game with achievements:
  `defeated`, `defeated:<enemy id>`, `items:<item id>` (items gained; gear moved and what a
  new game starts with are not) and `quests_done`. A game without achievements counts nothing.
  Unlocking shows a toast and gives the rewards (what does not fit waits).
* Conditions `count:<name>>=N` (also counted by `progress_of`) and `achievement:<id>`; dialogue
  events `count:<name>[:N]`, `unlock_achievement:<id>` and `give_skill_points:<actor>:N`.
* `ui/achievements_menu.gd` (`RpgAchievementsMenu`, built in code): unlocked and total, points,
  one row each (unlocked first, a locked one with its counts, a locked secret as "???"). The
  pause menu has **Achievements** (`%Achievements`, shown only in a game that has some).
* The validator: **VAL-034** (warning), what `problems()` of a quest, a skill tree or an
  achievement finds, and an item whose `set_id` names no set (`content_checks.gd`,
  `_check_game_data`).
* **The project tools** (`addons/rpg_project_tools/`): three more tabs of the dock, built like
  the Quests tab on `data_tab.gd` (a file row with New, Save, Reload and JSON export and import,
  one undo step a change). **Skills** (`skill_tree_tab.gd`): the tree's id, title, points per
  row and reset price, its skills in a list with a form (id, title, description, column, row,
  ranks, cost, `requires` as "blade 2, guard", bonuses as "attack +2" or "speed x1.1" lines, the
  battle skill it teaches) and a picture of the grid with the lines of the requirements; a
  skill named by a problem is marked. **Achievements** (`achievement_tab.gd`): id, title,
  description, the condition (checked as you type, the counters the game keeps listed under
  it), secret, points, rewards, the icon by its path, and a test with a pretend counter and
  gold. **Item sets** (`item_set_tab.gd`): id, title, bonuses as "2: defense +5, attack +1"
  lines, the items of game/data/items that name the set with Add and Remove (each saves the
  item's `set_id`) and the durability of the item picked. `RpgSkillTree`, `RpgAchievement` and
  `RpgItemSet` have `to_dict` / `from_dict`, and `RpgItemSet.problems()`; a skill on the cell
  of another names it ("skill 6 (swift) is on the cell of skill 4 (healing)").
* **The builder.** `recipes/progression_recipe.gd` (new, after `data_recipe`) seeds, once, what
  the feature `progression` (*Skills and achievements*) asks for: `skill_trees/adventurer.tres`
  in a turn-based game, an action RPG or a metroidvania, `achievements/<id>.tres` for what the
  game has (`errand` with the demo, `hunter` with combat, `seasoned` but on a farm, `savings`,
  and the secret `treasure` with the village chest), and `item_sets/traveler.tres` when
  `data_recipe` gave the starter weapon and armour `set_id` `traveler` (it does with the feature
  on and both seeded). A config without the key (every config before 1.5.0) gets none of it:
  the recipe writes nothing, and `data_recipe`'s hash has the new key `gear_set` only when the
  set is made. The translations recipe adds the seeded keys (`ProgressionRecipe.SEED_STRINGS`).
* More text keys: `UI_SKILLS`, `UI_SKILL_POINTS`, `UI_LEARN`, `UI_UNLEARN`, `UI_RESET`,
  `UI_RESET_COST`, `UI_RANK`, `UI_SKILL_NEEDS`, `UI_ROW_LOCKED`, `UI_ROW_LOCKED_SHORT`,
  `UI_NO_POINTS`, `UI_MAX_RANK`, `UI_SKILL_NEEDED`, `UI_SKILL_NOT_LEARNED`, `UI_SKILL_LEARNED`,
  `UI_NO_SKILL_TREES`, `UI_ACHIEVEMENTS`, `UI_ACHIEVEMENT_UNLOCKED`, `UI_ACHIEVEMENTS_TOTAL`,
  `UI_SECRET`, `UI_NO_ACHIEVEMENTS`.

### Finishing 1.5.0 (M18)

What an older game sees when it is regenerated (the runtime is copied on every regeneration);
each is inert where the game's data does not ask for it.

* **Repair** (T18.04): `RpgShopDefinition.repairs` (false by default), `REPAIR_SHARE` (0.5),
  `repair_cost`, `repair_rows(game)` (worn gear first, then the bag's) and `repair(game, i)`
  (all or nothing; the gold goes to the shop's purse); `RpgGameState.mend(actor, slot)` and
  `RpgInventory.mend_at(index)` take the wear off. The shop menu makes a **Repair** tab beside
  the others for a shop that repairs (the scene of an older game has none, so the script makes
  it); its rows read "Sword · Wear 5/40 — 3 G". New text keys `UI_REPAIR`,
  `UI_NOTHING_TO_REPAIR`, `UI_REPAIRED`.
* **The dock's Items and Shops tabs** (T18.02, T18.03): `RpgShopDefinition.to_dict`,
  `apply_dict`, `from_dict` (`RpgFarmShop` adds its hours), `row_problem` and
  `stock_problems`; `RpgItemDefinition.to_dict` and `from_dict` (an icon cut from a sheet is
  written as `{atlas, region}`). The validator's VAL-034 names a shop's row whose item has no
  file. `addons/rpg_project_tools/tools/strings_tsv.gd` reads `game/i18n/strings.tsv` and adds
  rows for new keys.
* **The starter shop** (T18.04), with the feature `progression` (on for a new project; a config
  without the key is built as before and `data_recipe`'s hash gains `starter_shop: 2` only when
  it applies): three potions that restock (each morning of a farm, every 10 minutes of play
  elsewhere), 300 gold of the shop's own, buying back, repairs; the starter weapon has a
  durability of 40.

## 1.4.0

(There is no 1.3.0 entry: release 1.3.0 changed the wizard only.)

**Compatibility with 1.0 to 1.3.** The save version stays 1 and older saves load. One key is
new and optional: `meta`, a section that the three slots and the autosave share, which holds
the high-score table of an arcade game and loads as an empty table everywhere else.
`rpggen/world_plan.json` may have a `stages` section. The folders `archetypes/arcade/`,
`archetypes/shmup/`, `archetypes/run_and_gun/` and `archetypes/racing/` are installed only in
projects of those kinds; a turn-based, action or metroidvania project has no new file from
them, and its TileSets, maps and scenes are unchanged.

**Two fixes that change what an older game shows** once it is regenerated:

* The **minimap** (`RpgMinimap`) was placed 120 px left of the screen and was never seen. It is
  in the top-right corner now. The *Minimap* setting turns it off.
* The screens that lie over the game (the member picker, the equip picker) were 0 by 0 px with
  their shade over nothing and their content hung from the top-left corner. They cover the
  screen now.

* **The arcade framework** (`archetypes/arcade/`), shared by the three kinds below:
  * `RpgArcadeMode` (the run: stages in order, the save between stages, `run_data()` and
    `restore_run_data()` for what a kind keeps of a run), `RpgArcadeStage`,
    `RpgArcadeStageSequence` (reads `game/data/stages.json`, then the stages of
    `generated/data/stages.json` that list does not have).
  * `RpgArcadeScroller` (moves the camera along one axis, stops for a blocking wave or a boss,
    `follow()` for a camera that is led), `RpgArcadeSpawner` and `RpgArcadeWave` (formations
    `line`, `column`, `v`, `circle`, `sine`; triggers `progress`, `time`, `after`).
  * `RpgArcadeLives`, `RpgArcadeScore` (a multiplier that grows without a hit),
    `RpgArcadeBoss` and `RpgArcadeBossPhase` (phases at a fraction of the health, a telegraph
    before every attack), `RpgArcadeBulletPool` (bullets that hit by distance; `wall_mask`,
    `life_s`), `RpgArcadeExplosion`.
  * `RpgArcadeStageClear` (the tally), `RpgArcadeContinueScreen`, `RpgArcadeHighScores` and the
    table on the title screen, `RpgArcadeHud`.
* **The shoot 'em up** (`archetypes/shmup/`): `RpgShmupMode`, `RpgShmupShip` (eight-way, a
  focus speed, a hurtbox of one point, banking frames), `RpgShmupWeapon` (`straight`, `spread`,
  `laser`, `homing`; levels 1 to 3), the bomb, enemy bullet patterns (`aimed`, `ring`, `fan`,
  `spiral`), the enemies `popcorn`, `turret`, `asteroid` and `carrier` over `RpgShmupEnemy`,
  power-ups, the boss, `RpgShmupHud` with side panels in a game that scrolls up. Actions:
  `shoot`, `bomb`, `focus`. The ship's weapon and its level go on to the next stage and are in
  the saved run (`RpgArcadeMode.weapon`, as `spread:2`).
* **The run and gun** (`archetypes/run_and_gun/`): `RpgSoldier` over the metroidvania's
  `RpgPlatformActor` (eight-way aim, crouch, aim lock, lives or health, `can_jump`), `RpgGun`
  and the weapons `machine_gun`, `spread`, `laser` and `flame`, the grenade, the weapon pickup
  on its carrier, the enemies `runner`, `sniper`, `turret`, `jumper` and `wall_cannon` over
  `RpgGunEnemy`, the bosses `wall`, `walker` and `flyer`, and `RpgGrapple` (a hook along the
  aim, a swing on a rope, a hoist). `RpgPlatformMath` gained `swing_step` and `swing_period`.
  Actions: `shoot`, `grenade`, `aim_lock`, `grapple`. The soldier's weapon goes on to the next
  stage and is in the saved run.
* **Racing** (`archetypes/racing/`): `RpgCar` on `RpgCarPhysics` (speed, a turn rate that falls
  with speed, grip by surface, drift, bumps, boost, parts), `RpgCarInput` (relative or absolute
  steering), `RpgHeadingSprite` (a sheet of headings, or one picture turned), `RpgRaceCamera`,
  `RpgTrackSurfaces`, `RpgRace` (countdown, checkpoints, laps, places, wrong way),
  `RpgRaceCheckpoint`, `RpgRival` (a driver with a skill on the player's physics), pickups and
  weapons (boost, missile, bomb, shield, parts), `RpgChampionship`, `RpgRaceResults`,
  `RpgRacingHud` and `RpgRaceMinimap`. Actions: `accelerate`, `brake`, `boost`, `fire`.
* **The smoke runner** (`debug/smoke_runner.gd`): a step may name the error code its failure
  is reported with (`code`); without one it is SMOKE-001 as before. At its end it stops the
  audio players until none is playing, not once: a sound that began in that moment was
  reported by Godot as a resource still in use at exit.
* **Sound slots** of the kinds (`sfx_shoot`, `sfx_explosion`, `sfx_powerup`, `sfx_bomb`,
  `sfx_grenade`, `sfx_weapon_pickup`, `sfx_grapple`, `sfx_skid`, `sfx_bump`, `sfx_pickup`,
  `sfx_lap`, `sfx_countdown`, and the music slots `music_stage`, `music_boss`, `music_race`,
  `music_results`); silent when empty.

## 1.2.0

**Compatibility with 1.0 and 1.1.** The save version stays 1 and older saves load. Three keys
are new and optional, written only when they hold something, so the save of a turn-based or
action game is what 1.1 wrote: `abilities`, `broken_cells` and `room_fog`. `rpggen/world_plan.json`
may have a `rooms` section. Top-down TileSets, maps and scenes are unchanged.

**Moved scripts.** The real-time combat set moved from `archetypes/arpg/` to `combat/realtime/`
with its uids: `damage_info.gd`, `hitbox.gd`, `hurtbox.gd`, `health.gd`, `projectile.gd`,
`state_machine.gd`, `pickup.gd`, `screen_feedback.gd`. Class names and behaviour are unchanged.
A script without a class name stays at each old path and extends the new one, so
`preload("res://addons/rpg_runtime/archetypes/arpg/hitbox.gd")` still works; **these shims go
away in 2.0**. A project that was open in the editor while it was regenerated needs *Project →
Reload Current Project* once. `RpgArpgMath` extends the new `RpgRealtimeMath`.

* **The metroidvania archetype** (`archetypes/metroidvania/`):
  * `RpgPlatformActor` (a `CharacterBody2D` moved by intents: `move_x`, `move_y`, `press_jump`,
    `release_jump`, `press_dash`; gravity, a variable jump, coyote time and a jump buffer,
    one-way platforms on layer 11, ladders, the wall slide), `RpgPlatformPlayer` (attack, hurt,
    hazards and the return to safe ground, interaction), `RpgPlatformInput`, `RpgPlatformMath`,
    `RpgSideTiles`.
  * `RpgAbilities` (the table: `double_jump`, `dash`, `wall_jump`, `high_jump`, `break_blocks`),
    `RpgAbilityPickup`, `RpgAbilityGate`; `GameState.grant`, `has_ability`, the signal
    `Events.ability_granted`; `RpgGate.required_ability` and the condition `ability:<id>`.
  * `RpgRoom` (an `RpgMapRoot` with exits, a camera of its own and `arrive(exit_id, carry)`),
    `RpgRoomExit`, `RpgSideCamera`, `RpgItemPickup`; `SceneRouter.go_to_room(map, exit_id,
    carry)` changes the room without a fade and keeps the player's speed.
  * `RpgSideNpc`, `RpgSideInteractable`; chests, signs, doors and spawn points have `side_view`.
  * `RpgSideEnemy` with `patrol`, `flyer` and `shooter`, and `RpgGuardian` (three phases, grants
    an ability, opens its room).
  * `RpgSaveStation` (`rest()`, `save_to(slot)`, `respawn_point(state)`), `RpgMetroidvaniaHud`,
    `RpgMetroidvaniaMode` (saving only at stations, an autosave on every room change, a defeated
    player returns to the last station).
* Shared code, for every archetype: `RpgAnimationDriver.resolve_side`, `has_side`, `play_side`
  (animations without a facing, mirrored for the other side); `RpgStatsComponent.holder`;
  `RpgUtil.beside`; `RpgDefeatPolicy.can_continue()`; `RpgUiController.open_menu(name, args)`;
  `RpgMinimapData.room_list`, `room_boxes`, `room_map` and the room mode of `RpgMinimap` and
  `RpgWorldMapMenu`; `GameState.visit_room`, `room_visited`, `remember_broken_cell`,
  `broken_cells_of`. A combat mode may have `save_at_stations`, `autosave_on_every_map` and
  `respawn_after_defeat()`; modes without them behave as before.
* New text keys: `UI_NEEDS_ABILITY`, `UI_SAVE_AT_STATION`, `MV_RESTED`, and
  `MV_ABILITY_<ID>_NAME`, `_DESC`, `_HINT` per ability.
* Builder: `recipes/metroidvania/` (player, objects, rooms, parallax, enemies, HUD), `lib/
  side_tileset.gd` and `lib/side_kit.gd`; the TileSet recipe adds the side-view physics layers
  only for this archetype; `validate.gd`, the map graph and the world repair know rooms and
  their exits (repair kind `exit`).

## 1.1.0

**Compatibility with 1.0.** The save version stays 1 and a 1.0 save loads. Every new key is
optional: a quest stage's `next`, `title` and `rewards`, the `sfx_step_<surface>` and custom
sound slots, `rpggen/surfaces.json`, `rpggen/audio_loops.json` and `rpggen/world_plan.json` (a
project without the file behaves as in 1.0). No script moved or was renamed. A scene made by 1.0
keeps working as it is: a shop scene without the Sell all button, a HUD scene without the
members' bars (they are added at run time), a starter map whose houses share one interior, and a
project with `field_1`. One behaviour changes: **music loops** (in 1.0 a track played once).

* Dialogue: `RpgDialogueRunner.event_refs(event)` and an optional `ids` argument of
  `event_problem` (unknown shop, quest and actor ids). New event `play_sound:<slot>`.
* Followers in the action RPG: `RpgFollowers` asks the combat mode to `customize_follower(node,
  member, index)` and leaves a follower whose meta `held` is true where it is (its place on the
  trail goes to meta `home`). `RpgAssist` (`archetypes/arpg/components/assist.gd`): the first two
  followers walk to an enemy within 3 tiles of the player and swing every 1.2 s with the
  member's attack, stay within 6 tiles, and are down for 5 s at 0 HP. `RpgArpgMode`
  signal `party_health_changed`; the HUD shows a bar per member.
* Sound: any slot named `music_<name>` or `sfx_<name>`; `RpgSoundBank.surface_of`,
  `has_step_surfaces`, `step_slot`; `RpgMovement.surface_at` (a tile's `footstep` custom data,
  else its asset's `surface:<name>` tag). Loop points: `RpgAudio.apply_loop(stream, {start_ms,
  end_ms})`, `loop_of(path)`; `play_music` applies the loop of `rpggen/audio_loops.json` (a WAV
  loops between both points; Ogg Vorbis and MP3 return to the start point from their end).
* Quests: `RpgQuestDefinition.next_of`, `edges`, `problems`, `reached(state)`, `to_dict`,
  `from_dict`; a stage may name its `next` stage (or `done`) and have `rewards`, given when its
  condition finishes it.
* Sequences: `RpgSequence.STEP_KINDS`, `step_kind`, `new_step`, `entity_problems`;
  `RpgSequenceRunner.sequence_from(commands)`, and while the editor's debugger is attached the
  message `rpg_sequence:run` plays the commands the dock's Cutscenes tab sends.
* World map: with `rpggen/world_plan.json` the first entry is **World** (`RpgWorldMapMenu.
  overview`: a box per area where the plan put it, lit when visited, a mark per door pair); an
  area is listed by its name. New text key `UI_WORLD_OVERVIEW`.
* Enemy definitions of recolour variants (the builder's enemy recipes): the variant's name and
  its source's stats times the variant's multipliers.
* Shops: `RpgShopMenu` rows have a quantity (`max_quantity`, `quantity_of`, `set_quantity`,
  `change_quantity`; `transact(item, qty)`), and a **Sell all** button (`sell_all()`).
  `RpgShopDefinition.buys` (categories, empty = all), `buys_category`, `sell_all_items`,
  `sell_all_value`, `sell_all`. New text keys: `UI_SHOP_QUANTITY_HINT`, `UI_SELL_ALL`,
  `UI_SELL_ALL_CONFIRM`, `UI_SOLD_ALL`. A shop resource and a shop scene made by 1.0 keep working.
* Builder: `interior_recipe` version 3 seeds one interior per house of the starter map;
  `second_map_recipe` version 3 builds the areas of a world plan (and `field_1` without one);
  `audio_bus_recipe` version 4 writes the surfaces and loops tables; `ui_recipes` version 13.

## 1.0.0

* First stable release. The runtime is unchanged in behavior from 0.3.0; the version number now
  matches rpggen 1.0.0, the diagnostic bundle and the Windows export preset that ship with it.
* Regenerating a project made with 0.x asks for confirmation once (`--accept-runtime-upgrade`
  or the dialog in the wizard) because the major version changed.
* Before the release (M11): the action-RPG **heavy attack** (`secondary_attack`: 1.75x damage,
  1.5x knockback, slower swing); chests built from a two-frame strip, sheet or an `open`
  animation show their open picture; the action-RPG HUD uses a nine-sliced UI bar from the pack
  when there is one and sits on the project theme's panel.
* Sound slots: a sound bank (`rpggen/sound_bank.json`), `RpgAudio.play`, `play_ui_slot` and
  `play_music_slot` (silent no-ops for an unset slot), sounds for pick-ups, hits, attacks,
  level-ups, saving, chests, doors, menus (cursor, confirm, cancel) and footsteps, the map music
  of the map root, the battle music and the title music. New events: `chest_opened`,
  `door_used` and `attack_started`.
* A game-over screen (`RpgGameOver`, `RpgDefeatPolicy` shared by both archetypes): continue from
  the newest save, try the map again or quit to the title; smoke runs skip it.
* Autosave: a fourth save slot 0 beside slots 1 to 3, written when a map is entered (never during
  a battle, dialogue or fade, and at most every 10 s), listed first in the load menu; the
  Settings menu can turn it off. Slot numbers 1 to 3 are unchanged, save version stays 1.
* A second outdoor map `field_1.tscn` behind a gap in the east wall of a new starter map; screen
  shake and hit-stop on a landed heavy attack (Settings > Screen shake); a key prompt over what the
  player can interact with; the game version on the title screen; the map and play time in the
  pause menu.
* Review follow-ups (M12): a save over a **damaged** slot file no longer replaces the last good
  backup with it (the backup is made only from a file that verifies, and the new save is moved
  into place by renaming it over the old one); four messages that bypassed translation (a damaged
  save, a save from a newer version, "cannot use that now" and the chest text) now use the keys
  `UI_SAVE_DAMAGED_LOADED_BACKUP`, `UI_SAVE_FROM_NEWER_VERSION`, `UI_CANNOT_USE_NOW`,
  `UI_CHEST_FOUND` and `UI_CHEST_EMPTY`. Projects made earlier fall back to the English text.
* Fixed while running M11 against Godot 4.7.2: the interact prompt shows `E`, not
  `E - Physical`; `RpgAudio` lets go of its streams when it leaves the tree.
* Save and load screens (M12): a slot reads "Slot 2 — Village · Lv 3 · 1:12 played · 12 Oct 14:05"
  (the map's name, level, play time and the local time of saving); the header gained the optional
  fields `saved_unix` and `map_name` (a translation key from the new `RpgMapRoot.display_name`
  export, default `MAP_<ID>`; a map without a translation shows its file name), so
  `save_version` stays 1 and older saves still read (they show no date). Saving over a used slot
  asks for confirmation with the focus on "No"; a 160x90 picture of the screen is kept beside the
  slot (`slot_N.png`, not when headless) and shown on its button; the slot loops use
  `SaveManager.SLOTS`. New keys: `UI_LV`, `UI_PLAYED`, `UI_OVERWRITE_SAVE`, `UI_YES`, `UI_NO` and
  `UI_MONTH_1` to `UI_MONTH_12`. Fixed: a toast that was dropped to make room no longer logs an
  error when its timer ends.
* Equipment (M12): `GameState.equipment` ({actor id: {weapon, armor, accessory}}, keyed by actor for
  party members), `equip`, `unequip`, `equipped_modifiers`, `stat_of` / `effective_stat` and
  `equip_preview`. Items of the categories WEAPON, ARMOR and ACCESSORY go to their slot; the old
  piece returns to the inventory. Both combat systems read attack, defense (and, turn-based,
  speed) through `get_stat` with the worn modifiers (`RpgBattleActor.stat`, the hitbox and the
  hurtbox); enemies wear nothing. The inventory menu has an Equip button and the status menu lists
  the slots; both open `RpgEquipPicker`, which shows the stat changes (green gain, red loss) of
  the focused choice before it is confirmed. The save has the optional key `equipment` (an older
  save loads with empty slots; `save_version` stays 1). New keys: `UI_EQUIP`, `UI_EQUIPMENT`,
  `UI_TAKE_OFF`, `UI_SLOT_WEAPON`, `UI_SLOT_ARMOR`, `UI_SLOT_ACCESSORY`, `UI_NO_CHANGE`,
  `UI_NOTHING_TO_EQUIP`, `UI_CANNOT_EQUIP` and `UI_MOVE_SPEED`.
* Party members (M12, turn-based): `GameState.join_party` / `leave_party` (at most `MAX_PARTY` = 4
  characters, the player included; a member is built from `game/data/actors/<id>.tres`),
  `party_ids`, `in_party`, `actor_definition` / `actor_name`, `give_experience_to`, `revive_party`
  and `heal_party_full`. Dialogue events `join_party:<id>` and `leave_party:<id>`, the condition
  `party:<id>`, and the new event `party_changed`. In battle every member acts (the controller
  already built the party from `GameState.party`; it now uses their names and art), experience is
  shared (`give_experience` now grants it to the whole party), and a fallen member stands up at
  1 HP after a victory or an escape; the defeat policy revives or heals the whole party. The
  battle UI marks whose turn it is (small text for a party of three or more), and the
  inventory menu asks on whom to use an item (`UI_USE_ON`). The status menu pages through the members with its own
  equipment. `heal_full` heals everyone. The party was already in the save. The action RPG has no
  followers in 1.0. New keys: `UI_PARTY_JOINED` and `UI_PARTY_LEFT`. New turn-based projects get the
  actor "Mira" (`companion.tres`) and a villager choice that brings her along.
* Imported maps (M12): the generator builds the Tiled and LDtk maps of a pack that the user ticks
  as `game/maps/imported/<pack>/<map>.tscn`, or as the starter map. No runtime script changed; the
  smoke steps that fight the demo's enemy pass with a note in a project whose starter map was
  imported.
* Quest journal (M12): `RpgQuestDefinition` (`game/data/quests/<id>.tres`: a title key, ordered
  `stages` [{id, description key, complete_when condition}] and `rewards` {gold, experience,
  items}). `GameState.quests[id]` holds the current stage id, or `"done"`, so saves are unchanged
  (and the older `set_quest:` / `quest:` still work on the same dictionary). `quest_start`,
  `quest_set_stage`, `quest_complete` (rewards once), `refresh_quests` (a stage whose
  `complete_when` holds moves on by itself, and the last one completes the quest; it runs on flag,
  item, gold, level-up, dialogue and load events) and `journal_ids`. Dialogue events
  `quest_start:<id>`, `quest_stage:<id>:<stage>` and `quest_complete:<id>`; conditions
  `quest_active:<id>`, `quest_done:<id>` and `quest_stage:<id>:<stage>`; a toast for every
  start, stage change and completion; new event `quest_changed`. The pause menu has a Journal
  button (`journal_menu.tscn`: Active and Completed tabs, the stages of the quest in focus).
  New keys: `UI_JOURNAL`, `UI_QUESTS_ACTIVE`, `UI_QUESTS_DONE`, `UI_NO_QUESTS_ACTIVE`,
  `UI_NO_QUESTS_DONE`, `UI_QUEST_NEW`, `UI_QUEST_UPDATED` and `UI_QUEST_DONE`. New projects get the
  quest "The villager's errand" (talk, open the chest if the map has one, tell the villager).
* Shops (M12): `RpgShopDefinition` (`game/data/shops/<id>.tres`: `stock` = [{item_id, price}] where
  a price below 0 means the item's `value`, and `sell_ratio`, default 0.5) with all-or-nothing
  `buy` / `sell` that return `""` or why they were refused (not enough gold, no room in the bag,
  not held, worthless; key and quest items are never bought). The dialogue event `open_shop:<id>`
  sends `Events.shop_requested`; `RpgUiController` opens `RpgShopMenu` (a new generated scene
  `shop_menu.tscn`) when the dialogue closes, with the game paused. The menu has Buy and Sell tabs,
  one button per item, the gold you have and the item's description, and one focus ring for the
  gamepad. `RpgInventory.room_for(item_id)`. New keys: `UI_SHOP`, `UI_BUY`, `UI_SELL`,
  `UI_GOLD_SHORT`, `UI_BOUGHT`, `UI_SOLD`, `UI_NOT_ENOUGH_GOLD`, `UI_NO_ROOM`, `UI_CANNOT_TRADE`,
  `UI_NOTHING_FOR_SALE` and `UI_NOTHING_TO_SELL`. New projects get a `village_shop` and a villager
  who offers it after the first talk.
* An item's `max_hp` modifier raises the cap everywhere (`RpgUtil.max_hp(stats)`: the status menu,
  both HUDs, healing items and heals, full refills, the level-up refill); wearing it does not heal,
  and taking it off pulls the current hp down to the smaller cap (never to 0). A `move_speed`
  modifier scales the player's walk (`RpgMovement.walk_speed()`; it is a factor on the base
  `move_speed`, so the dodge is scaled too). New event `equipment_changed(actor_id, slot)`, which
  the action-RPG HUD listens to; it was emitted before the signal existed, so nobody saw it.
* Sequences (M12): `RpgSequence` (`game/data/sequences/<id>.tres`, or kept inside a map by a
  trigger) holds commands that `RpgSequenceRunner` (created by boot under SceneRouter as
  `SequenceRunner`) plays in fixed physics steps: `move_actor`, `face`, `animate`, `wait`,
  `fade_out` / `fade_in`, `shake`, `camera_pan`, `camera_lock` / `camera_unlock`, `play_sound`,
  `show_dialogue` (a file or lines written into the command), `give_item` / `take_item`,
  `set_flag`, `set_var` / `add_var`, `event` (any dialogue event), `start_battle`, `change_map`,
  and the flow commands `label`, `goto`, `if` / `else`, `call`, `end` and `wait_for` (with
  `wait: false` a move, fade, pan or shake runs in the background while the next commands go on).
  While one runs the player's input, the interact prompt, the pause menu, autosave, overworld
  enemies and action-RPG fighters (no damage either) are held; `RpgSequenceRunner.running()` is
  what they ask. A sequence marked `skippable` is skipped with cancel: the rest plays at once
  (dialogues run their events with the first choice; a battle is still fought). Starting one:
  `RpgTriggerArea` (walk in, or interact; once per game through the flag `<entity_id>.triggered`;
  an optional condition), the dialogue event `run_sequence:<id>` (after the dialogue closes) or
  `RpgSequenceRunner.instance().run(...)`. New events `sequence_requested`, `sequence_started`,
  `sequence_finished`. `RpgActor.scripted_walk`, `hold_animation` and `release_animation`;
  `RpgSceneRouter.fade_alpha` / `set_fade_alpha`; `RpgDialogueBox.fast_forward` and
  `RpgDialogueRunner.fast_forward`.
* Variables (M12): `GameState.variables` (name -> int, `get_var` / `set_var` / `add_var`, saved
  under the optional key `variables`, so `save_version` stays 1), the dialogue events
  `set_var:<name>=<N>` and `add_var:<name>:<N>`, the condition `var:<name><op><N>` (`>=`, `<=`,
  `==`, `!=`, `>`, `<`) and the event `variable_changed`.
* Random encounters (M12, turn-based): `RpgEncounterZone` (a polygon, a shape, or the cells of an
  `Encounters` TileMapLayer; `steps_per_encounter`, default 24; `disabled_flag`),
  `RpgEncounterTable` (`game/data/encounters/<id>.tres`: weighted enemy groups, `can_escape`) and
  `RpgEncounterSteps` (tiles walked, teleports ignored, 6 grace steps after every battle). The
  turn-based mode counts the steps and starts the battles with `GameState.rng`, so a seeded game
  meets the same enemies at the same step. New turn-based projects get a zone over the east half
  of the field map (`game/data/encounters/field_1.tres`).
* Ranged combat (M12, action RPG): `RpgProjectile` (made in code, drawn as an orb or an arrow; the
  team's hitbox layers plus walls; the melee formula with the shooter's attack; spent on its first
  hit, at a wall or at its range; held during a sequence). `RpgItemDefinition.ranged`: a worn
  ranged weapon fires an arrow per attack instead of the swing (the heavy attack's arrow uses the
  heavy damage and knockback); the seeded bow is ranged.
* Enemy kinds (M12, action RPG): `behavior.kind` `melee`, `shooter`, `turret` or `charger`, with the
  components `RpgEnemyShoot` and `RpgEnemyCharge` (a telegraph tint during the windup) and new
  behavior keys (`shoot_range_px`, `keep_away_px`, `projectile_speed`, `projectile_range_px`,
  `shoot_windup_s`, `shoot_cooldown_s`, `charge_range_px`, `charge_speed`, `charge_windup_s`,
  `charge_s`, `charge_recover_s`, `charge_cooldown_s`). New definitions take the kind from words in
  the asset's name; new projects get a charger and a shooter made from the first enemy, used by the
  field map.
* Followers (M12): `RpgFollowers` (boot, under SceneRouter as `Followers`; boot's `followers`
  export) draws the party members behind the player on the map, one tile apart along the path the
  player walked, facing and walking with it. Pictures only: no body, nothing saved. Both archetypes.
  `RpgUtil.world_position` and `RpgUtil.map_tile_px` are new helpers.
* Keys, switches and gates (M12): `RpgGate` (opens for good with `key_item`, flag
  `<entity_id>.unlocked`; open while the dialogue condition `open_when` holds; drawn bars unless it
  has a "Visual" child), `RpgSwitch` (a plate, latching or `hold`, or a lever, `once`; flag
  `<entity_id>.on`) and locked map doors (`RpgDoor.key_item`, `consume_key`, `entity_id`). New keys
  `UI_LOCKED`, `UI_LOCKED_NEED`, `UI_UNLOCKED`; new events `switch_toggled`, `gate_changed`.
* Battle depth (M12, turn-based): `RpgStats.mp` / `max_mp` (saved under optional keys; +2 max MP a
  level for anyone who has some; refilled by a level up, `heal_party_full`, joining and a new game;
  `RpgUtil.max_mp`; the "mp" item effect). `RpgSkillDefinition` (`game/data/skills/<id>.tres`:
  kind physical / magic / heal / status, targets, MP cost, power, element, status and chance,
  cures) and a working `skill` command (the skill list in the item submenu; blocked by silence).
  `RpgActorDefinition` gains `skills` (skill -> level learned), `element_rates`, `status_immune`,
  `attack_element`, `attack_status` and `attack_status_chance`; `RpgItemDefinition` gains the same
  for worn equipment plus `element` and `cures` (the "cure" effect, in battle). `RpgBattleStatus`:
  poison, regen, sleep, silence, blind, haste, slow; they live on the `RpgBattleActor` and end with
  the battle. `RpgBattleMath.hit_chance` (speed, `evade`, blind), `roll_magic`, `roll_heal`,
  `apply_rate`; `RpgBattleEffects` resolves attacks, skills and the end of a round;
  `RpgBattleAi` runs `behavior.turn_based_rules` ({when, use, target, chance, once}) before the
  weights, whose keys may now be skill ids. New targets `TARGET_ALL_ALLIES`; new log entry type
  `miss`; the party panel shows MP and statuses. New turn-based projects get the skills fire, cure,
  sleep and venom, a hero who knows fire, a companion with cure and sleep, an antidote and an
  ether in the shop, and enemies with a weakness, a resistance or a rule. The skill command's label
  key is now `BATTLE_SKILL` (`BATTLE_SKILLS_NONE` stays, as "Skill", for older seeded files).
* Credits (M12): `RpgCredits` (`generated/data/credits.tres`, written on every build from the
  packs' licences, and the user's `game/data/credits_extra.tsv`) and `RpgCreditsMenu`, opened by
  a new *Credits* button on the title screen and in the pause menu (both look the button up with
  `get_node_or_null`, so scenes built before it still work). New keys `UI_CREDITS`,
  `UI_CREDITS_ASSETS`, `UI_CREDITS_ENGINE`, `UI_CREDITS_BY`.
* Eight-direction sprites (M12): a sprite can have the animations `<action>_down_left`,
  `_down_right`, `_up_left` and `_up_right`. `RpgAnimationDriver.play` takes an optional third
  argument, the direction of travel, and plays the diagonal along it when the sprite has one (a
  missing left or right diagonal is the other one mirrored); `RpgActor` passes its velocity and
  remembers it for the idle picture, and followers pass the way their path goes. A facing with no
  animation of its own now shows the direction 45 degrees next to it before it falls back to
  `down`, so a sprite drawn only in the four diagonals works. New: `dir_to_facing8`. `facing`
  stays one of four directions, so hitboxes, interaction and saves are unchanged.
* Input glyphs (M12): `RpgInputGlyphs` (`ui/input_glyphs.gd`) gives the text glyph of an action
  for the device used last: `[E]` on a keyboard, `[A]` / `[Cross]` / `[B]` on an Xbox,
  PlayStation or Nintendo pad (from the pad's name), `[Pad 0]` on a pad of unknown make. It reads
  the InputMap when asked, so remapped keys show at once. `RpgSettings` tracks the device
  (`input_device`, signal `input_device_changed`; a release, stick drift or mouse motion does not
  switch it). The interaction prompt, a key-hint line in the battle interface and on the title
  screen, and the settings remap list use it. No glyph art is bundled; the glyphs are text.
* Languages (M12): *Settings > Language* lists *System* and the locales of
  `generated/i18n` (`RpgStrings.locales()`); `RpgSettings.language` ("" follows the system) is saved
  in `settings.cfg` under `[text]` and applied with `TranslationServer.set_locale`. The settings
  menu redoes the texts it sets in code when the language changes; the title screen and battle
  hints follow `NOTIFICATION_TRANSLATION_CHANGED`. A key a language lacks shows its English text.
* Dialogue tools (M12): `RpgCondition.evaluate_on(expr, state)`, `problems(expr)` and
  `atom_problem(atom)`; `RpgDialogueRunner.execute_event_on(event, state)`, `event_problem(event)`,
  `EVENTS`, and the runner's optional `condition_check` / `event_runner` callables (the editor's test
  player uses a scratch state); `RpgDialogueJson.to_json` / `to_dict` (the import also reads a
  `portrait` path). The game's behaviour is unchanged.
* Lighting (M12): `RpgMapRoot` adds a `CanvasModulate` named `Ambient` (day outdoors,
  `RpgDayNight.INTERIOR` inside: `is_interior`, or a map id starting with "interior"; your own
  colour with `ambient_override`). `RpgLightSource` (`world/light_source.gd`, a `PointLight2D`):
  objects tagged `light` get one from the builder, with the radial texture of the lighting recipe
  (`generated/lighting/light_radial.tres`); a flame flickers, a lamp is steady, and it is switched
  off outside the camera. `RpgDayNight`: the optional time-of-day cycle (`RpgSettings.day_night`,
  *Settings → Day and night*, off by default) tints outdoor maps from the play time (a day per 24
  minutes, from 8 o'clock), so a save looks the same when it is loaded.
* Minimap and world map (M12): the builder's `minimap_recipe` saves one `ImageTexture` per map of
  `game/maps` to `generated/minimaps/<key>.tres` (`RpgMinimapData.key_for`: the project path
  without `res://` and `.tscn`, `/` as `__`), a pixel per cell with the metadata `origin_cell` and `tile_size`.
  `RpgMinimap` (`ui/minimap.gd`), added by Boot on a `CanvasLayer` named `MinimapLayer`, shows the
  area around the player with markers (`RpgMinimapData.markers`: doors, unopened chests, quest
  targets) and is hidden by `RpgSettings.minimap` (*Settings > Minimap*, on by default). A quest
  stage may name an entity id under the optional key `target`; `GameState.quest_targets()` lists
  those of the active quests. The fog: `GameState.fog_mark` / `fog_seen` / `visited_maps`, saved
  under the optional key `map_fog` ({key: {w, h, bits as base64}}; save_version stays 1).
  `RpgWorldMapMenu` (`world_map_menu`, *Pause > Map*) shows the visited maps with unseen cells
  covered. Projects built earlier keep working: the settings and pause menus look up the new
  controls by name and skip them when missing.
* `RpgDialogueLine`, `RpgDialogueChoice` and `RpgDialogueResource` are `@tool` scripts (pure data):
  the editor's dialogue tab reads and edits real instances (with placeholder instances it crashed
  the editor of a project that had dialogue). `RpgStrings.format(key, arg)` formats a translated
  toast with the English text when no translation has the key; the quest, party, door and gate
  toasts use it, so they work in the editor and in tests without the game's translations.

## 0.3.0

* Action-RPG archetype (`archetypes/arpg/`): hitboxes that are live only on attack frames, hurtboxes
  with invulnerability windows, health, knockback and crits; the player's combat state machine
  (idle, move, attack with an input buffer, hurt, dodge, dead); enemies with a component-based AI
  (detection with line of sight, chase, wander, telegraphed attacks, loot pickups); the HUD; the
  generic swing effect for characters without attack animations; optional tile-based navigation.
* Shared code: `RpgActor` gained `move_locked`, `facing_locked` and `animation_locked` (set by an
  archetype's combat code), `RpgAnimationDriver` gained `has_animation` / `play_exact`, the
  inventory menu has an extension point for archetype buttons, and boot takes the archetype's HUD.
## 0.2.0

* Turn-based archetype (`archetypes/turn_based/`): battle commands (attack, defend, item, skill
  placeholder, run), the battle controller and turn manager, the battle scene and interface,
  overworld enemies that start encounters, and the combat mode that returns the result to the map.
* A defeated enemy stays defeated across saves; escaping gives a short grace period; losing sends
  the player back to the newest save, or to the map's default spawn with full health.

## 0.1.0

* First release of the shared RPG runtime: events bus, game state, scene routing, saving,
  stats, items, inventory, dialogue, interaction, settings, audio, UI and translation-ready text.
