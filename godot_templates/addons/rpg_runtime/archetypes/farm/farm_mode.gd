class_name RpgFarmMode
extends RpgCombatMode
## The farm's mode (T17.04), SceneRouter.combat. A farm has no encounters; what the mode owns is
## what lasts from map to map: the calendar it asks for (`RpgCalendar.ensure()`), the farmer's
## energy and hotbar (its children `Energy` and `Hotbar`), the crops of the game, the four
## tools, the night of the fields (the calendar's `on_night`, NIGHT_CROPS), and the end of the
## day (its child `DayEnd`, T17.08: the night of the shipping bin, sleeping, passing out, the
## morning's summary), the weather (its child `Weather`, T17.11) and what a season changes
## beside the crops (its child `Seasons`, T17.11: the pictures of the ground and the music), and
## the days of the year that are not like the others (its child `Events`, T17.25: festivals and
## birthdays, with `festivals` on).

const ENERGY_NODE := "Energy"
const HOTBAR_NODE := "Hotbar"

## False: staying up to 2:00 costs no money (the option `starter_map.pass_out_loss`; the mode's
## recipe sets it).
@export var pass_out_loss: bool = true
## The days of a season and the real seconds of a game minute (the options
## `starter_map.days_per_season` and `starter_map.day_length`; the mode's recipe sets them). The
## mode gives both to the calendar it asks for.
@export var days_per_season: int = RpgCalendar.DAYS_PER_SEASON
@export var minute_s: float = RpgCalendar.MINUTE_S
## The folder of the game's own data files (`crops.json`, `people.json`, ...), set by the
## recipe. Empty in a mode that is made by code: the game then has the planned files only.
@export var data_dir: String = ""
## True: the year has festivals and the people have birthdays (the option
## `starter_map.festivals`; the mode's recipe sets it, and a mode that is made by code has none).
@export var festivals: bool = false

var energy: RpgEnergy = null
var hotbar: RpgHotbar = null
## The end of the day (RpgDayEnd).
var day_end: RpgDayEnd = null
## The weather (RpgFarmWeather) and the seasons' pictures and music (RpgFarmSeasons).
var weather: RpgFarmWeather = null
var seasons: RpgFarmSeasons = null
## The animal houses and the animals in them (RpgAnimalHouse, T17.07): its child `Animals`,
## which does nothing in a farm without an animal house.
var animals: RpgAnimalHouse = null
## What lies at the edges of the farm in the morning (RpgForage, T17.10: its child `Forage`,
## which also holds the table of the fish) and the cast of the rod (RpgFishing: `Fishing`).
var forage: RpgForage = null
var fishing: RpgFishing = null
## The festivals and the birthdays (RpgFarmEvents, T17.25: its child `Events`, which does
## nothing in a farm without `festivals`).
var events: RpgFarmEvents = null
## The crops of the game (game/data/crops.json).
var crops: RpgCropData = null

var _tools: Dictionary = {}  # item id -> RpgFarmTool

## The mode of the running game, or null in a game that is no farm.
static func current() -> RpgFarmMode:
	var router := RpgUtil.router()
	return router.combat as RpgFarmMode if router != null else null

func _ready() -> void:
	_name_data_files()
	ensure_parts()
	var calendar := RpgCalendar.ensure()
	if calendar != null:
		set_calendar(calendar)
		calendar.on_night(RpgCalendar.NIGHT_CROPS, _on_night)
	# the people of the village (T17.09): who they are, how well the farmer knows them, and
	# their schedules for the NPCs that carry one
	RpgFriendship.ensure()
	var bus := RpgUtil.events()
	if bus != null and not bus.game_paused.is_connected(_on_paused):
		bus.game_paused.connect(_on_paused)
	# the weather's morning comes before the day's end: the rain of a wet day has watered the
	# fields when sleeping saves the game
	weather.attach()
	seasons.attach()
	animals.attach()  # after the weather: it says whether the animals go out
	day_end.attach()  # after the fields: its night (NIGHT_SHOP) and its morning follow theirs
	forage.attach()
	fishing.attach()
	events.attach()  # after the friendships and the fishing: it asks the one and hears the other

## Gives `calendar` the season and the day this farm has (`days_per_season`, `minute_s`).
func set_calendar(calendar: RpgCalendar) -> void:
	calendar.days_per_season = RpgCalendar.season_length(days_per_season)
	calendar.minute_s = minute_s

## Tells the data classes where the game's own files are, before any of them reads.
func _name_data_files() -> void:
	if data_dir == "":
		return
	RpgCropData.user_path = data_dir.path_join("crops.json")
	RpgAnimalData.user_path = data_dir.path_join("animals.json")
	RpgForage.user_path = data_dir.path_join("forage.json")
	RpgFriendship.people_path = data_dir.path_join("people.json")
	RpgFarmEvents.user_path = data_dir.path_join("events.json")

## Makes what the mode consists of (in `_ready`, not when the scene is built: a saved scene
## would hold the parts and every instance would make them twice).
func ensure_parts() -> void:
	if energy == null:
		energy = get_node_or_null(ENERGY_NODE) as RpgEnergy
	if energy == null:
		energy = RpgEnergy.new()
		energy.name = ENERGY_NODE
		add_child(energy)
	if hotbar == null:
		hotbar = get_node_or_null(HOTBAR_NODE) as RpgHotbar
	if hotbar == null:
		hotbar = RpgHotbar.new()
		hotbar.name = HOTBAR_NODE
		add_child(hotbar)
	if day_end == null:
		day_end = get_node_or_null(RpgDayEnd.NODE_NAME) as RpgDayEnd
	if day_end == null:
		day_end = RpgDayEnd.new()
		day_end.name = RpgDayEnd.NODE_NAME
		add_child(day_end)
	day_end.pass_out_loss = pass_out_loss
	if weather == null:
		weather = get_node_or_null(RpgFarmWeather.NODE_NAME) as RpgFarmWeather
	if weather == null:
		weather = RpgFarmWeather.new()
		weather.name = RpgFarmWeather.NODE_NAME
		add_child(weather)
	if seasons == null:
		seasons = get_node_or_null(RpgFarmSeasons.NODE_NAME) as RpgFarmSeasons
	if seasons == null:
		seasons = RpgFarmSeasons.new()
		seasons.name = RpgFarmSeasons.NODE_NAME
		add_child(seasons)
	if animals == null:
		animals = get_node_or_null(RpgAnimalHouse.NODE_NAME) as RpgAnimalHouse
	if animals == null:
		animals = RpgAnimalHouse.new()
		animals.name = RpgAnimalHouse.NODE_NAME
		add_child(animals)
	if forage == null:
		forage = get_node_or_null(RpgForage.NODE_NAME) as RpgForage
	if forage == null:
		forage = RpgForage.new()
		forage.name = RpgForage.NODE_NAME
		add_child(forage)
	if fishing == null:
		fishing = get_node_or_null(RpgFishing.NODE_NAME) as RpgFishing
	if fishing == null:
		fishing = RpgFishing.new()
		fishing.name = RpgFishing.NODE_NAME
		add_child(fishing)
	if events == null:
		events = get_node_or_null(RpgFarmEvents.NODE_NAME) as RpgFarmEvents
	if events == null:
		events = RpgFarmEvents.new()
		events.name = RpgFarmEvents.NODE_NAME
		add_child(events)
	events.enabled = festivals
	if crops == null:
		crops = RpgCropData.load_default()
	if _tools.is_empty():
		var tools: Array[RpgFarmTool] = [RpgFarmHoe.new(), RpgFarmWateringCan.new(), RpgFarmSickle.new(), RpgFarmAxe.new()]
		for tool in tools:
			_tools[tool.id] = tool
	if not _tools.has(&"fishing_rod"):
		var rod := RpgFarmRod.new()  # the rod of T17.10: it casts through the mode's `Fishing`
		rod.fishing = fishing
		_tools[rod.id] = rod

func is_in_combat() -> bool:
	return false

func start_encounter(_data: RpgEncounterData) -> void:
	push_warning("[RPG-COMBAT] a farm has no encounters")

## The tool an item is, or null for an item that is none.
func tool_for(item_id: StringName) -> RpgFarmTool:
	var tool: RpgFarmTool = _tools.get(item_id)
	return tool

## What eating one of an item restores: the `energy` of the crop it is the produce of, of the
## fish or the thing to forage it is (T17.10), else the amount of a healing item, else 0 (it is
## no food).
func food_energy(item_id: StringName) -> int:
	if crops != null:
		var crop_id := crops.crop_of_produce(item_id)
		if crop_id != "":
			return maxi(0, RpgUtil.to_int(crops.crop(crop_id).get("energy", 0)))
	if forage != null and forage.energy_of(item_id) > 0:
		return forage.energy_of(item_id)
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(item_id) if state != null else null
	if def != null and def.use_effect == &"heal":
		return maxi(0, def.effect_amount)
	return 0

## Eats one of an item. False, and the item is kept, when it is no food or the farmer is rested.
func eat(item_id: StringName) -> bool:
	var state := RpgUtil.state()
	var amount := food_energy(item_id)
	if state == null or amount <= 0 or not state.inventory.has(item_id) or energy.value >= energy.max_energy:
		return false
	state.inventory.remove(item_id, 1)
	energy.restore(amount)
	RpgUtil.notify(RpgFarmStrings.t("FARM_ATE", [RpgFarmStrings.item_name(item_id)]))
	return true

# ------------------------------------------------------------------ the night and the morning

## The night of the fields. The calendar still shows the day that ended: the season of the
## morning after decides what withers.
func _on_night(_day: int) -> void:
	var calendar := RpgCalendar.current()
	if calendar == null:
		return
	var next := RpgCalendar.date_after(calendar.day, calendar.season, calendar.year, 1, calendar.days_per_season)
	RpgField.night_all(crops, RpgCalendar.season_name_of(next[1]))

# ------------------------------------------------------------------ the pause menu

## The pause menu has a People page (T17.09) and, in a farm with festivals, a Calendar page
## (T17.25). The menu is made anew each time it opens, so the buttons are added each time; a
## shop or another menu that pauses the game gets none.
func _on_paused(paused: bool) -> void:
	if not paused or RpgFriendship.current() == null:
		return
	var router := RpgUtil.router()
	var controller := router.get_node_or_null("UiController") if router != null else null
	if controller == null:
		return
	var menu: Variant = controller.get(&"_menu")
	if menu is RpgPauseMenu and is_instance_valid(menu):
		var pause: RpgPauseMenu = menu
		RpgPeoplePage.add_to(pause)
		if RpgFarmEvents.current() != null:
			RpgCalendarPage.add_to(pause)
