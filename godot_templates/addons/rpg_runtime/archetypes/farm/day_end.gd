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
## * **Being defeated** (T17.24, `pass_out()`, which RpgFarmFight calls) ends the day as staying
##   up to 2:00 does, whatever the hour: the farmer wakes at the bed, with what that costs; the
##   toast says it was knocked out.
## * **Exhaustion** (T18.11, with `exhaustion` on: the mode's `exhaustion_ends_day`, the option
##   *Exhaustion ends the day*): trying a tool at zero energy a second time says the farmer is
##   exhausted and offers to go home (to the bed, the day goes on); a third time, or once
##   EXHAUST_MINUTES of game time have passed at zero, the farmer collapses and the day ends as
##   at 2:00 (`collapse()`).
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
## Game minutes at zero energy before the farmer collapses (T18.11).
const EXHAUST_MINUTES := 60
## The event of the choice *Go home* of the offer (a dialogue event `emit:<this>`).
const GO_HOME_EVENT := "farm_go_home"
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
## True: working at zero energy ends the day (T18.11); the mode sets it.
var exhaustion := false
## True when the last night ended with the farmer collapsing from exhaustion.
var collapsed := false
## Tries of a tool at zero energy, and game minutes spent at zero, since the energy last ran out.
var tries := 0
var minutes_at_zero := 0
var _collapsing := false

var _sleeping := false
## True while a defeat ends the day (`pass_out`), and for the morning after it (`knocked_out`).
var _fainting := false
var knocked_out := false
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
		if not calendar.minute_passed.is_connected(_on_minute):
			calendar.minute_passed.connect(_on_minute)
	var bus := RpgUtil.events()
	if bus != null:
		if not bus.game_saved.is_connected(_on_slot_used):
			bus.game_saved.connect(_on_slot_used)
		if not bus.game_loaded.is_connected(_on_loaded):
			bus.game_loaded.connect(_on_loaded)
		if not bus.dialogue_event.is_connected(_on_dialogue_event):
			bus.dialogue_event.connect(_on_dialogue_event)

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

## Ends the day as staying up to 2:00 does, at any hour (T17.24: the farmer was defeated). False
## when it cannot (no calendar, a night that is still running, the summary still open).
func pass_out() -> bool:
	var calendar := RpgCalendar.current()
	if calendar == null or _sleeping or _fainting or is_summary_open():
		return false
	_fainting = true
	calendar.end_day()
	_fainting = false
	return true

## Ends the day as staying up to 2:00 does, at any hour (T18.11: the farmer collapsed from
## exhaustion). False when it cannot.
func collapse() -> bool:
	var calendar := RpgCalendar.current()
	if calendar == null or _sleeping or _fainting or _collapsing or is_summary_open():
		return false
	_collapsing = true
	calendar.end_day()
	_collapsing = false
	return true

# ------------------------------------------------------------------ exhaustion (T18.11)

## A tool was tried at zero energy (the farmer calls it). With `exhaustion` on: the second try
## offers to go home, the third ends the day. Returns true when the day ended.
func tried_exhausted() -> bool:
	if not exhaustion:
		return false
	tries += 1
	if tries >= 3:
		return collapse()
	if tries == 2:
		RpgUtil.notify(RpgFarmStrings.t("FARM_EXHAUSTED"))
		offer_home()
	return false

## Asks whether to go home (the dialogue box, a choice); *Go home* puts the farmer at the bed.
func offer_home() -> void:
	var box := RpgUtil.service(&"rpg_dialogue_box")
	if box == null or not box.has_method("open") or box.call("is_open"):
		return
	var line := RpgDialogueLine.new()
	line.id = &"exhausted"
	line.text = RpgFarmStrings.t("FARM_GO_HOME_ASK")
	var home := RpgDialogueChoice.new()
	home.text = RpgFarmStrings.t("FARM_GO_HOME")
	home.next = &"home"
	var stay := RpgDialogueChoice.new()
	stay.text = RpgFarmStrings.t("FARM_NOT_YET")
	stay.next = &"stay"
	var choices: Array[RpgDialogueChoice] = [home, stay]
	line.choices = choices
	var going := RpgDialogueLine.new()
	going.id = &"home"
	going.text = RpgFarmStrings.t("FARM_GOING_HOME")
	going.events = PackedStringArray(["emit:" + GO_HOME_EVENT])
	var staying := RpgDialogueLine.new()  # never shown: its condition is false, the box closes
	staying.id = &"stay"
	staying.condition = "flag:farm.%s" % GO_HOME_EVENT
	var res := RpgDialogueResource.new()
	var lines: Array[RpgDialogueLine] = [line, going, staying]
	res.lines = lines
	box.call("open", res, _the_farmer())

func _on_dialogue_event(event_name: String, _arg: String) -> void:
	if event_name == GO_HOME_EVENT:
		_wake_at_bed()

## Counts the minutes at zero energy; at EXHAUST_MINUTES the farmer collapses.
func _on_minute(_minute: int) -> void:
	if not exhaustion:
		return
	var energy := _energy()
	if energy == null or not energy.is_exhausted():
		tries = 0
		minutes_at_zero = 0
		return
	minutes_at_zero += 1
	if minutes_at_zero >= EXHAUST_MINUTES:
		collapse()

func is_summary_open() -> bool:
	return _summary != null and is_instance_valid(_summary)

## The summary that is shown, or null.
func summary() -> RpgDaySummary:
	return _summary if is_summary_open() else null

## The night listener: the calendar still shows the day that ended, and its minute says whether
## the clock ended it (2:00) or somebody else did.
func _on_night(_day: int) -> void:
	var calendar := RpgCalendar.current()
	knocked_out = _fainting
	collapsed = _collapsing
	if _sleeping:
		_how = SLEPT
	elif _fainting or _collapsing or (calendar != null and calendar.minute >= RpgCalendar.DAY_END):
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
	tries = 0
	minutes_at_zero = 0
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
	RpgFarmSounds.play(RpgFarmSounds.ROOSTER)
	_finish_morning(how)

## What follows the night, in its order: the farmer is at the bed, the game is saved, the
## summary is shown and closed, the save screen is offered. It waits only for a map change and
## for the summary, so a morning without either is done when this returns.
func _finish_morning(how: String) -> void:
	if how != ENDED:
		await _wake_at_bed()
		save_night()
	if how == PASSED_OUT and knocked_out:
		var short := RpgRealtimeText.t("UI_GOLD_SHORT", [], RpgStrings.KEYS)
		RpgUtil.notify(RpgFarmCaveStrings.t("FARM_KNOCKED_OUT_LOST", [money_lost, short]) if money_lost > 0 else RpgFarmCaveStrings.t("FARM_KNOCKED_OUT"))
	elif how == PASSED_OUT and collapsed:
		var short := RpgRealtimeText.t("UI_GOLD_SHORT", [], RpgStrings.KEYS)
		RpgUtil.notify(RpgFarmStrings.t("FARM_COLLAPSED_LOST", [money_lost, short]) if money_lost > 0 else RpgFarmStrings.t("FARM_COLLAPSED"))
	elif how == PASSED_OUT:
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
