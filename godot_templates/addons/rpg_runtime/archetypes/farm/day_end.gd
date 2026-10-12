class_name RpgDayEnd
extends Node
## The end of a farm's day (T17.08). A child of the farm's mode (`DayEnd`), made by it like the
## energy and the hotbar.
##
## * **The night**: a night listener of the calendar (`on_night`, NIGHT_SHOP: after the crops and
##   the animals, so that what the night itself yields is never sold a day early, and with the
##   shop, whose business money is) sells what is in the shipping bin (RpgShippingBin.sell_all).
## * **Sleeping** (`sleep()`, what `interact` with an RpgBed calls): `RpgCalendar.end_day()`
##   once, with all its listeners; in the morning the energy is full, the game is saved into the
##   autosave slot and into the slot the player chose (the slot of the last save or load by
##   hand; a game that has none yet is offered the save screen), and the summary is shown.
## * **Staying up to 2:00** (the clock ends the day itself): the farmer wakes at the bed
##   (RpgBed.home) with PASS_OUT_ENERGY of the energy and, with `pass_out_loss`, PASS_OUT_MONEY
##   of the money gone. The game is saved into the autosave slot and the chosen one.
## * A day that something else ends (`end_day()` called by a test, by a cutscene) is neither: the
##   farmer wakes rested where it stands and nothing is saved. The bin is sold all the same.
## * **The summary** (RpgDaySummary) is shown once when the day begins, over the paused game,
##   when the night sold something.

## A morning is done: `how` is SLEPT, PASSED_OUT or ENDED. The summary, if any, is closed.
signal woke(how: String)
signal summary_opened(summary: RpgDaySummary)

const NODE_NAME := "DayEnd"
const SLEPT := "slept"
const PASSED_OUT := "passed_out"
const ENDED := "ended"
## What is left of the energy, and what is taken of the money, after passing out.
const PASS_OUT_ENERGY := 0.5
const PASS_OUT_MONEY := 0.1
## Over the HUD, under the menus (60).
const SUMMARY_LAYER := 55
## The flag that keeps the slot the player chose (`farm.save_slot`): in the flags, so that a
## new game has none and a loaded game has its own.
const FLAG_ENTITY := "farm"
const SLOT_KEY := "save_slot"

## False: passing out costs no money (the option `starter_map.pass_out_loss`).
var pass_out_loss := true
## What the last night sold (RpgShippingBin.sell_all), how it came, and what passing out cost.
var last_sale: Dictionary = {}
var last_night := ENDED
var money_lost := 0
## True when the last morning's save into the autosave slot was written.
var saved := false
## The farmer, when the map cannot be asked (a test sets it).
var farmer: Node2D = null

var _sleeping := false
var _how := ENDED
var _summary: RpgDaySummary = null
var _layer: CanvasLayer = null

## The day's end of the running game, or null in a game that is no farm.
static func current() -> RpgDayEnd:
	var mode := RpgFarmMode.current()
	return mode.day_end if mode != null else null

## Listens to the calendar and to the saves. The mode calls it once the calendar exists; a
## second call changes nothing.
func attach() -> void:
	var calendar := RpgCalendar.current()
	if calendar != null:
		calendar.on_night(RpgCalendar.NIGHT_SHOP, _on_night)
		if not calendar.day_began.is_connected(_on_morning):
			calendar.day_began.connect(_on_morning)
	var bus := RpgUtil.events()
	if bus != null:
		if not bus.game_saved.is_connected(_on_slot_used):
			bus.game_saved.connect(_on_slot_used)
		if not bus.game_loaded.is_connected(_on_loaded):
			bus.game_loaded.connect(_on_loaded)

# ------------------------------------------------------------------ the slot the player chose

func _on_slot_used(slot: int) -> void:
	var state := RpgUtil.state()
	if state != null and slot > RpgSaveManager.AUTOSAVE_SLOT and slot != chosen_slot():
		state.set_flag(FLAG_ENTITY, SLOT_KEY, slot)

func _on_loaded(slot: int) -> void:
	last_sale = {}
	_on_slot_used(slot)

## The slot a sleep is also saved into, or RpgSaveManager.NO_SLOT.
func chosen_slot() -> int:
	var state := RpgUtil.state()
	if state == null:
		return RpgSaveManager.NO_SLOT
	var slot := RpgUtil.to_int(state.get_flag(FLAG_ENTITY, SLOT_KEY, RpgSaveManager.NO_SLOT), RpgSaveManager.NO_SLOT)
	return slot if slot > RpgSaveManager.AUTOSAVE_SLOT and slot <= RpgSaveManager.SLOTS else RpgSaveManager.NO_SLOT

# ------------------------------------------------------------------ sleeping and the night

## Goes to sleep: the day ends, once. False when it cannot (no calendar, a night that is still
## running, the summary still open).
func sleep(bed: RpgBed = null) -> bool:
	var calendar := RpgCalendar.current()
	if calendar == null or _sleeping or is_summary_open():
		return false
	if bed != null:
		bed.remember()
	_sleeping = true
	calendar.end_day()
	_sleeping = false
	return true

func is_summary_open() -> bool:
	return _summary != null and is_instance_valid(_summary)

## The summary that is shown, or null.
func summary() -> RpgDaySummary:
	return _summary if is_summary_open() else null

## The night listener: the calendar still shows the day that ended, and its minute says whether
## the clock ended it (2:00) or somebody else did.
func _on_night(_day: int) -> void:
	var calendar := RpgCalendar.current()
	if _sleeping:
		_how = SLEPT
	elif calendar != null and calendar.minute >= RpgCalendar.DAY_END:
		_how = PASSED_OUT
	else:
		_how = ENDED
	last_sale = RpgShippingBin.sell_all()

func _energy() -> RpgEnergy:
	var mode := get_parent() as RpgFarmMode
	return mode.energy if mode != null else null

func _on_morning(_day: int) -> void:
	var how := _how
	_how = ENDED
	last_night = how
	money_lost = 0
	saved = false
	var energy := _energy()
	var state := RpgUtil.state()
	if how == PASSED_OUT:
		if energy != null:
			energy.value = floori(energy.max_energy * PASS_OUT_ENERGY)
		if pass_out_loss and state != null:
			money_lost = floori(state.gold * PASS_OUT_MONEY)
			state.gold -= money_lost
	elif energy != null:
		energy.fill()
	_finish_morning(how)

## What follows the night, in its order: the farmer is at the bed, the game is saved, the
## summary is shown and closed, the save screen is offered. It waits only for a map change and
## for the summary, so a morning without either is done when this returns.
func _finish_morning(how: String) -> void:
	if how != ENDED:
		await _wake_at_bed()
		save_night()
	if how == PASSED_OUT:
		var short := RpgRealtimeText.t("UI_GOLD_SHORT", [], RpgStrings.KEYS)
		RpgUtil.notify(RpgFarmStrings.t("FARM_PASSED_OUT_LOST", [money_lost, short]) if money_lost > 0 else RpgFarmStrings.t("FARM_PASSED_OUT"))
	if RpgDaySummary.worth_showing(last_sale):
		var shown := show_summary(last_sale)
		await shown.closed
	if how == SLEPT and chosen_slot() == RpgSaveManager.NO_SLOT:
		offer_slot()
	woke.emit(how)

# ------------------------------------------------------------------ the bed

func _the_farmer() -> Node2D:
	if farmer != null and is_instance_valid(farmer):
		return farmer
	var router := RpgUtil.router()
	return router.current_map.get_player() if router != null and router.current_map != null else null

## Puts the farmer where it wakes: at the bed of the game, on its map (the map changes when the
## farmer passed out on another one). Nothing in a game that has seen no bed.
func _wake_at_bed() -> void:
	var state := RpgUtil.state()
	var home := RpgBed.home(state)
	if home.is_empty():
		return
	var map := RpgUtil.to_str(home["map"])
	var at: Vector2 = home["position"]
	var facing := RpgUtil.to_str(home["facing"])
	var router := RpgUtil.router()
	var here := router.current_map.scene_file_path if router != null and router.current_map != null else ""
	if router != null and map != "" and here != map:
		state.current_map = map
		state.player_position = at
		state.player_facing = facing
		await router.reload_from_state()
		return
	var who := _the_farmer()
	if who == null:
		return
	if who.is_inside_tree():
		who.global_position = at
	else:
		who.position = at
	if who.has_method(&"set_facing"):
		who.call(&"set_facing", facing)

# ------------------------------------------------------------------ the save

## Saves the morning into the autosave slot and, when the player chose one, into that slot too
## (whatever the autosave setting says: sleeping is how a farm saves). False when the autosave
## could not be written.
func save_night() -> bool:
	var save := RpgUtil.save_manager()
	saved = save != null and save.save(RpgSaveManager.AUTOSAVE_SLOT)
	if not saved:
		return false
	var slot := chosen_slot()
	if slot != RpgSaveManager.NO_SLOT:
		save.save(slot)
	RpgUtil.notify(RpgRealtimeText.t("UI_AUTOSAVED", [], RpgStrings.KEYS))
	return true

## Opens the save screen of the game (as a save station does), for a game that has no slot of
## its own yet. Returns the menu, or null when it cannot be opened.
func offer_slot() -> Control:
	var router := RpgUtil.router()
	var controller := router.get_node_or_null("UiController") as RpgUiController if router != null else null
	return controller.open_menu("save_load_menu", {"mode": "save"}) if controller != null else null

# ------------------------------------------------------------------ the summary

## Shows the summary of a sale over the paused game and returns it.
func show_summary(sale: Dictionary) -> RpgDaySummary:
	if is_summary_open():
		_summary.close()
	if _layer == null:
		_layer = CanvasLayer.new()
		_layer.name = "SummaryLayer"
		_layer.layer = SUMMARY_LAYER
		_layer.process_mode = Node.PROCESS_MODE_ALWAYS
		add_child(_layer)
	_summary = RpgDaySummary.new()
	_summary.name = "DaySummary"
	_summary.setup(sale)
	_layer.add_child(_summary)
	_summary.closed.connect(_on_summary_closed)
	var tree := RpgUtil.tree()
	if tree != null:
		tree.paused = true
	RpgUtil.emit(&"game_paused", [true])
	RpgMenuUtil.play_ui(&"sfx_sell")
	summary_opened.emit(_summary)
	return _summary

func _on_summary_closed() -> void:
	_summary = null
	var tree := RpgUtil.tree()
	if tree != null:
		tree.paused = false
	RpgUtil.emit(&"game_paused", [false])
