# Changelog

## 1.5.0

**Compatibility with 1.0 to 1.4.** The save version stays 1 and older saves load. One key is
new and optional: `calendar`, written only by a game that has a calendar; a save without it
loads on the first morning. No autoload is new, and a game without a calendar has the light
and the saves it had.

* **The calendar** (`world/calendar.gd`, `RpgCalendar`): the minute of the day, the day of the
  season, the season and the year. A day runs from 6:00 to 2:00 of the night; a game minute is
  `minute_s` real seconds (0.7: a day is 14 minutes); a season has `days_per_season` days (28,
  or 14 or 7). Time stands still while the game is paused (every menu), in a dialogue, in a
  cutscene, in a battle and while the map changes, and indoors with `stops_indoors`. Signals:
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
* **The farm** (`archetypes/farm/`, a seventh kind; installed only into a farm's project).
  `RpgFarmMode` is its mode (`SceneRouter.combat`): it asks for the calendar, makes the
  farmer's `RpgEnergy` and `RpgHotbar`, knows the four tools (`tool_for`), what an item
  restores when it is eaten (`food_energy`, `eat`), and runs the night of the fields from the
  calendar's `on_night` (`NIGHT_CROPS`). Until sleeping and the farm's own map exist it fills
  the energy and the watering can every morning.
* `RpgFarmer` extends `RpgActor`, the top-down player: `cell()`, `tile_ahead()` (and the static
  `ahead_of`, `step_of`), a frame on the ground at the tile ahead (the child `TileFrame`), and
  `use_held()`: a ripe crop ahead is harvested whatever is held, a tool works, a seed is
  planted in tilled soil, food is eaten. New input actions: `use`, `next_item`, `prev_item`,
  `hotbar_1` to `hotbar_10`. A tool's use shows the sheet's animation of its name (`hoe`,
  `water`, `sickle`, `axe`), else `attack`, else the tool's icon over the hands (`ToolIcon`).
  At zero energy the farmer walks at half its speed and no tool works.
* `RpgFarmTool` (an item id, an energy cost, a use time, the cell states it acts on, what it
  clears) and the four tools in `tools/`: `RpgFarmHoe` (`hoe`: tills ground), `RpgFarmWateringCan`
  (`watering_can`: waters soil, holds 20 cells' worth, is filled at a `water` tile for no
  energy), `RpgFarmSickle` (`sickle`: a ripe crop, a withered one, grass) and `RpgFarmAxe`
  (`farm_axe`: a stump, a branch). A use that changes nothing costs nothing.
* `RpgHotbar`: the first ten stacks of the inventory, one of them held (`held`, `select`,
  `next`, `prev`, `item_at`, `qty_at`, `held_item`, `hold_item`; the signal `changed`).
  `RpgEnergy`: `value`, `max_energy` (100), `spend`, `restore`, `fill`, `is_exhausted`; the
  signal `changed`. `RpgFarmHud` (`ui/farm_hud.gd`) shows both at the bottom of the screen.
* `RpgField`, a node of a farm map: the state of every worked cell as data (`cells`), painted
  on the map's `Soil` layer, with the crops as `RpgCrop` scenes among the Y-sorted entities.
  What can be tilled is the bool custom data `tillable` of a tile, and `water` fills the can.
  `till`, `water`, `water_all`, `plant`, `harvest`, `remove_crop`, `clear_obstacle`,
  `state_of` (`ground`, `soil`, `crop`, `ripe`, `withered`), `is_watered`, `crop_at`,
  `grown_at`; the signals `changed` and `harvested`. A night (`RpgField.grow`, `night_all`):
  a watered crop grows a day, an unwatered one does not, soil dries, a crop that does not grow
  in the season that begins withers, and bare soil is ground again after three dry nights. A
  field grows whether its map is shown or not.
* `RpgCropData`: the crops of `game/data/crops.json` (the user's; a crop only
  `generated/data/crops.json` has is added). `crop`, `crop_of_seed`, `crop_of_produce`, `days`,
  `stages`, `regrow`, `grows_in`, `of_season`, and the static `stage_of` and `is_ripe`.
* **Saves.** A farm keeps its state in `flags`, so the save has no new key: `farm` (`energy`,
  `held`, `water`) and `farm_field` (one key a field: its worked cells).
* **Money** (a farm only). `RpgShippingBin` (`archetypes/farm/shipping_bin.gd`, a solid thing
  of a map): `interact` while a thing with a price is held puts the whole held stack into it,
  `interact` with a tool or nothing in the hand takes the last stack back out. What is in it
  is in the flags (`farm_bin.items`), so the static `contents`, `count`, `put`, `take_back`,
  `price_of` and `sell_all` need no node: the night sells the bin wherever the farmer is, each
  thing at its item's `value`.
* `RpgDayEnd` (`archetypes/farm/day_end.gd`, the mode's child `DayEnd`, `RpgFarmMode.day_end`,
  `RpgDayEnd.current()`): its night listener (`NIGHT_SHOP`) sells the bin; `sleep()` ends the
  day once, and the morning after it the energy is full, the game is saved into the autosave
  slot and into the slot the player last saved to or loaded from by hand (`chosen_slot()`,
  the flag `farm.save_slot`; a game without one is offered the save screen), and the farmer
  stands at the bed. A day the clock ends at 2:00 is passing out: half the energy
  (`PASS_OUT_ENERGY`), a tenth of the money gone (`PASS_OUT_MONEY`) unless `pass_out_loss`
  is off (`RpgFarmMode.pass_out_loss`), awake at the bed of the game on whatever map it is,
  saved. A day ended by `end_day()` from elsewhere is neither: rested, nothing saved. Signals
  `woke(how)` (`slept`, `passed_out`, `ended`) and `summary_opened`. The mode no longer fills
  the energy every morning; it still fills the watering can until a map has water.
* `RpgBed` (`archetypes/farm/bed.gd`): `interact` sleeps. The first bed a game sees and every
  bed slept in is where the farmer wakes (`RpgBed.home`, the flags `farm_bed`;
  `wake_offset`, `wake_facing`, `footprint`).
* `RpgDaySummary` (`archetypes/farm/ui/day_summary.gd`): what the night sold, what each thing
  earned and the total, over the paused game, once, and only after a night that sold
  something; `confirm`, `interact`, `cancel` or its button closes it (`lines`, `total_text`,
  `worth_showing`, the signal `closed`).
* `RpgFarmShop` (`archetypes/farm/farm_shop.gd`, an `RpgShopDefinition`): `opens`, `closes`,
  `closed_weekday` and `is_open()`, `open_at`, `hours_text()`; its offer is its `stock`, then
  the seeds of the crops that grow in the season of the day (`seasonal`), then what
  `RpgFarmShop.add_stock_source(callable)` adds (the callable takes the season's name and
  returns rows `{item_id, price}`); a tool the farmer has is not offered again.
* `RpgShopDefinition.closed_reason()` is new and "" for every shop; `RpgUiController.open_shop`
  shows a non-empty one as a toast and does not open the shop. Only `RpgFarmShop` gives one,
  so every other shop opens as it did.
* `RpgWorldMapMenu` lists no *World* row for a plan file that holds nothing but a farm's
  crops (no areas). Every other game is what it was.
* **Schedules** (`actors/schedule.gd`, `RpgSchedule`; installed in every project and at work
  only in one with a calendar). A child `Schedule` of an NPC with `entries`: from which
  `hour`, on which `days` of the week, in which `weather`, on which `map`, at which `place` (a
  marker made by `RpgSchedule.make_place`, a `Marker2D` in the group `rpg_place`) or `cell`.
  `resolve(hour, weekday, weather)` gives the entry in force: the last whose hour has come
  among those of the day and the weather, an entry with a weather before one without. When
  its map is entered the NPC is put where the calendar says it is; one whose place is on
  another map is away (hidden, not in the way, not talkable). When an hour passes on the map
  that is shown it walks to its new place along the map's navigation
  (`NavigationServer2D.map_get_path`), to the nearest door when the place is on another map,
  and from the nearest door when it comes back; on a map without navigation it fades out, is
  moved and fades in (`fade_s`). `RpgSchedule.set_weather` tells every schedule the weather
  of the day; `RpgSchedule.source` gives a schedule without entries those of its `person`.
  New: `RpgNpc.schedule()` (null for an NPC without one, which is what it was).
* **Friendship** (`archetypes/farm/friendship.gd`, `RpgFriendship`; a farm only): points a
  person, ten hearts of 250. `talk(id)` gives 20 once a day; `gift(id, item_id)` gives by
  taste (80 loved, 45 liked, 20 otherwise, -20 disliked) and is taken twice a week; the
  calendar's `day_began` resets both counters. It reads `game/data/people.json` (the people,
  their tastes and their schedules), counts a talk when the player interacts with the NPC of
  a person, and is found with `RpgFriendship.current()` (made by `ensure()`, a child of
  GameState). Saved under the new optional key `friendship`, written only by a game that has
  it; the save version stays 1.
* The dialogue condition `friendship:<id>>=N` (hearts); false in a game without friendships.
* `RpgPeoplePage` (`archetypes/farm/ui/people_page.gd`): who was met, their hearts, and their
  taste for the items that were given to them. `RpgPeoplePage.add_to(pause_menu)` adds its
  button to a pause menu.
* **The weather** (`archetypes/farm/weather.gd`, `RpgFarmWeather`, the mode's child `Weather`,
  `RpgFarmMode.weather`; a farm only): `sun`, `rain`, a `storm` in summer, `snow` in winter.
  The weather of a day follows from the game's seed (the flag `farm_weather.seed`, drawn once
  a game) and the number of the day (`weather_of(seed, index, days_per_season)`), so it is the
  same before and after a save; the first day is fair. It is decided at `NIGHT_WEATHER` and in
  force from `day_began`; a new game and a loaded game take theirs when their map is entered.
  `today`, `forecast()`, `is_wet()`, `keeps_animals_in()`, the signal `changed(kind)`, and the
  debug hooks `force(kind)` and `force_tomorrow(kind)`. A wet day waters every tilled cell of
  every field in the morning (`water_fields`), what is tilled later in the day at once, and
  once more before the crops grow; it tells the schedules `"rain"` (`RpgSchedule.set_weather`).
  `enabled` is false until the mode's scene sets it: a mode made by code, and the smoke run,
  have fair weather unless a day is forced.
* `RpgWeatherOverlay` (`archetypes/farm/weather_overlay.gd`): what falls over the screen on an
  outdoor map, on a CanvasLayer (2) of the weather: a strip of cells repeated over the screen
  (`fall`), twice over for a storm without a picture, or drawn snow (`flakes`).
* `RpgDayNight.weather_tint` (a static `Color`, white): what the outdoor light is multiplied
  by. Only a farm's weather sets it; interiors and a map's own ambient are not touched.
* `RpgWeatherSign` (`archetypes/farm/weather_sign.gd`): `interact` shows tomorrow's weather as
  a toast.
* `RpgFarmSeasons` (`archetypes/farm/seasons.gd`, the mode's child `Seasons`,
  `RpgFarmMode.seasons`): on entering an outdoor map and on `season_changed` it replaces the
  textures that `generated/data/seasons.json` names by those of the season: the atlas sources
  of the tile sets, `Sprite2D.texture`, the frames of `AnimatedSprite2D` (`apply(map,
  season)`). It plays the music of the season on outdoor maps (`music_spring` to
  `music_winter`; a season without its own plays the first that is filled) and `music_night`
  from 20:00, in the place of the map's own music; a game with none of the slots keeps that.
* `RpgFarmHud` shows the time (in steps of ten minutes), the weekday, the day and the season,
  the weather (a word, or an icon of `weather_icons`) and the money, beside the hotbar and the
  energy; it hides the basic HUD's line of money, and tells a harvest and what the shipping
  bin paid by a toast (`watch_field`, `harvest_text`, `sale_text`). New text keys:
  `FARM_WEATHER_SUN`, `_RAIN`, `_STORM`, `_SNOW`, `FARM_FORECAST`, `FARM_HUD_DATE`,
  `FARM_HARVESTED`, `FARM_SOLD`.

* **The farm's own map and the people in it** (T17.06, T17.09). `RpgWaterSource`
  (`archetypes/farm/water_source.gd`): the pond or the well of a farm, a solid thing that
  fills the watering can with `interact` (`fill_can`); `use` with the can held fills it at a
  tile whose custom data `water` is true, as before. **The morning no longer fills the can**:
  `RpgFarmMode` filled it as a stand-in while no map had water.
* `RpgFarmMode` asks for the friendships (`RpgFriendship.ensure()`, after the calendar) and
  gives the pause menu its People page each time the menu opens (`Events.game_paused`,
  `RpgPeoplePage.add_to`).
* `RpgFarmer.give_held(target)`: `interact` on a person while an item that can be given is
  held (`is_gift`: not a tool, not a bag of seeds) gives it (`RpgFriendship.gift`); when
  nothing is given the farmer talks as before.
* `RpgInteraction.before` (a Callable, unset by default): asked before a target is interacted
  with; when it answers true the target's own `interact` is not called. Only the farmer sets
  it; every other kind interacts as it did.
* New texts of the farm: `FARM_CAN_FILLED`, `FARM_CAN_FULL`, and the names of its maps
  (`MAP_FARM`, `MAP_FARM_HOUSE`, `MAP_FARM_COOP`, `MAP_FARM_BARN`).
* The door check of the project tools counts the farm of a farm's plan (`farm.map` in
  `rpggen/world_plan.json`) among the maps of the world: a door of it that leads to a spawn
  point the village does not have is `VAL-028` (a warning that *Repair the world* mends), not
  `VAL-017`.

* **Foraging** (a farm only, T17.10). `RpgForage` (`archetypes/farm/forage.gd`, the mode's
  child `Forage`): every morning things of the season lie at some of the places of a map (its
  markers `Forage/Spot<n>`; for a farm map without markers the cells `spots` of
  `generated/data/forage.json`) and are picked up with `interact` (`RpgForagePickup`,
  `archetypes/farm/forage_pickup.gd`, made by `refresh` among the entities of the map). What
  lies where is not stored: `forage_of(entries, seed, day, season, places)` derives it from
  the seed of the game (the weather's), the map (`map_seed`), the index of the day and the
  season, 45 in a hundred places and always at least one. What was picked up today is the flag
  `farm_forage.picked`. The table is `game/data/forage.json`, then what only
  `generated/data/forage.json` has (`things`, `fish`, `energy_of`).
* **Fishing** (a farm only, T17.10). `RpgFarmRod` (`archetypes/farm/tools/rod.gd`, the item
  `fishing_rod`, 3 energy a cast) casts at a tile whose custom data `water` is true;
  `RpgFishing` (`archetypes/farm/fishing.gd`, the mode's child `Fishing`) does the rest:
  `cast(field, cell)` (false with a toast at a well: `water_kind` asks the map's
  `RpgWaterSource`), a wait of 1 to 4 seconds of the running game that follows from the seed
  and the number of the cast (`wait_of`; the flag `farm_fishing.casts`), the bite (`bit`, the
  sound `sfx_bite` when the game has such a slot), then the bar (`RpgFishingBar`,
  `archetypes/farm/ui/fishing_bar.gd`, on a layer of its own): `mark`, `zone`, `meter`, the
  zone rising while `use` is held; `caught(item)` when the meter is full, `lost(why)` when it
  is empty, when the line is pulled in, when nothing bites, when the bag is full and when a new
  day or another map ends the cast. A cast passes 10 minutes of the calendar and the bar 20
  more. `fish_for` chooses among the fish of the table that bite in the season, at the time of
  day (`time_of`) and in the water. `advance(delta)` and `button` are for tests.
* `RpgFarmMode` has the two parts (`forage`, `fishing`) and the rod among its tools;
  `food_energy` knows what a fish and a thing to forage restore. `RpgFarmer.fishing` keeps the
  farmer where it stands while a line is out. `RpgWaterSource.kind` is now read by the game.
  New texts: `ITEM_FISHING_ROD_NAME`, `ITEM_FISHING_ROD_DESC`, `FARM_FORAGED`,
  `FARM_FISH_WELL`, `FARM_FISH_PULLED`, `FARM_FISH_NOTHING`, `FARM_FISH_AWAY`,
  `FARM_FISH_CAUGHT`. New flags of the saved game (no new key): `farm_forage`, `farm_fishing`.
* **Animals** (T17.07; `archetypes/farm/`). `RpgAnimalHouse` is a part of the mode (its child
  `Animals`, `RpgFarmMode.animals`; it does nothing in a farm without an animal house). The
  herd is data in the flags of the game state (`farm_animals.herd`: a row an animal with its
  kind, name, house, stall, colour variant, friendship, `fed`, `petted` and the product it has
  `ready`; `farm_animals.trough`: house -> full), so the save has no new key and the night
  works on animals whose map is not shown. `herd()`, `animal(id)`, `of_house(house)`,
  `friendship(id)`, `hearts(id)`, `trough_full(house)` are static; `room_in`, `can_buy`, `buy`,
  `fill_trough`, `feed_with`, `pet`, `take_product`, `touch`, `product_for`, `product_price`,
  `night`, `is_outside`, `is_night`, `populate`, `show_room`, `show_yard`, `node_of`, `shown`
  and the signal `changed` are the node's. One portion of the feed in the trough of a house
  feeds every animal of it for the day; petting gives 15 points once a day; in the night
  (`on_night`, `NIGHT_ANIMALS`) a fed animal gets its product and 5 points and an unfed one
  loses 20; from five hearts (of ten, 100 points each) the product is the kind's `large` item.
  Animals are out in their yard from 6:00 to 18:00 unless `RpgFarmWeather.keeps_animals_in()`,
  else in their stalls; the nodes of a map are made from the data when it is entered and when
  the hour or the weather changes the place.
* `RpgFarmAnimal` extends `RpgActor` (layer 5: found by `interact`, walked through): the node of one animal (`animal_id`, `kind`),
  which wanders a rectangle (`roam`, with random numbers of its own), sleeps (`sleep`: the
  `sleep` animation when the sheet has one) and is petted and relieved of its product by
  `interact`. `RpgFarmTrough` (a `StaticBody2D`, layers 1 and 5, made at `Markers/Trough` by
  `make`) takes the held feed on `interact`; `RpgAnimalProduct` (an `Area2D`, layer 5) is what
  lies on the floor of a coop and is picked up by `interact`. `RpgAnimalData` reads
  `game/data/animals.json`, then `generated/data/animals.json` for the kinds and houses the
  first does not list.
* `RpgFarmShop.buy` (new, an override): a row of a stock source that names `deliver` (a callable
  `func(item_id, qty) -> String`) is paid for and delivered instead of being put into the bag;
  the animals' rows are such rows, and no other shop has any. `RpgField` has the signal
  `cleared(cell, what)`, emitted by `clear_obstacle`: cut grass is hay in a farm with animals.
* **The isometric tile set** (T17.13; the builder only: no script of the runtime changed, and a
  project that is not isometric is built as it was). A project whose config says `projection:
  isometric` gets `generated/tilesets/iso.tres` from the tile set recipe through the new
  `builder/lib/iso_tileset.gd`: Godot's isometric tile shape with the layout *diamond down*
  (a cell (x, y), x east and y south, has its middle at `((x - y + 1) * w / 2, (x + y + 1) * h
  / 2)`), the tile size the diamond of the pack (180 x 104, never assumed 2:1), sources that
  are atlas pictures of single tiles in `generated/iso_atlases/`, and for every tile its
  texture origin (the middle of its diamond from the middle of its atlas cell), the custom
  data `asset_id`, `footstep`, `tillable` and `water`, and a collision polygon that is its
  diamond (a wall) or a profile laid on the diamond. A tile turned four ways is four tiles: an
  alternative tile of Godot cannot show another picture. `IsoTileset.new(catalog)` answers
  the map recipes: `tile_for(asset_id, turn)`, `piece_for(pack | tag | role, joins)`,
  `paint(layer, cell, asset_id, turn)`, `cell_to_local`, `stand(sprite, facets, at)`. The merge
  rules are the ones of every tile set: no source loses its id and no tile its atlas coords.
  `RECIPE_VERSION` of the tile set recipe stays 5: its hash has a new key only for an
  isometric tile set.
* `CatalogReader.assets()` (and with it `assets_by_role` and every lookup built on them) leaves
  out what was drawn for the other view (T17.13): nothing whose `projection` is `isometric` in
  a project that is seen from above or from the side, no sheet of square tiles in an isometric
  one. No catalog before 1.5 has such an asset, so nothing an older project is built from
  changes. `asset(id)` still finds any asset by its id.
* **Isometric maps and actors** (T17.14; `world/iso.gd`, `RpgIso`). The arithmetic of the
  view, the same as `rpggen/core/iso_math.py` (one table of cases tests both): `cell_to_screen`,
  `screen_to_cell`, `grid_point`, `depth` (the sort key of a cell: the y of its middle),
  `diamond`, `neighbours` and `step` (n the upper right, e the lower right, s the lower left, w
  the upper left), `unit` (the length of one step in px), `side_of`, `faced_side` and
  `faced_cell`, `pad_vector` and `pad_side`, `bounds`, and `sort_keys` / `in_front` for a thing
  that stands on several cells. And what asks a map, for squares and diamonds alike:
  `footprint_of(map)` (zero on squares), `map_unit`, `cell_at`, `cell_position`, `cell_ahead`,
  `move_vector`, `reach_dir`, `used_rect`, `controls()`. A map of squares is answered with the
  arithmetic of squares.
* On an isometric map `RpgUtil.map_tile_px(map)` is `RpgIso.unit` of its diamond (34 for 60 x
  34), not the width of the diamond: what a reach, a spacing or the step counter of the random
  encounters means by a tile there. On every other map it is what it was.
* `RpgActor` has `look()` (the last direction of travel), `map_node()`, `map_cell()` and
  `cell_ahead()`: the cell an actor stands on and the one it faces, asked of the map. On an
  isometric map the cell ahead is the neighbour the actor last walked towards, else the one
  its facing names (up n, right e, down s, left w).
* `RpgPlayerInput.pad(input)`: on an isometric map whose project says `iso_controls: grid`
  (the project setting `rpg/iso_controls`, written by the builder for an isometric project
  only) the four directions of the pad follow the axes of the diamond, and `RpgInteraction`
  reaches towards the neighbour the player faces. With the default (`screen`) and on every map
  of squares the pad is the screen, as before. The facing of an actor is still one of four, by
  where it goes on the screen; a sheet with diagonal animations shows them along the axes.
* `RpgMapRoot.used_rect_px()` (the limits of the camera) is the rectangle around the painted
  diamonds of an isometric map. `RpgMinimapData.cell_at` finds the cell of a position by the
  diamond for a minimap whose texture has the metadata `isometric`: the minimap of an
  isometric map is its plan from above, a pixel a cell, like every other.
* The builder (T17.14). `builder/lib/map_geo.gd` (`MapGeo`) is the seam between a plan of cells
  and the px of a map: `center`, `foot`, `bottom`, `step`, `cell_shape`, `cells_outline`,
  `gate_position`, `building_info`, `building_position`, `find_tile`, `tile_of_asset`,
  `nth_tile_with_role`, `other_tiles`, `wall_tile`, `paint_joined` / `paint_runs` /
  `fill_joined`, `paint_walls`, `border_collision`, `add_exit_door`, and the static
  `tile_unit(ctx)`. The starter map, the interiors, the field, the areas of a world, the doors
  and gates of a world plan, the actors and the object scenes take every position, shape and
  tile through it; for a project seen from above it calls what they called before, with the
  same numbers. For `projection: isometric` the maps are painted on `iso.tres`: ground from
  the flat `GROUND` tiles (patches of the others by the seed), roads, water and walls from the
  pieces whose `joins` fit (`IsoTileset.nearest_piece`: the piece with the fewest wrong sides
  and one note a map when none fits exactly; the plain tile when none names its sides), a wall
  that rises on the Y-sorted `Props` layer, an invisible diamond a cell where the packs have no
  wall. An isometric object stands on the middle of its diamond and blocks the cells it stands
  on; one of several cells is drawn in two halves that sort apart (`Sprite`, `SpriteRight`,
  the root `y_sort_enabled`); the `Entrance` of a building is a band along its south side and
  its `ExitSpawn` the middle of the door cell. `RECIPE_VERSION` of no recipe moved: the hashes
  of the map recipes and of the project settings have new keys (`iso`, `iso_v`,
  `iso_controls`) only in an isometric project, so nothing of a project seen from above is
  built again.
* `builder/smoke/smoke_map.gd`: what a smoke step asks the map instead of the screen (`cells`,
  `pad_toward`, `walk_toward`). The steps `collision_blocks`, `enter_building`,
  `exit_building`, `decor_blocks`, `walk_to_field`, `return_from_field`, `world_doors` and
  `encounter_start` walk to a place through it; on a map of squares they hold the key they
  always held. The steps that talk to somebody or open something stand as far from it as the
  player's interaction reaches (9 px with tiles of 16 px, as before), and `followers_trail`
  walks at least a tile and a quarter (80 px, as before, up to a tile of 64 px).
* The text of the menus of an isometric project follows the config's `base_tile_size`, not the
  diamond (`theme_recipe.gd`), and the player's camera is drawn back when fewer than eight
  diamonds would fit across the screen (`MapGeo.camera_zoom`: 180 px diamonds on a screen of
  640 px are shown at 0.44).
* **The farm in the isometric view** (T17.14). The plan of a farm is a grid of cells in both
  views and a save has the same shape; what follows is how the game and the builder turn its
  cells into places on diamonds. Nothing of a farm seen from above changes.
  * `RpgField` asks its `Soil` layer for cells and places as before, so a layer of diamonds
    carries over. New: `footprint()` (the diamond of its cells, zero on squares) and
    `foot_of(cell)` (where a thing of a cell stands: a px above the lower edge of a square, the
    middle of a diamond; crops are put there). `tile_px` is `RpgIso.unit` of the diamond on an
    isometric layer.
  * `RpgFarmer.tile_ahead()` is the neighbour the farmer faces on diamonds
    (`RpgIso.faced_cell`, what `RpgActor.cell_ahead()` answers), with either setting of
    `iso_controls`; on squares it is what it was. New: `diamond()`, and `face_cell(cell)`,
    which turns the farmer to a cell beside its own (the facing on squares; the facing and
    where it looks on diamonds). The `TileFrame` takes the shape of the field's diamond when
    the map has one, and keeps its width on the screen when the camera is drawn back. Without a field on a map of diamonds (the farmhouse) `cell()` asks the map.
  * `RpgFarmAnimal.roam_cells(layer, cells, inset)`: an animal wanders over cells of a layer
    of diamonds (`roaming_cells()`), where `roam(rect)` takes a rectangle of the screen.
    `RpgAnimalHouse` uses it for a yard of an isometric farm and puts the trough, the animals
    and what they leave on the middle of their cells.
  * `RpgFarmTrough.make`, `RpgForagePickup.make` and `RpgAnimalProduct.make` take the diamond
    of the map as a last, optional argument: the thing then lies on the middle of its cell and
    its shape is that diamond (the trough a box on it).
  * `archetypes/farm/farm_iso.gd` (`RpgFarmIso`): the diamond of a cell as points and as a
    shape, `box` / `box_faces` (a box on a diamond: three `Polygon2D`, the south face, the
    east face in shade, the top), `halves` / `add_face` / `add_box` (a thing of several cells
    drawn in two halves that sort apart, as an isometric object of the packs is), `clip_x`,
    and `grid_of` / `world_of` (a place of the world in the grid of a layer of diamonds).
  * The builder. The farm's recipes take every position and every shape through `MapGeo`:
    `farm_map_recipe.gd` (the farm and the rooms; `farm_root` and `room_root` give the nodes
    of a map before it is saved), `home_recipe.gd`, `field_recipe.gd`, `crop_recipes.gd`,
    `forage_recipe.gd` (`add_places(root, geo)`), `hud_recipe.gd` (the sign) and
    `people_recipes.gd` (the village's door, the places and the people). For an isometric
    farm: `farm_soil.tres` is an isometric tile set of the project's footprint whose five
    tiles are drawn as diamonds (`FarmBuild.iso_soil_texture`), with the flat isometric tile
    a pack tagged `soil` or `watered` as its source 1 or 2 when it has one
    (`FarmBuild.iso_soil_asset`); a building of the packs
    stands on the plan's footprint with its door before the plan's door cell
    (`iso_building_offset`), else the building is a drawn box with a roof whose door is a band
    along its south side; fences join the pieces beside them; the bin, the bed, the well,
    trees and scenery are isometric pictures of the packs (one cell, by the same words) or
    boxes on their diamond; what blocks blocks its diamond. `FarmBuild.tile` is one step on
    the diamonds. `RECIPE_VERSION` of no recipe moved: the hashes have new keys (`iso`,
    `iso_v`) only in an isometric project.
  * `builder/smoke/smoke_steps_farm.gd` asks the map: walks through doors go to the door
    (`SmokeMap.walk_toward`), the farmer is turned to the cell it works on (`face_cell`),
    stands where its interaction reaches (`RpgIso.reach_dir`), and a yard is its cells. On a
    farm of squares every step does what it did.
* **The isometric race** (T17.15). A race is driven on the flat plan of its track whatever
  the view: the position, the heading and the velocity of a car, the barriers, the checkpoints,
  the waypoints, the pickups and the weapons are the plan's, and `RpgCarPhysics`, `RpgRace`,
  `RpgRival`, `RpgRaceCheckpoint` and `RpgTrackSurfaces` are unchanged (a rival drives the
  same lap in both views, step for step). Only what is drawn is elsewhere.
  * `RpgRaceView` (`archetypes/racing/race_view.gd`, new): the child `View` of a track that is
    painted on diamonds; a track seen from above has none. `footprint`, `cell_px`, `origin`;
    `to_screen`, `to_plan`, `screen_vector`, `plan_vector`, `screen_heading`, `plan_heading`,
    `scale_px`, `depth`, `screen_rect`, `screen_corners`, on `RpgIso`'s grid; `RpgRaceView.of(node)`
    finds it from anything of the track (null from above).
  * `RpgCar`: `view()`, `shown_position()`, `shown_heading()`, `shown_forward()`: where the car
    is drawn and which way it points on the screen (its own place and heading from above). On
    a track with a view its `Visual` is moved to that place, takes the row of diamonds as its
    `z_index`, and shows the heading as it is seen; with `absolute_steering` the stick is a
    direction of the screen. From above the car does what it did.
  * `RpgHeadingSprite` is given the heading on the screen. A car in eight headings as eight
    files (`car_N.png` to `car_NW.png`, N up on the screen, then clockwise) shows `SE` when it
    heads east in the plan; a sheet drawn from straight above is shown the same way and looks
    flat; one picture is turned. Eight headings turn in steps of 45 degrees.
  * `RpgRaceCamera`: follows where the car is drawn (`target_position()`) and leads it the way
    it moves on the screen; `base_zoom` (1 by default: nothing changes from above) is the zoom
    over a car that stands, and a fixed camera never comes nearer than that.
  * `RpgRacePickup` and `RpgRaceWeapon` keep their place in the plan and draw themselves where
    the view has it (`shown_position()`).
  * The builder: `recipes/racing/iso_track.gd` builds the track of an isometric project (the
    ground on `iso.tres`, the road from the road pieces of the packs along the loop or drawn,
    the marks, the walls and the scenery on the diamonds; the barriers, the cars, the pickups
    and the race in the plan); `MapGeo.paint_sides` lays pieces whose sides are known;
    `RaceBuild.scale_for` chooses the scale for the picture of the car. The hashes of the
    racing recipes have a key more only in an isometric project, and a race seen from above
    is built byte for byte as before.
  * `builder/smoke/smoke_steps_racing.gd` asks the car where it is drawn in the three places
    that are about the picture (the car is on the screen, the frame of its picture, the
    camera ahead of it), and holds the arrows of absolute steering the way the waypoint is
    seen. Everything else already asked the plan.

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
