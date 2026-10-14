class_name RpgMarriage
extends Node
## Courting, the wedding and the spouse of a farm (T17.26). A child `Marriage` of the farm's
## mode, made by it like the events. It does nothing unless `enabled` (the option
## `starter_map.courtable` above 0; the mode's recipe sets `courting`), and then
## `RpgMarriage.current()` is null.
##
## * **Who can be courted** is `courtable` of a person's entry of people.json (the plan chose
##   them: rpggen/core/people_plan.py); for a person whose entry of the user's file has no such
##   key (a farm from before the card, or one that switched marriage on later) the planned
##   people's (`generated/data/people.json`).
## * **Courting.** Somebody who can be courted has at most eight hearts (RpgFriendship.cap_of)
##   until a **bouquet** is given (`interact` with the person while it is held, or `give`): from
##   eight hearts it is taken, the courting begins and the two last hearts are open. Below eight,
##   or to somebody who cannot be courted, it is not taken and the bouquet stays in the bag.
## * **The proposal.** At ten hearts a **pendant** given to the one who is courted is a yes: the
##   wedding is WEDDING_AFTER days later (the next day that is no festival from then on), a day
##   for everybody on the village square (RpgFarmEvents.add_event, kind `wedding`): the shop is
##   closed and the people gather there. Only one pendant is ever taken.
## * **The wedding's night** makes the engaged one the spouse (`spouse`). Nothing has to be done
##   on the day: a farmer who stays away is married all the same.
## * **The spouse** lives in the farmhouse: in the room of the bed (RpgBed.home), on the cell
##   beside the one the farmer wakes on (`home_cell`). Its day (`spouse_entry`) wins over the
##   person's own schedule (RpgSchedule.override, after a festival's): at home from 6:00, on its
##   own spot of the village square from 12:00 to 17:00 on SQUARE_DAYS when it is dry, at home
##   again, and asleep from 22:00 (not seen). Its NPC of the village is away while it is at home;
##   in the farmhouse it is an NPC made at run time of the person's scene (`Spouse`), which says
##   lines of its own: what it did this morning.
## * **The morning's help**, on some mornings (`help_on`; the first morning after the wedding is
##   always one of watering): it **waters** part of the plot (the dry cells of the farm's field
##   with a crop first, at most WATER_MOST), **feeds** the animals (fills every trough that is
##   empty), or **leaves something on the table** of the farmhouse (a produce of the season,
##   RpgSpouseTable, taken with `interact`). A wet day needs no watering, a farm without animals
##   no feeding: such a morning is a quiet one.
## * **Neglect.** At night everybody the farmer has met and did not talk to that day loses
##   DECAY_POINTS: friendship falls slowly, and nothing worse happens (a courting, an engagement
##   or a marriage is never undone). Children are not part of it.
## * **The shop** sells the bouquet and the pendant (a stock source of RpgFarmShop) while the
##   farmer is not married, where the game has their items (`game/data/items/`).
## * **The state** is in the flags of the game (`farm_marriage`), so the save has no new key:
##   `courting` (ids), `engaged`, `wedding` (the index of its day), `spouse`, `wed` (the index of
##   the wedding's day), `home` (the spouse's cell), `help` (this morning's: {day, kind, count,
##   item}) and `table` (what lies on the table: {day, item}). RpgCondition's atoms
##   `courting:<id>`, `engaged:<id>` and `spouse:<id>` read them.

## Somebody was courted, engaged or married, or the morning's help was done.
signal changed

const NODE_NAME := "Marriage"
## The game state carries the marriage of the running game under this meta (see `current`).
const STATE_META := &"rpg_farm_marriage"
const FLAG_ENTITY := "farm_marriage"
const COURTING_KEY := "courting"
const ENGAGED_KEY := "engaged"
const WEDDING_KEY := "wedding"
const SPOUSE_KEY := "spouse"
const WED_KEY := "wed"
const HOME_KEY := "home"
const HELP_KEY := "help"
const TABLE_KEY := "table"
const PLANNED_PEOPLE := "res://generated/data/people.json"
const COURTABLE := "courtable"
const BOUQUET := &"bouquet"
const PENDANT := &"pendant"
## The stages of a person (`stage_of`).
const COURTING := "courting"
const ENGAGED := "engaged"
const SPOUSE := "spouse"
## From how many hearts the bouquet is taken, and the pendant.
const COURT_HEARTS := 8
const PROPOSE_HEARTS := 10
## How many days after the proposal the wedding is.
const WEDDING_AFTER := 3
## What a day without a talk costs everybody the farmer has met.
const DECAY_POINTS := 2
## The most cells the spouse waters in a morning.
const WATER_MOST := 8
## The field of the farm (RpgField.resolved_id of the farm's map).
const FARM_FIELD := "farm"
## The kinds of the morning's help, and the week of them (by the day's index and the spouse).
const WATER := "water"
const FEED := "feed"
const TABLE := "table"
const QUIET := "quiet"
const HELP_WEEK: Array[String] = [WATER, FEED, TABLE, WATER, QUIET, TABLE, FEED]
## The spouse's day: the days of the week it spends the afternoon on the square, and the hours.
const SQUARE_DAYS: Array[int] = [1, 3]
const SQUARE_FROM := 12
const HOME_AGAIN := 17
const BED_HOUR := 22
## What the map of a spouse asleep is called: no map has it, so the spouse is not seen.
const ASLEEP := "#asleep"
const SPOUSE_NODE := "Spouse"
## After the bin and the festival's night: the wedding's night makes the spouse.
const NIGHT := RpgCalendar.NIGHT_SHOP + 60

## False: the farm has no marriage (see the top of the file).
@export var enabled: bool = false

## Person id -> `courtable` of the planned people, for whoever has no such key in the user's file.
var planned: Dictionary = {}

var _loaded := false
var _attached := false
var _before: Callable = Callable()  # the override of the schedules this one asks first
var _bound := false

# ------------------------------------------------------------------ finding it

## The marriage of the running game, or null: a game that is no farm, or a farm without it.
static func current() -> RpgMarriage:
	var state := RpgUtil.state()
	if state == null or not state.has_meta(STATE_META):
		return null
	var found: Variant = state.get_meta(STATE_META)
	if not is_instance_valid(found) or not (found is RpgMarriage):
		return null
	var out: RpgMarriage = found
	return out

## Listens to the calendar, to the maps and to the saves, caps the friendships and adds the
## shop's rows. The mode calls it once the calendar exists; a second call changes nothing, and
## so does a call while `enabled` is off.
func attach() -> void:
	var state := RpgUtil.state()
	if not enabled or state == null:
		return
	state.set_meta(STATE_META, self)
	table()
	var calendar := RpgCalendar.current()
	if calendar != null:
		calendar.on_night(NIGHT, _on_night)
		if not calendar.day_began.is_connected(_on_morning):
			calendar.day_began.connect(_on_morning)
	var bus := RpgUtil.events()
	if bus != null:
		if not bus.map_entered.is_connected(_on_map):
			bus.map_entered.connect(_on_map)
		if not bus.game_loaded.is_connected(_on_loaded):
			bus.game_loaded.connect(_on_loaded)
	RpgFriendship.cap_of = points_cap
	RpgFarmShop.add_stock_source(shop_rows)
	_attached = true

## The spouse's day wins over the person's own schedule, a festival's over both: the override
## of the schedules that is there (the events') is asked first. The mode calls it after the
## events attached.
func bind_schedules() -> void:
	if not _attached or _bound:
		return
	if RpgSchedule.override != schedule_override:
		_before = RpgSchedule.override
		RpgSchedule.override = schedule_override
	_bound = true

func _exit_tree() -> void:
	_let_go()

func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		_let_go()

## What the marriage set outside itself is as it was.
func _let_go() -> void:
	if not _attached:
		return
	_attached = false
	_bound = false
	if RpgSchedule.override == schedule_override:
		RpgSchedule.override = _before if _before.is_valid() else Callable()
	_before = Callable()
	if RpgFriendship.cap_of == points_cap:
		RpgFriendship.cap_of = Callable()
	RpgFarmShop.remove_stock_source(shop_rows)
	var state := RpgUtil.state()
	if state != null and state.has_meta(STATE_META):
		var found: Variant = state.get_meta(STATE_META)
		if not is_instance_valid(found) or found == self:
			state.remove_meta(STATE_META)

func _mode() -> RpgFarmMode:
	return get_parent() as RpgFarmMode

func _friends() -> RpgFriendship:
	return RpgFriendship.current()

# ------------------------------------------------------------------ who can be courted

## Reads the planned people's `courtable`, once. A test gives them with `add_planned` instead.
func table() -> void:
	if _loaded:
		return
	_loaded = true
	if not FileAccess.file_exists(PLANNED_PEOPLE):
		return
	var data := RpgUtil.to_dict(RpgUtil.restore_numbers(JSON.parse_string(FileAccess.get_file_as_string(PLANNED_PEOPLE))))
	add_planned(RpgUtil.to_array(data.get("people", [])))

## Takes `courtable` of the entries of planned people (what a test has instead of the file).
func add_planned(entries: Array) -> void:
	_loaded = true
	for raw: Variant in entries:
		var entry := RpgUtil.to_dict(raw)
		var id := RpgUtil.to_str(entry.get("id", ""))
		if id != "" and entry.has(COURTABLE) and not planned.has(id):
			planned[id] = RpgUtil.to_bool(entry[COURTABLE])

## True for a person who can be courted: `courtable` of its entry of people.json, else the plan's.
func is_courtable(id: String) -> bool:
	table()
	var friends := _friends()
	var entry := friends.person(id) if friends != null else {}
	if entry.has(COURTABLE):
		return RpgUtil.to_bool(entry[COURTABLE])
	return RpgUtil.to_bool(planned.get(id, false))

## The people who can be courted, in the order of people.json.
func courtable() -> Array[String]:
	var out: Array[String] = []
	var friends := _friends()
	if friends == null:
		return out
	for id in friends.order:
		if is_courtable(id):
			out.append(id)
	return out

# ------------------------------------------------------------------ the state

func _flag(key: String, fallback: Variant) -> Variant:
	var state := RpgUtil.state()
	return state.get_flag(FLAG_ENTITY, key, fallback) if state != null else fallback

func _put_flag(key: String, value: Variant) -> void:
	var state := RpgUtil.state()
	if state != null:
		state.set_flag(FLAG_ENTITY, key, value)

## Who the farmer courts (a bouquet was taken), in the order they were courted.
func courting() -> Array[String]:
	var out: Array[String] = []
	for raw: Variant in RpgUtil.to_array(_flag(COURTING_KEY, [])):
		out.append(RpgUtil.to_str(raw))
	return out

## Who the farmer is engaged to, or "".
func engaged() -> String:
	return RpgUtil.to_str(_flag(ENGAGED_KEY, ""))

## Who the farmer is married to, or "".
func spouse() -> String:
	return RpgUtil.to_str(_flag(SPOUSE_KEY, ""))

## The index of the wedding's day (RpgCalendar.today()), or -1 without an engagement.
func wedding_day() -> int:
	return RpgUtil.to_int(_flag(WEDDING_KEY, -1), -1) if engaged() != "" else -1

## Where a person stands with the farmer: SPOUSE, ENGAGED, COURTING or "".
func stage_of(id: String) -> String:
	if id == "":
		return ""
	if spouse() == id:
		return SPOUSE
	if engaged() == id:
		return ENGAGED
	return COURTING if courting().has(id) else ""

## The most points a person can have (RpgFriendship.cap_of): eight hearts for somebody who can
## be courted and is not courted yet, all ten for everybody else.
func points_cap(id: String) -> int:
	if is_courtable(id) and stage_of(id) == "":
		return COURT_HEARTS * RpgFriendship.HEART_POINTS
	return RpgFriendship.MAX_POINTS

# ------------------------------------------------------------------ the bouquet and the pendant

## True for the bouquet and the pendant: what RpgFriendship.gift hands over to `give`.
func is_token(item_id: StringName) -> bool:
	return item_id == BOUQUET or item_id == PENDANT

## The farmer gives a person the bouquet or the pendant (`take`: out of the bag). Returns the
## stage it began (COURTING or ENGAGED), or "" when it was not taken; the person says why, and
## nothing leaves the bag.
func give(id: String, item_id: StringName, take: bool = true) -> String:
	var friends := _friends()
	var state := RpgUtil.state()
	if friends == null or state == null or id == "" or not is_token(item_id):
		return ""
	if take and not state.inventory.has(item_id):
		return ""
	var name_of := friends.display_name(id)
	var why := refusal(id, item_id)
	if why != "":
		RpgUtil.notify(why)
		return ""
	if take:
		state.inventory.remove(item_id, 1)
	if item_id == BOUQUET:
		var list := courting()
		list.append(id)
		var plain: Array = []
		plain.assign(list)
		_put_flag(COURTING_KEY, plain)
		RpgUtil.notify(RpgFarmStrings.t("FARM_COURT_BEGIN", [name_of]))
		changed.emit()
		return COURTING
	var day := _wedding_date()
	_put_flag(ENGAGED_KEY, id)
	_put_flag(WEDDING_KEY, day)
	var date := RpgCalendar.date_of(day, _length())
	var events := RpgFarmEvents.current()
	if events != null:
		events.add_event({"id": "wedding_" + id, "kind": RpgFarmEvents.WEDDING, "person": id, "name": RpgFarmStrings.t("FARM_WEDDING_NAME", [name_of]), "season": date[1], "day": date[0], "year": date[2]})
	RpgUtil.notify(RpgFarmStrings.t("FARM_PROPOSE_YES", [name_of, RpgFarmStrings.season(RpgCalendar.season_name_of(date[1])), date[0]]))
	changed.emit()
	return ENGAGED

## Why a person does not take the bouquet or the pendant now, or "" when it would.
func refusal(id: String, item_id: StringName) -> String:
	var friends := _friends()
	var name_of := friends.display_name(id) if friends != null else id.capitalize()
	var hearts := friends.hearts(id) if friends != null else 0
	if item_id == BOUQUET:
		if not is_courtable(id):
			return RpgFarmStrings.t("FARM_COURT_NOBODY", [name_of])
		if stage_of(id) != "":
			return RpgFarmStrings.t("FARM_COURT_ALREADY", [name_of])
		if hearts < COURT_HEARTS:
			return RpgFarmStrings.t("FARM_COURT_NOT_YET", [name_of])
		return ""
	if spouse() != "" or engaged() != "":
		return RpgFarmStrings.t("FARM_PROPOSE_TAKEN")
	if stage_of(id) != COURTING:
		return RpgFarmStrings.t("FARM_PROPOSE_NOT_COURTING", [name_of])
	if hearts < PROPOSE_HEARTS:
		return RpgFarmStrings.t("FARM_PROPOSE_NOT_YET", [name_of])
	return ""

func _length() -> int:
	var calendar := RpgCalendar.current()
	return calendar.days_per_season if calendar != null else RpgCalendar.DAYS_PER_SEASON

## The index of the wedding's day: WEDDING_AFTER days from today, or the first day from then on
## that is no festival.
func _wedding_date() -> int:
	var calendar := RpgCalendar.current()
	var day := (calendar.today() if calendar != null else 0) + WEDDING_AFTER
	var events := RpgFarmEvents.current()
	if events == null:
		return day
	for i in 4 * _length():
		if RpgFarmEvents.festival_of(events.events_of(day)).is_empty():
			return day
		day += 1
	return day

## The rows of the farm's shop (a stock source of RpgFarmShop): the bouquet and the pendant, at
## the price of their items, while the farmer is not married and the game has them.
func shop_rows(_season_name: String = "") -> Array:
	var rows: Array = []
	var state := RpgUtil.state()
	if state == null or spouse() != "" or courtable().is_empty():
		return rows
	for item_id: StringName in [BOUQUET, PENDANT]:
		if state.items.has(item_id):
			rows.append({"item_id": String(item_id), "price": -1})
	return rows

# ------------------------------------------------------------------ the spouse's day

## The id of the map of the farmhouse: the map of the bed the farmer wakes at, "" before the
## game has seen a bed.
func house_id() -> String:
	var home := RpgBed.home(RpgUtil.state())
	return RpgUtil.to_str(home.get("map", "")).get_file().get_basename()

## The spouse's cell in the farmhouse ([x, y]), [] before the farmhouse was entered.
func home_cell() -> Array:
	return RpgUtil.to_array(_flag(HOME_KEY, []))

## Where the spouse is at `hour` of today: an entry of an RpgSchedule (see the top of the file),
## or {} without a spouse or before the game has seen a bed.
func spouse_entry(hour: int) -> Dictionary:
	var house := house_id()
	if spouse() == "" or house == "":
		return {}
	var now := RpgSchedule.day_hour(hour)
	if now >= BED_HOUR:
		return {"hour": BED_HOUR, "map": house + ASLEEP}
	var calendar := RpgCalendar.current()
	if now >= SQUARE_FROM and now < HOME_AGAIN and calendar != null and SQUARE_DAYS.has(calendar.weekday()) and RpgSchedule.weather() == "":
		var square := _square_of(spouse())
		if not square.is_empty():
			return square
	return {"hour": RpgSchedule.DAY_FIRST_HOUR, "map": house, "cell": home_cell(), "facing": "down"}

## The person's own spot of the square: the entry of its schedule that names one.
func _square_of(id: String) -> Dictionary:
	var friends := _friends()
	if friends == null:
		return {}
	for raw: Variant in friends.schedule_of(id):
		var own := RpgUtil.to_dict(raw)
		if RpgUtil.to_str(own.get("place", "")).begins_with("square") and RpgUtil.to_str(own.get("map", "")) != "":
			return {"hour": SQUARE_FROM, "map": RpgUtil.to_str(own["map"]), "place": RpgUtil.to_str(own["place"]), "facing": "down"}
	return {}

## RpgSchedule.override: a festival's place first (the override that was there), then the
## spouse's day; {} for anybody else.
func schedule_override(person: String, hour: int) -> Dictionary:
	if _before.is_valid():
		var forced := RpgUtil.to_dict(_before.call(person, hour))
		if not forced.is_empty():
			return forced
	if person == "" or person != spouse():
		return {}
	return spouse_entry(hour)

# ------------------------------------------------------------------ the night and the morning

## The night: everybody who was not talked to today loses a little, and the wedding's night
## makes the spouse. The calendar still shows the day that ended.
func _on_night(_day: int) -> void:
	var friends := _friends()
	if friends != null:
		for id in friends.met:
			if not friends.talked.has(id):
				friends.add_points(id, -DECAY_POINTS)
	var calendar := RpgCalendar.current()
	var who := engaged()
	if who != "" and calendar != null and calendar.today() >= wedding_day():
		marry(who)

## The engaged one is the spouse from now on (the wedding's night).
func marry(id: String) -> void:
	var calendar := RpgCalendar.current()
	_put_flag(SPOUSE_KEY, id)
	_put_flag(ENGAGED_KEY, "")
	_put_flag(WED_KEY, calendar.today() if calendar != null else 0)
	var friends := _friends()
	RpgUtil.notify(RpgFarmStrings.t("FARM_WEDDING_DONE", [friends.display_name(id) if friends != null else id.capitalize()]))
	changed.emit()

## The help of the morning with this index: the first morning after the wedding waters, the
## others go round HELP_WEEK by the day and the spouse. QUIET without a spouse.
func help_on(index: int) -> String:
	var id := spouse()
	if id == "":
		return QUIET
	if index == RpgUtil.to_int(_flag(WED_KEY, -10), -10) + 1:
		return WATER
	return HELP_WEEK[posmod(index + id.hash(), HELP_WEEK.size())]

## This morning's help as it was done: {day, kind, count, item}; {} on another day.
func help_today() -> Dictionary:
	var calendar := RpgCalendar.current()
	var kept := RpgUtil.to_dict(_flag(HELP_KEY, {}))
	if calendar == null or RpgUtil.to_int(kept.get("day", -1), -1) != calendar.today():
		return {}
	return kept

func _on_morning(_day: int) -> void:
	var calendar := RpgCalendar.current()
	if calendar != null and spouse() != "":
		do_help(calendar.today())
	refresh()

## Does the help of the morning with this index and says so. Returns what was done:
## {day, kind, count, item}; a wet day needs no watering, a farm without animals or with fed
## ones no feeding, and such a morning is QUIET.
func do_help(index: int) -> Dictionary:
	var kind := help_on(index)
	var done := {"day": index, "kind": kind, "count": 0, "item": ""}
	var mode := _mode()
	var friends := _friends()
	var who := friends.display_name(spouse()) if friends != null else spouse().capitalize()
	match kind:
		WATER:
			var wet := mode != null and mode.weather != null and mode.weather.is_wet()
			done["count"] = 0 if wet else water_part()
			if RpgUtil.to_int(done["count"]) > 0:
				RpgUtil.notify(RpgFarmStrings.t("FARM_SPOUSE_WATERED", [who, done["count"]]))
		FEED:
			done["count"] = feed_animals()
			if RpgUtil.to_int(done["count"]) > 0:
				RpgUtil.notify(RpgFarmStrings.t("FARM_SPOUSE_FED", [who]))
		TABLE:
			var item := table_item(index)
			if item != &"":
				done["item"] = String(item)
				done["count"] = 1
				_put_flag(TABLE_KEY, {"day": index, "item": String(item)})
				RpgUtil.notify(RpgFarmStrings.t("FARM_SPOUSE_TABLE", [who, RpgFarmStrings.item_name(item)]))
	if RpgUtil.to_int(done["count"]) <= 0:
		done["kind"] = QUIET
	_put_flag(HELP_KEY, done)
	changed.emit()
	return done

## Waters part of the farm's field, shown or not: the dry cells with a living crop first, then
## the other dry cells, in the order of their names, at most WATER_MOST and at least one when
## any is dry, about half of them. Returns how many it watered.
static func water_part(most: int = WATER_MOST) -> int:
	var state := RpgUtil.state()
	if state == null:
		return 0
	var saved := RpgUtil.to_dict(state.get_flag(RpgField.FLAG_ENTITY, FARM_FIELD, {}))
	var crops: Array[String] = []
	var bare: Array[String] = []
	for key: Variant in saved.keys():
		var entry := RpgUtil.to_dict(saved[key])
		if RpgUtil.to_bool(entry.get("w", false)):
			continue
		if RpgUtil.to_str(entry.get("crop", "")) != "" and not RpgUtil.to_bool(entry.get("dead", false)):
			crops.append(RpgUtil.to_str(key))
		else:
			bare.append(RpgUtil.to_str(key))
	crops.sort()
	bare.sort()
	var dry := crops + bare
	var count := mini(most, ceili(dry.size() * 0.5))
	for i in count:
		var entry := RpgUtil.to_dict(saved[dry[i]])
		entry["w"] = true
		entry["idle"] = 0
		saved[dry[i]] = entry
	if count <= 0:
		return 0
	state.set_flag(RpgField.FLAG_ENTITY, FARM_FIELD, saved)
	var shown := RpgField.current()
	if shown != null and shown.resolved_id() == FARM_FIELD:
		shown.load_state()
		shown.refresh()
	return count

## Fills every trough of the farm that is empty. Returns how many it filled.
static func feed_animals() -> int:
	var herd := RpgAnimalHouse.current()
	if herd == null:
		return 0
	var houses: Array[String] = []
	for row in RpgAnimalHouse.herd():
		var house := RpgUtil.to_str(row.get("house", ""))
		if house != "" and not houses.has(house):
			houses.append(house)
	var count := 0
	for house in houses:
		if not RpgAnimalHouse.trough_full(house) and herd.fill_trough(house):
			count += 1
	return count

## What the spouse leaves on the table on the morning with this index: a produce of a crop of
## the season that the game has, by the day; &"" when there is none.
func table_item(index: int) -> StringName:
	var mode := _mode()
	var state := RpgUtil.state()
	if mode == null or mode.crops == null or state == null:
		return &""
	var found: Array[StringName] = []
	for crop_id in mode.crops.of_season(RpgField.season_now()):
		var produce := StringName(RpgUtil.to_str(mode.crops.crop(crop_id).get("produce", "")))
		if produce != &"" and state.items.has(produce):
			found.append(produce)
	return found[posmod(index, found.size())] if not found.is_empty() else &""

## What lies on the table and has not been taken: its item, or &"".
func on_table() -> StringName:
	return StringName(RpgUtil.to_str(RpgUtil.to_dict(_flag(TABLE_KEY, {})).get("item", "")))

## The thing on the table goes into the bag. False when nothing lies there or the bag is full.
func take_table() -> bool:
	var item := on_table()
	var state := RpgUtil.state()
	if item == &"" or state == null:
		return false
	if state.inventory.add(item, 1) <= 0:
		RpgUtil.notify(RpgFarmStrings.t("FARM_FULL"))
		return false
	_put_flag(TABLE_KEY, {})
	RpgUtil.notify(RpgFarmStrings.t("FARM_TABLE_TOOK", [RpgFarmStrings.item_name(item)]))
	refresh()
	changed.emit()
	return true

# ------------------------------------------------------------------ the farmhouse

func _on_map(_id: StringName) -> void:
	refresh()

func _on_loaded(_slot: int) -> void:
	refresh()

func _shown_map() -> Node:
	var router := RpgUtil.router()
	return router.current_map if router != null else null

## True when `map` is the farmhouse: the map of the bed the farmer wakes at.
func is_house(map: Node) -> bool:
	var home := RpgBed.home(RpgUtil.state())
	return map != null and RpgUtil.to_str(home.get("map", "")) != "" and map.scene_file_path == RpgUtil.to_str(home["map"])

## Shows the farmhouse as the marriage has it (the map that is shown when null): the spouse at
## its place and what lies on the table. Returns the spouse's NPC, or null.
func refresh(map: Node = null) -> Node:
	if map == null:
		map = _shown_map()
	if not is_house(map):
		return null
	var cell := spouse_cell(map)
	if cell != Vector2i(-1, -1):
		_put_flag(HOME_KEY, [cell.x, cell.y])
	_show_table(map)
	return _show_spouse(map)

## The first TileMapLayer of a map with a tile set: the one RpgSchedule.cell_position counts by.
static func _layer_of(map: Node) -> TileMapLayer:
	for node in map.find_children("*", "TileMapLayer", true, false):
		var layer := node as TileMapLayer
		if layer.tile_set != null:
			return layer
	return null

## The spouse's cell in the farmhouse: beside the cell the farmer wakes on, east of it, else
## south, else west, on the floor of the room; (-1, -1) for a map without tiles or a game that
## has seen no bed.
func spouse_cell(map: Node) -> Vector2i:
	var home := RpgBed.home(RpgUtil.state())
	var layer := _layer_of(map)
	if home.is_empty() or layer == null:
		return Vector2i(-1, -1)
	var at: Vector2 = home["position"]
	var wake := layer.local_to_map(layer.to_local(at)) if layer.is_inside_tree() else layer.local_to_map(at - RpgUtil.world_position(layer))
	var floor_rect := layer.get_used_rect().grow(-1)
	for step: Vector2i in [Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]:
		if floor_rect.has_point(wake + step):
			return wake + step
	return wake

func _entities(map: Node) -> Node:
	var parent := map.get_node_or_null("YSorted/Entities")
	return parent if parent != null else map

## The NPC of the spouse in the farmhouse: made of the person's scene when there is none, put
## where its day says (RpgSchedule.place_now), with what it says this morning. Null without a
## spouse or a scene.
func _show_spouse(map: Node) -> Node:
	var parent := _entities(map)
	var old := parent.get_node_or_null(SPOUSE_NODE)
	var id := spouse()
	if id == "":
		if old != null:
			old.queue_free()
		return null
	if old == null:
		old = _make_spouse(id)
		if old == null:
			return null
		parent.add_child(old)
		var schedule := RpgSchedule.new()
		schedule.name = RpgSchedule.NODE_NAME
		schedule.person = id
		schedule.entries = [{"hour": RpgSchedule.DAY_FIRST_HOUR, "map": house_id(), "cell": home_cell(), "facing": "down"}]
		schedule.fade_s = 0.0
		old.add_child(schedule)
	if &"dialogue" in old:
		old.set(&"dialogue", spouse_dialogue())
	var plan := old.get_node_or_null(RpgSchedule.NODE_NAME) as RpgSchedule
	if plan != null and plan.actor == null:
		plan.setup()  # a map that is not in the tree yet (a test): the schedule finds its NPC
	elif plan != null:
		plan.place_now()
	return old

func _make_spouse(id: String) -> Node:
	var friends := _friends()
	var path := RpgUtil.to_str(friends.person(id).get("scene", "")) if friends != null else ""
	if path == "" or not ResourceLoader.exists(path):
		return null
	var packed := load(path) as PackedScene
	if packed == null:
		return null
	var npc := packed.instantiate()
	npc.name = SPOUSE_NODE
	if &"entity_id" in npc:
		npc.set(&"entity_id", "person_%s" % id)
	if &"facing" in npc:
		npc.set(&"facing", "down")
	return npc

## What the spouse says in the farmhouse: a line about this morning.
func spouse_dialogue() -> RpgDialogueResource:
	var friends := _friends()
	var id := spouse()
	var key := "FARM_SPOUSE_SAY_NONE"
	match RpgUtil.to_str(help_today().get("kind", "")):
		WATER:
			key = "FARM_SPOUSE_SAY_WATERED"
		FEED:
			key = "FARM_SPOUSE_SAY_FED"
		TABLE:
			key = "FARM_SPOUSE_SAY_TABLE"
	var line := RpgDialogueLine.new()
	line.id = &"spouse_morning"
	line.speaker = friends.display_name(id) if friends != null else id.capitalize()
	line.text = RpgFarmStrings.t(key)
	var res := RpgDialogueResource.new()
	res.lines.append(line)
	return res

## The NPC of the spouse in the map that is shown, or null.
func spouse_node() -> Node:
	var map := _shown_map()
	return _entities(map).get_node_or_null(SPOUSE_NODE) if map != null else null

## The table with what the spouse left on it, south of the spouse's cell (north when the room
## ends there); taken away when nothing lies there.
func _show_table(map: Node) -> void:
	var parent := _entities(map)
	var old := parent.get_node_or_null(RpgSpouseTable.NODE_NAME)
	var item := on_table()
	if old != null and (item == &"" or RpgUtil.to_str(old.get(&"item_id")) != String(item)):
		parent.remove_child(old)
		old.queue_free()
		old = null
	var cell := home_cell()
	if item == &"" or old != null or cell.size() != 2:
		return
	var layer := _layer_of(map)
	var at := Vector2i(RpgUtil.to_int(cell[0]), RpgUtil.to_int(cell[1])) + Vector2i(0, 1)
	if layer != null and not layer.get_used_rect().grow(-1).has_point(at):
		at -= Vector2i(0, 2)
	var tile := RpgUtil.map_tile_px(map)
	var diamond := RpgIso.footprint_of(map)
	var table_node := RpgSpouseTable.make(item, tile, diamond)
	table_node.taken.connect(func() -> void: take_table())
	parent.add_child(table_node)
	var spot := RpgSchedule.cell_position(map as Node2D, at)
	var foot := spot if diamond != Vector2i.ZERO else spot + Vector2(0.0, tile * 0.5 - 1.0)
	if table_node.is_inside_tree():
		table_node.global_position = foot
	else:
		var holder := parent as Node2D
		table_node.position = foot - (RpgUtil.world_position(holder) if holder != null else Vector2.ZERO)

## The table of the farmhouse that is shown, or null.
func table_node() -> RpgSpouseTable:
	var map := _shown_map()
	return _entities(map).get_node_or_null(RpgSpouseTable.NODE_NAME) as RpgSpouseTable if map != null else null
