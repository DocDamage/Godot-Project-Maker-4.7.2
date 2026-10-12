class_name RpgFarmMode
extends RpgCombatMode
## The farm's mode (T17.04), SceneRouter.combat. A farm has no encounters; what the mode owns is
## what lasts from map to map: the calendar it asks for (`RpgCalendar.ensure()`), the farmer's
## energy and hotbar (its children `Energy` and `Hotbar`), the crops of the game, the four
## tools, the night of the fields (the calendar's `on_night`, NIGHT_CROPS), and the end of the
## day (its child `DayEnd`, T17.08: the night of the shipping bin, sleeping, passing out, the
## morning's summary).

const ENERGY_NODE := "Energy"
const HOTBAR_NODE := "Hotbar"

## False: staying up to 2:00 costs no money (the option `starter_map.pass_out_loss`; the mode's
## recipe sets it).
@export var pass_out_loss: bool = true

var energy: RpgEnergy = null
var hotbar: RpgHotbar = null
## The end of the day (RpgDayEnd).
var day_end: RpgDayEnd = null
## The crops of the game (game/data/crops.json).
var crops: RpgCropData = null

var _tools: Dictionary = {}  # item id -> RpgFarmTool

## The mode of the running game, or null in a game that is no farm.
static func current() -> RpgFarmMode:
	var router := RpgUtil.router()
	return router.combat as RpgFarmMode if router != null else null

func _ready() -> void:
	ensure_parts()
	var calendar := RpgCalendar.ensure()
	if calendar != null:
		calendar.on_night(RpgCalendar.NIGHT_CROPS, _on_night)
		if not calendar.day_began.is_connected(_on_morning):
			calendar.day_began.connect(_on_morning)
	day_end.attach()  # after the fields: its night (NIGHT_SHOP) and its morning follow theirs

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
	if crops == null:
		crops = RpgCropData.load_default()
	if _tools.is_empty():
		var tools: Array[RpgFarmTool] = [RpgFarmHoe.new(), RpgFarmWateringCan.new(), RpgFarmSickle.new(), RpgFarmAxe.new()]
		for tool in tools:
			_tools[tool.id] = tool

func is_in_combat() -> bool:
	return false

func start_encounter(_data: RpgEncounterData) -> void:
	push_warning("[RPG-COMBAT] a farm has no encounters")

## The tool an item is, or null for an item that is none.
func tool_for(item_id: StringName) -> RpgFarmTool:
	var tool: RpgFarmTool = _tools.get(item_id)
	return tool

## What eating one of an item restores: the `energy` of the crop it is the produce of, else
## the amount of a healing item, else 0 (it is no food).
func food_energy(item_id: StringName) -> int:
	if crops != null:
		var crop_id := crops.crop_of_produce(item_id)
		if crop_id != "":
			return maxi(0, RpgUtil.to_int(crops.crop(crop_id).get("energy", 0)))
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

## A stand-in until the card that owns it: the farmer wakes with a full can (the pond or the
## well of the farm's plan is T17.06). The energy of the morning is RpgDayEnd's: full after a
## sleep, half after staying up to 2:00.
func _on_morning(_day: int) -> void:
	RpgFarmWateringCan.fill()
