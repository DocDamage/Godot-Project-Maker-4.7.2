class_name RpgFarmEvents
extends Node
## The days of a farm's year that are not like the others (T17.25): a **festival** a season, the
## **birthdays** of the people, and whatever the game adds at run time (`add_event`: a wedding,
## T17.26). A child of the farm's mode (`Events`), made by it like the weather and the end of
## the day. It does nothing unless `enabled` (the option `starter_map.festivals`; the mode's
## recipe sets it), and then `RpgFarmEvents.current()` is null: no page, no button, no day off.
##
## * **The events** are data: `game/data/events.json` (the user's: `user_path`, which the mode
##   names) and, for the ids that file does not list, `generated/data/events.json` (the plan's,
##   written on every build). An entry `{"id": ..., "removed": true}` of the user's file takes
##   one away. An event is a Dictionary:
##     id, kind, name      `kind` is what there is to do (the constants below); a kind nobody
##                         knows is a gathering with nothing to do
##     season, day         the season by its name ("spring") or its number, the day of it. A day
##                         the season of this game no longer has is folded into it (`day_in`)
##     year                only in this year; every year without it
##     from, to            the hours the people stand at `place` (9 to 20 without them)
##     map, place          the map (`RpgMapRoot.map_id`) and the marker the people gather at;
##                         each takes the spot of it their own schedule names (`square_3`)
##     shop_closed         false: the shop keeps its hours on this day
##     spots, each         an egg hunt: the markers the eggs lie at, what one pays
##     table               a contest, a feast: the marker the table stands at
##     goal, prize         from how many (or which price) on the prize is won: {gold} or
##                         {item, qty}
##     judge               a produce contest: "price" (the dearest thing shipped this season)
##                         or "count" (how many things)
##     points              a feast: the friendship everybody gains
## * **A festival day**: the shop is closed all day and says why (`RpgFarmShop.day_off`), the
##   people stand on the square from `from` to `to` whatever their schedules and the weather say
##   (`RpgSchedule.override`), `festival_began` is emitted in the morning and `festival_ended`
##   in the night, and the map the event names has the eggs or the table of the day on its
##   markers (RpgFestivalThing; where a village has no such marker, around `place`).
## * **What there is to do.** An egg hunt: each egg is found with `interact`, pays `each`, and
##   the last one of `goal` pays the prize. A fishing count: every fish that is caught that day
##   counts, and the one that makes `goal` pays the prize. A produce contest: `interact` with
##   the table has what the bin sold this season judged, once. A feast: `interact` with the
##   table while a food is held gives it, once, and everybody's friendship grows.
## * **Birthdays**: `birthday` of a person's entry of people.json (`{season, day}`); for
##   somebody whose entry has none (a farm from before the card), the planned people's
##   (`generated/data/people.json`). RpgFriendship asks `birthday_gift_open`.
## * **The state** is in the flags of the game (`farm_events`), so the save has no new key:
##   `added` (the events `add_event` added), `today` (what was found, caught or judged on the
##   festival of the day: it is forgotten when the day is another) and `birthday_gifts` (who
##   had theirs today).
## * **The day before** a festival the weather's sign says so (`tomorrow_text`) and so do the
##   people (the dialogue atom `festival_tomorrow`; RpgCondition finds this node through the
##   game state, since the script is in no project but a farm's).
## * **The calendar** (RpgCalendarPage) lists a season: `season_rows`. `open_calendar()` shows
##   it over the paused game (the wall calendar of the farmhouse, RpgWallCalendar); the pause
##   menu has it as a page.

## A festival's morning and its night. `event` is the entry of the day.
signal festival_began(event: Dictionary)
signal festival_ended(event: Dictionary)
## What was found, caught or judged changed, or an event was added or taken away.
signal changed

const NODE_NAME := "Events"
const PLANNED_PATH := "res://generated/data/events.json"
const PLANNED_PEOPLE := "res://generated/data/people.json"
## The game state carries the events of the running game under this meta (see `current`).
const STATE_META := &"rpg_farm_events"
const FLAG_ENTITY := "farm_events"
const ADDED_KEY := "added"
const TODAY_KEY := "today"
const GIFTS_KEY := "birthday_gifts"
const EGG_HUNT := "egg_hunt"
const FISHING_COUNT := "fishing_count"
const PRODUCE_CONTEST := "produce_contest"
const FEAST := "feast"
const GATHERING := "gathering"
const WEDDING := "wedding"
## What `events_on` lists somebody's birthday as. Not a kind of events.json.
const BIRTHDAY := "birthday"
const JUDGE_COUNT := "count"
const FROM_HOUR := 9
const TO_HOUR := 20
const PLACE := "square"
## After the bin was sold (RpgCalendar.NIGHT_SHOP): the night of a festival ends it.
const NIGHT := RpgCalendar.NIGHT_SHOP + 50
## Over the HUD and the morning's summary, under the menus (60).
const PAGE_LAYER := 56
const PAGE_LAYER_NODE := "CalendarLayer"
const FOUND_SOUND := &"sfx_harvest"
const PRIZE_SOUND := &"sfx_sell"

## The user's file of the running game. Set by the farm's mode from its `data_dir`: a runtime
## script names no path of the game itself.
static var user_path := ""

## False: the farm has no festivals and no birthdays (see the top of the file).
@export var enabled: bool = false
## False: the events of the files and the birthdays are left out, and only what `add_event`
## adds is a day for everybody. A farm with marriage and without festivals (T17.26) has its
## wedding this way: the mode turns `enabled` on for it and this off.
@export var with_files: bool = true

## The events of the files, in their order, and the ids the user's file took away.
var events: Array[Dictionary] = []
var removed: Array[String] = []
## Person id -> {season, day} of the planned people, for whoever has none in the user's file.
var planned_birthdays: Dictionary = {}

var _loaded := false
var _attached := false
var _things: Array = []  # the RpgFestivalThings of the map that is shown (untyped: may be freed)
var _layer: CanvasLayer = null
var _page: RpgCalendarPage = null

# ------------------------------------------------------------------ finding it

## The events of the running game, or null: a game that is no farm, or a farm without them.
static func current() -> RpgFarmEvents:
	var state := RpgUtil.state()
	if state == null or not state.has_meta(STATE_META):
		return null
	var found: Variant = state.get_meta(STATE_META)
	if not is_instance_valid(found) or not (found is RpgFarmEvents):
		return null
	var out: RpgFarmEvents = found
	return out

## Listens to the calendar, to the maps and to the saves, and tells the shop and the schedules
## of the festivals. The mode calls it once the calendar exists; a second call changes nothing,
## and so does a call while `enabled` is off.
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
	var mode := _mode()
	if mode != null and mode.fishing != null and not mode.fishing.caught.is_connected(_on_caught):
		mode.fishing.caught.connect(_on_caught)
	RpgSchedule.override = schedule_override
	RpgFarmShop.day_off = shop_day_off
	_attached = true

func _exit_tree() -> void:
	_let_go()

func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		_let_go()

## What the events set outside themselves is as it was.
func _let_go() -> void:
	if not _attached:
		return
	_attached = false
	if RpgSchedule.override == schedule_override:
		RpgSchedule.override = Callable()
	if RpgFarmShop.day_off == shop_day_off:
		RpgFarmShop.day_off = Callable()
	var state := RpgUtil.state()
	if state != null and state.has_meta(STATE_META):
		var found: Variant = state.get_meta(STATE_META)
		if not is_instance_valid(found) or found == self:
			state.remove_meta(STATE_META)

func _mode() -> RpgFarmMode:
	return get_parent() as RpgFarmMode

# ------------------------------------------------------------------ the table

## Reads the files, once. A test gives the entries with `add_list` instead.
func table() -> void:
	if _loaded:
		return
	_loaded = true
	if not with_files:
		return
	add_file(user_path)
	add_file(PLANNED_PATH)
	add_birthdays(PLANNED_PEOPLE)

## Adds the events of a file that are not there yet. A file that is missing adds nothing.
func add_file(path: String) -> void:
	if path == "" or not FileAccess.file_exists(path):
		return
	var data := RpgUtil.to_dict(RpgUtil.restore_numbers(JSON.parse_string(FileAccess.get_file_as_string(path))))
	add_list(RpgUtil.to_array(data.get("events", [])))

## Adds entries (what a test has instead of a file). One without an id, or whose id is there
## already or was removed, is left out; one that says `"removed": true` adds nothing and keeps
## every later entry of its id out.
func add_list(entries: Array) -> void:
	_loaded = true
	for raw: Variant in entries:
		var entry := RpgUtil.to_dict(raw)
		var id := RpgUtil.to_str(entry.get("id", ""))
		if id == "" or removed.has(id) or not event(id).is_empty():
			continue
		if RpgUtil.to_bool(entry.get("removed", false)):
			removed.append(id)
			continue
		if season_index(entry.get("season")) < 0 or RpgUtil.to_int(entry.get("day", 0)) < 1:
			push_warning("[RPG-WORLD] the event %s has no season and day" % id)
			continue
		events.append(entry)
	changed.emit()

## Reads the birthdays of the planned people of a file (generated/data/people.json).
func add_birthdays(path: String) -> void:
	if path == "" or not FileAccess.file_exists(path):
		return
	var data := RpgUtil.to_dict(RpgUtil.restore_numbers(JSON.parse_string(FileAccess.get_file_as_string(path))))
	for raw: Variant in RpgUtil.to_array(data.get("people", [])):
		var entry := RpgUtil.to_dict(raw)
		var id := RpgUtil.to_str(entry.get("id", ""))
		var born := RpgUtil.to_dict(entry.get("birthday", {}))
		if id != "" and not born.is_empty() and not planned_birthdays.has(id):
			planned_birthdays[id] = born

## The event of the files with this id, or {}.
func event(id: String) -> Dictionary:
	for entry in events:
		if RpgUtil.to_str(entry.get("id", "")) == id:
			return entry
	return {}

# ------------------------------------------------------------------ dates

## The number of a season given by its name ("spring") or its number; -1 for neither.
static func season_index(value: Variant) -> int:
	if value is String or value is StringName:
		return RpgCalendar.SEASONS.find(str(value))
	if value is int or value is float:
		var number := RpgUtil.to_int(value, -1)
		return number if number >= 0 and number < RpgCalendar.SEASONS.size() else -1
	return -1

## The day of a season of `length` days a planned day is: itself while the season has it, else
## folded into it week for week (26 is 12 of 14 days and 5 of 7), so the day of the week stays.
static func day_in(day: int, length: int) -> int:
	var days := RpgCalendar.season_length(length)
	return (maxi(1, day) - 1) % days + 1

func _length() -> int:
	var calendar := RpgCalendar.current()
	return calendar.days_per_season if calendar != null else RpgCalendar.DAYS_PER_SEASON

## True when an event (or a birthday) falls on this date.
func falls_on(entry: Dictionary, day: int, season: int, year: int) -> bool:
	if season_index(entry.get("season")) != season or day_in(RpgUtil.to_int(entry.get("day", 0)), _length()) != day:
		return false
	var only := RpgUtil.to_int(entry.get("year", 0))
	return only <= 0 or only == year

## Everything of a date, in this order: the events of the files, the events that were added,
## and the birthdays (each `{kind: BIRTHDAY, person, name, season, day}`).
func events_on(day: int, season: int, year: int) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	table()
	for entry in events:
		if falls_on(entry, day, season, year):
			out.append(entry)
	for entry in added():
		if falls_on(entry, day, season, year):
			out.append(entry)
	for id in birthdays_on(day, season):
		out.append({"id": "birthday_" + id, "kind": BIRTHDAY, "person": id, "name": birthday_name(id), "season": season, "day": day})
	return out

## Everything of the day with this index (`RpgCalendar.today()`).
func events_of(index: int) -> Array[Dictionary]:
	var date := RpgCalendar.date_of(index, _length())
	return events_on(date[0], date[1], date[2])

func today() -> Array[Dictionary]:
	var calendar := RpgCalendar.current()
	if calendar == null:
		return []
	return events_of(calendar.today())

func tomorrow() -> Array[Dictionary]:
	var calendar := RpgCalendar.current()
	if calendar == null:
		return []
	return events_of(calendar.today() + 1)

## The first of `list` that is a day for everybody (not a birthday), or {}.
static func festival_of(list: Array[Dictionary]) -> Dictionary:
	for entry in list:
		if RpgUtil.to_str(entry.get("kind", "")) != BIRTHDAY:
			return entry
	return {}

## The festival (or the wedding, or whatever was added) of today, or {}.
func festival() -> Dictionary:
	return festival_of(today())

func is_festival() -> bool:
	return not festival().is_empty()

func festival_tomorrow() -> Dictionary:
	return festival_of(tomorrow())

## True when today has an event of this kind (`event:<kind>` in a dialogue).
func has_kind(kind: String) -> bool:
	for entry in today():
		if RpgUtil.to_str(entry.get("kind", "")) == kind:
			return true
	return false

## The name of an event as a sentence shows it: its `name` (a translation key or plain text),
## else its id made readable.
static func event_name(entry: Dictionary) -> String:
	var text := RpgUtil.to_str(entry.get("name", ""))
	if text == "":
		return RpgUtil.to_str(entry.get("id", "")).capitalize()
	return String(TranslationServer.translate(text))

## The hours the people stand at the place of an event: [from, to).
static func hours_of(entry: Dictionary) -> Array[int]:
	var from := clampi(RpgUtil.to_int(entry.get("from", FROM_HOUR), FROM_HOUR), RpgSchedule.DAY_FIRST_HOUR, 23)
	var to := clampi(RpgUtil.to_int(entry.get("to", TO_HOUR), TO_HOUR), from + 1, 24)
	return [from, to]

# ------------------------------------------------------------------ events added at run time

## The events `add_event` added, in the order they were added.
func added() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var state := RpgUtil.state()
	if state == null:
		return out
	for raw: Variant in RpgUtil.to_array(state.get_flag(FLAG_ENTITY, ADDED_KEY, [])):
		var entry := RpgUtil.to_dict(raw)
		if RpgUtil.to_str(entry.get("id", "")) != "":
			out.append(entry)
	return out

func _store_added(list: Array[Dictionary]) -> void:
	var state := RpgUtil.state()
	if state != null:
		var plain: Array = []
		plain.assign(list)
		state.set_flag(FLAG_ENTITY, ADDED_KEY, plain)

## Adds an event to the year of this game, kept with the saved game: `{kind, season, day}` and
## whatever else an event has (`year` for one that happens once, `name`, `place`, `from`, `to`,
## `shop_closed`, anything the caller wants to find again). It is on the calendar from now on
## and, like a festival, a day off for the shop on which the people gather at its `place` (the
## square of the village the planned festivals name, without one). Returns its id (the `id` it
## was given, else one made of its kind and its date), or "" for an entry without a kind or
## with a date that is none. An event of the same id is replaced.
func add_event(entry: Dictionary) -> String:
	var season := season_index(entry.get("season"))
	var day := RpgUtil.to_int(entry.get("day", 0))
	var kind := RpgUtil.to_str(entry.get("kind", ""))
	if kind == "" or kind == BIRTHDAY or season < 0 or day < 1:
		return ""
	var kept := entry.duplicate(true)
	kept["season"] = RpgCalendar.SEASONS[season]
	kept["day"] = day
	var year := RpgUtil.to_int(entry.get("year", 0))
	if year > 0:
		kept["year"] = year
	else:
		kept.erase("year")
	var id := RpgUtil.to_str(entry.get("id", ""))
	if id == "":
		id = "%s_%d_%s_%d" % [kind, year, kept["season"], day]
	kept["id"] = id
	if not kept.has("place"):
		kept["place"] = _village_place()
	if not kept.has("map"):
		kept["map"] = _village_map()
	var list := added()
	for i in range(list.size() - 1, -1, -1):
		if RpgUtil.to_str(list[i].get("id", "")) == id:
			list.remove_at(i)
	list.append(kept)
	_store_added(list)
	refresh()
	changed.emit()
	return id

## Takes an added event away again. False when no such event was added.
func remove_event(id: String) -> bool:
	var list := added()
	for i in list.size():
		if RpgUtil.to_str(list[i].get("id", "")) == id:
			list.remove_at(i)
			_store_added(list)
			refresh()
			changed.emit()
			return true
	return false

## Where the planned festivals gather: the map and the place of the first that names one.
func _village_map() -> String:
	table()
	for entry in events:
		if RpgUtil.to_str(entry.get("map", "")) != "":
			return RpgUtil.to_str(entry["map"])
	return ""

func _village_place() -> String:
	table()
	for entry in events:
		if RpgUtil.to_str(entry.get("place", "")) != "":
			return RpgUtil.to_str(entry["place"])
	return PLACE

# ------------------------------------------------------------------ birthdays

func _friends() -> RpgFriendship:
	return RpgFriendship.current()

## The birthday of a person: `{season: int, day: int}` (the day as this game's seasons have
## it), or {} for somebody without one. The entry of people.json counts; a person whose entry
## has no `birthday` at all has the planned one.
func birthday_of(id: String) -> Dictionary:
	table()
	if not with_files:
		return {}
	var friends := _friends()
	var entry := friends.person(id) if friends != null else {}
	var born := RpgUtil.to_dict(entry.get("birthday", {})) if entry.has("birthday") else RpgUtil.to_dict(planned_birthdays.get(id, {}))
	var season := season_index(born.get("season"))
	var day := RpgUtil.to_int(born.get("day", 0))
	if season < 0 or day < 1:
		return {}
	return {"season": season, "day": day_in(day, _length())}

## Whose birthday a date is: the people of people.json in its order, then anybody only the
## plan knows.
func birthdays_on(day: int, season: int) -> Array[String]:
	var out: Array[String] = []
	var friends := _friends()
	var ids: Array[String] = []
	if friends != null:
		ids.append_array(friends.order)
	else:
		for id: Variant in planned_birthdays.keys():
			ids.append(RpgUtil.to_str(id))
	for id in ids:
		var born := birthday_of(id)
		if not born.is_empty() and RpgUtil.to_int(born["season"]) == season and RpgUtil.to_int(born["day"]) == day:
			out.append(id)
	return out

func is_birthday(id: String) -> bool:
	var calendar := RpgCalendar.current()
	var born := birthday_of(id)
	return calendar != null and not born.is_empty() and RpgUtil.to_int(born["season"]) == calendar.season and RpgUtil.to_int(born["day"]) == calendar.day

func _person_name(id: String) -> String:
	var friends := _friends()
	return friends.display_name(id) if friends != null else id.capitalize()

## "Anna's birthday".
func birthday_name(id: String) -> String:
	return RpgFarmStrings.t("FARM_BIRTHDAY_OF", [_person_name(id)])

## "Birthday: spring 12", or "" for somebody without one.
func birthday_text(id: String) -> String:
	var born := birthday_of(id)
	if born.is_empty():
		return ""
	return RpgFarmStrings.t("FARM_PEOPLE_BIRTHDAY", [RpgFarmStrings.season(RpgCalendar.season_name_of(RpgUtil.to_int(born["season"]))), RpgUtil.to_int(born["day"])])

func _gifts_today() -> Array:
	var state := RpgUtil.state()
	var calendar := RpgCalendar.current()
	if state == null or calendar == null:
		return []
	var kept := RpgUtil.to_dict(state.get_flag(FLAG_ENTITY, GIFTS_KEY, {}))
	if RpgUtil.to_int(kept.get("day", -1), -1) != calendar.today():
		return []
	return RpgUtil.to_array(kept.get("people", []))

## True on the birthday of a person who has not had the gift of the day yet (RpgFriendship).
func birthday_gift_open(id: String) -> bool:
	return is_birthday(id) and not _gifts_today().has(id)

## The gift of the day was given.
func note_birthday_gift(id: String) -> void:
	var state := RpgUtil.state()
	var calendar := RpgCalendar.current()
	if state == null or calendar == null:
		return
	var people := _gifts_today()
	if not people.has(id):
		people.append(id)
	state.set_flag(FLAG_ENTITY, GIFTS_KEY, {"day": calendar.today(), "people": people})

# ------------------------------------------------------------------ the shop, the people, the sign

## What the keeper of the shop says on a day off, or "" (`RpgFarmShop.day_off`).
func shop_day_off() -> String:
	var entry := festival()
	if entry.is_empty() or not RpgUtil.to_bool(entry.get("shop_closed", true), true):
		return ""
	return RpgFarmStrings.t("FARM_SHOP_FESTIVAL", [event_name(entry)])

## The marker of an event a person stands at: the spot of its `place` the person's own
## schedule names on that map (`square_3`), else the place itself.
func spot_of(person: String, entry: Dictionary) -> String:
	var place := RpgUtil.to_str(entry.get("place", ""))
	var map_id := RpgUtil.to_str(entry.get("map", ""))
	var friends := _friends()
	if friends == null or place == "":
		return place
	for raw: Variant in friends.schedule_of(person):
		var own := RpgUtil.to_dict(raw)
		var named := RpgUtil.to_str(own.get("place", ""))
		if (named == place or named.begins_with(place + "_")) and RpgUtil.to_str(own.get("map", "")) == map_id:
			return named
	return place

## Where a person is at `hour` of a festival: an entry of an RpgSchedule that wins over the
## person's own, or {} outside the hours of the event and on a day like any other
## (`RpgSchedule.override`).
func schedule_override(person: String, hour: int) -> Dictionary:
	var entry := festival()
	if entry.is_empty() or RpgUtil.to_str(entry.get("place", "")) == "":
		return {}
	var hours := hours_of(entry)
	var now := RpgSchedule.day_hour(hour)
	if now < hours[0] or now >= hours[1]:
		return {}
	return {"hour": hours[0], "map": RpgUtil.to_str(entry.get("map", "")), "place": spot_of(person, entry), "facing": "down"}

## What the weather's sign adds on the day before a festival, or "".
func tomorrow_text() -> String:
	var entry := festival_tomorrow()
	if entry.is_empty():
		return ""
	var key := "FARM_FESTIVAL_TOMORROW" if RpgUtil.to_bool(entry.get("shop_closed", true), true) else "FARM_FESTIVAL_TOMORROW_OPEN"
	return RpgFarmStrings.t(key, [event_name(entry)])

# ------------------------------------------------------------------ what was done today

## What was done on the festival of today: `{day, id, found: [spot], count, done}`; a fresh one
## when the flags hold another day's or another event's.
func _today_state() -> Dictionary:
	var state := RpgUtil.state()
	var calendar := RpgCalendar.current()
	var id := RpgUtil.to_str(festival().get("id", ""))
	var fresh := {"day": calendar.today() if calendar != null else -1, "id": id, "found": [], "count": 0, "done": false}
	if state == null or calendar == null or id == "":
		return fresh
	var kept := RpgUtil.to_dict(state.get_flag(FLAG_ENTITY, TODAY_KEY, {}))
	if RpgUtil.to_int(kept.get("day", -1), -1) != calendar.today() or RpgUtil.to_str(kept.get("id", "")) != id:
		return fresh
	fresh["found"] = RpgUtil.to_array(kept.get("found", [])).duplicate()
	fresh["count"] = RpgUtil.to_int(kept.get("count", 0))
	fresh["done"] = RpgUtil.to_bool(kept.get("done", false))
	return fresh

func _store_today(value: Dictionary) -> void:
	var state := RpgUtil.state()
	if state != null and RpgUtil.to_str(value.get("id", "")) != "":
		state.set_flag(FLAG_ENTITY, TODAY_KEY, value)
		changed.emit()

## The spots whose egg was found today.
func found() -> Array[String]:
	var out: Array[String] = []
	for raw: Variant in RpgUtil.to_array(_today_state()["found"]):
		out.append(RpgUtil.to_str(raw))
	return out

## How many were counted today: the eggs that were found, or the fish that were caught.
func count() -> int:
	return RpgUtil.to_int(_today_state()["count"])

## True once the prize of today was won, the contest judged or the dish brought.
func is_done() -> bool:
	return RpgUtil.to_bool(_today_state()["done"])

## From how many on the prize of an event is won (all the eggs of a hunt that names no number).
static func goal_of(entry: Dictionary) -> int:
	var fallback := 1
	if RpgUtil.to_str(entry.get("kind", "")) == EGG_HUNT:
		fallback = maxi(1, RpgUtil.to_array(entry.get("spots", [])).size())
	return maxi(1, RpgUtil.to_int(entry.get("goal", fallback), fallback))

## Pays the prize of an event (`{gold}`, `{item, qty}` or both) and returns it in words
## ("150 G", "Turnip seeds x5"); "" for an event without one, or when the bag has no room.
func give_prize(entry: Dictionary) -> String:
	var state := RpgUtil.state()
	var prize := RpgUtil.to_dict(entry.get("prize", {}))
	if state == null or prize.is_empty():
		return ""
	var parts: PackedStringArray = []
	var gold := maxi(0, RpgUtil.to_int(prize.get("gold", 0)))
	if gold > 0:
		state.gold += gold
		parts.append(money_text(gold))
	var item := StringName(RpgUtil.to_str(prize.get("item", "")))
	var qty := maxi(1, RpgUtil.to_int(prize.get("qty", 1), 1))
	if item != &"" and state.items.has(item):
		var got: int = state.inventory.add(item, qty)
		if got > 0:
			parts.append(RpgFarmStrings.t("FARM_PRIZE_ITEM", [RpgFarmStrings.item_name(item), got]))
	if not parts.is_empty():
		RpgMenuUtil.play_ui(PRIZE_SOUND)
	return ", ".join(parts)

## "150 G".
static func money_text(gold: int) -> String:
	return "%d %s" % [gold, RpgRealtimeText.t("UI_GOLD_SHORT", [], RpgStrings.KEYS)]

## An egg of today's hunt is found at `spot` (the name of its marker). False when today has no
## hunt, the spot is none of it or its egg was found already. It pays `each`, and the egg that
## makes the goal pays the prize.
func find_egg(spot: String) -> bool:
	var entry := festival()
	var state := RpgUtil.state()
	if state == null or RpgUtil.to_str(entry.get("kind", "")) != EGG_HUNT:
		return false
	var spots := RpgUtil.to_array(entry.get("spots", []))
	var now := _today_state()
	var seen: Array = now["found"]
	if not spots.has(spot) or seen.has(spot):
		return false
	seen.append(spot)
	now["count"] = seen.size()
	var each := maxi(0, RpgUtil.to_int(entry.get("each", 0)))
	state.gold += each
	var goal := goal_of(entry)
	var won := seen.size() >= goal and not RpgUtil.to_bool(now["done"])
	if won:
		now["done"] = true
	_store_today(now)
	RpgMenuUtil.play_ui(FOUND_SOUND)
	RpgUtil.notify(RpgFarmStrings.t("FARM_EGG_FOUND", [seen.size(), spots.size(), money_text(each)]))
	if won:
		RpgUtil.notify(RpgFarmStrings.t("FARM_EGG_ALL", [seen.size(), give_prize(entry)]))
	_drop_thing(spot)
	return true

## A fish was caught (RpgFishing.caught): on the day of a fishing count it is counted, and the
## one that makes the goal pays the prize.
func _on_caught(_item: StringName) -> void:
	count_fish()

## Counts a fish for today's fishing count. False on a day without one.
func count_fish() -> bool:
	var entry := festival()
	if RpgUtil.to_str(entry.get("kind", "")) != FISHING_COUNT:
		return false
	var now := _today_state()
	now["count"] = RpgUtil.to_int(now["count"]) + 1
	var goal := goal_of(entry)
	var won := RpgUtil.to_int(now["count"]) >= goal and not RpgUtil.to_bool(now["done"])
	if won:
		now["done"] = true
	_store_today(now)
	if won:
		RpgUtil.notify(RpgFarmStrings.t("FARM_FISH_WON", [RpgUtil.to_int(now["count"]), give_prize(entry)]))
	elif not RpgUtil.to_bool(now["done"]):
		RpgUtil.notify(RpgFarmStrings.t("FARM_FISH_COUNTED", [RpgUtil.to_int(now["count"]), goal]))
	return true

## What a produce contest judges: the price of the dearest thing the bin sold this season, or
## (`judge: "count"`) how many things it sold.
static func score_of(entry: Dictionary) -> int:
	var best := RpgShippingBin.shipped_best()
	return RpgUtil.to_int(best["count"]) if RpgUtil.to_str(entry.get("judge", "")) == JUDGE_COUNT else RpgUtil.to_int(best["price"])

## `interact` with the table of today's festival while `held` is in the hand. Returns the line
## that is shown (as a toast too): the verdict of a contest, the thanks of a feast, what a
## feast still needs, or how today's hunt or count stands. "" on a day without a festival.
func use_table(held: StringName = &"") -> String:
	var entry := festival()
	if entry.is_empty():
		return ""
	var line := ""
	match RpgUtil.to_str(entry.get("kind", "")):
		PRODUCE_CONTEST:
			line = _judge(entry)
		FEAST:
			line = _bring(entry, held)
		EGG_HUNT:
			line = RpgFarmStrings.t("FARM_EGG_STANDING", [count(), RpgUtil.to_array(entry.get("spots", [])).size()])
		FISHING_COUNT:
			line = RpgFarmStrings.t("FARM_FISH_COUNTED", [count(), goal_of(entry)])
		_:
			line = RpgFarmStrings.t("FARM_FESTIVAL_TODAY", [event_name(entry)])
	RpgUtil.notify(line)
	return line

func _judge(entry: Dictionary) -> String:
	var now := _today_state()
	if RpgUtil.to_bool(now["done"]):
		return RpgFarmStrings.t("FARM_FESTIVAL_DONE")
	var best := RpgShippingBin.shipped_best()
	now["done"] = true
	now["count"] = score_of(entry)
	_store_today(now)
	if RpgUtil.to_int(best["count"]) <= 0:
		return RpgFarmStrings.t("FARM_CONTEST_NOTHING")
	if score_of(entry) < goal_of(entry):
		return RpgFarmStrings.t("FARM_CONTEST_LOST")
	if RpgUtil.to_str(entry.get("judge", "")) == JUDGE_COUNT:
		return RpgFarmStrings.t("FARM_CONTEST_COUNT_WON", [RpgUtil.to_int(best["count"]), give_prize(entry)])
	return RpgFarmStrings.t("FARM_CONTEST_WON", [RpgFarmStrings.item_name(StringName(RpgUtil.to_str(best["best"]))), give_prize(entry)])

## True for a thing that can be brought to a feast: whatever the farmer can eat.
func is_dish(item: StringName) -> bool:
	var mode := _mode()
	return item != &"" and mode != null and mode.food_energy(item) > 0

func _bring(entry: Dictionary, held: StringName) -> String:
	var state := RpgUtil.state()
	var now := _today_state()
	if RpgUtil.to_bool(now["done"]):
		return RpgFarmStrings.t("FARM_FESTIVAL_DONE")
	if state == null or not is_dish(held) or not state.inventory.has(held):
		return RpgFarmStrings.t("FARM_FEAST_BRING")
	var dish := RpgFarmStrings.item_name(held)
	state.inventory.remove(held, 1)
	now["done"] = true
	now["count"] = 1
	_store_today(now)
	var points := maxi(0, RpgUtil.to_int(entry.get("points", 0)))
	var friends := _friends()
	if friends != null:
		for id in friends.order:
			friends.add_points(id, points)
	var prize := give_prize(entry)
	RpgMenuUtil.play_ui(PRIZE_SOUND)
	var line := RpgFarmStrings.t("FARM_FEAST_THANKS", [dish])
	return line if prize == "" else "%s %s" % [line, prize]

# ------------------------------------------------------------------ the things on the map

func _shown_map() -> Node:
	var router := RpgUtil.router()
	return router.current_map if router != null else null

## The things of today that stand or lie on the map that is shown, in the order they were made.
func things() -> Array[RpgFestivalThing]:
	var out: Array[RpgFestivalThing] = []
	for raw: Variant in _things:
		if is_instance_valid(raw) and raw is RpgFestivalThing:
			var thing: RpgFestivalThing = raw
			if not thing.is_queued_for_deletion():
				out.append(thing)
	return out

## The egg or the table at a marker of the map that is shown, or null.
func thing_at(spot: String) -> RpgFestivalThing:
	for thing in things():
		if thing.spot == spot:
			return thing
	return null

func _drop_thing(spot: String) -> void:
	var thing := thing_at(spot)
	if thing != null:
		thing.queue_free()

## Where a marker of an event is on a map; for a map without it (a village from before the
## card) a place around the marker the people gather at, `index` steps round it; Vector2.INF
## when the map has neither.
static func marker_position(map: Node, marker: String, entry: Dictionary, index: int) -> Vector2:
	var found := RpgSchedule.find_place(map, marker)
	if found != null:
		return RpgUtil.world_position(found)
	var centre := RpgSchedule.find_place(map, RpgUtil.to_str(entry.get("place", "")))
	if centre == null:
		return Vector2.INF
	var tile := float(RpgUtil.map_tile_px(map))
	var ring: Array[Vector2] = [Vector2(0, 2), Vector2(2, 1), Vector2(-2, 1), Vector2(3, -1), Vector2(-3, -1), Vector2(1, 3), Vector2(-1, 3), Vector2(4, 2)]
	return RpgUtil.world_position(centre) + ring[index % ring.size()] * tile

## Puts the things of today's festival on `map` (the map that is shown when null): the eggs
## that were not found yet, or the table; takes away what was there. Returns how many there are.
func refresh(map: Node = null) -> int:
	if map == null:
		map = _shown_map()
	for old: Variant in _things:  # the things of a map that is gone went with it
		if is_instance_valid(old) and old is Node:
			var gone: Node = old
			gone.queue_free()
	_things.clear()
	var entry := festival()
	if map == null or entry.is_empty():
		return 0
	var map_id := RpgUtil.to_str(entry.get("map", ""))
	if map_id != "" and RpgForage.map_key(map) != map_id:
		return 0
	var parent := map.get_node_or_null("YSorted/Entities")
	if parent == null:
		parent = map
	var tile := RpgUtil.map_tile_px(map)
	var diamond := RpgIso.footprint_of(map)
	var wanted: Array[Array] = []  # [kind, marker, index]
	if RpgUtil.to_str(entry.get("kind", "")) == EGG_HUNT:
		var spots := RpgUtil.to_array(entry.get("spots", []))
		var seen := found()
		for i in spots.size():
			if not seen.has(RpgUtil.to_str(spots[i])):
				wanted.append([RpgFestivalThing.EGG, RpgUtil.to_str(spots[i]), i])
	if RpgUtil.to_str(entry.get("table", "")) != "":
		wanted.append([RpgFestivalThing.TABLE, RpgUtil.to_str(entry["table"]), 7])
	for row in wanted:
		var marker := RpgUtil.to_str(row[1])
		var at := marker_position(map, marker, entry, RpgUtil.to_int(row[2]))
		if not at.is_finite():
			continue
		var thing := RpgFestivalThing.make(RpgUtil.to_str(row[0]), marker, RpgUtil.to_int(row[2]), tile, diamond)
		parent.add_child(thing)
		# its foot is the bottom of its cell, or the middle of its diamond
		var foot := at if diamond != Vector2i.ZERO else at + Vector2(0.0, tile * 0.5 - 1.0)
		if thing.is_inside_tree():
			thing.global_position = foot
		else:
			thing.position = foot
		_things.append(thing)
	return _things.size()

# ------------------------------------------------------------------ the night and the morning

## The night of a festival ends it. The calendar still shows the day that ended.
func _on_night(_day: int) -> void:
	var entry := festival()
	if not entry.is_empty():
		festival_ended.emit(entry)

func _on_morning(_day: int) -> void:
	var entry := festival()
	if not entry.is_empty():
		RpgUtil.notify(RpgFarmStrings.t("FARM_FESTIVAL_TODAY", [event_name(entry)]))
		festival_began.emit(entry)
	for row in today():
		if RpgUtil.to_str(row.get("kind", "")) == BIRTHDAY:
			RpgUtil.notify(RpgFarmStrings.t("FARM_BIRTHDAY_TODAY", [_person_name(RpgUtil.to_str(row.get("person", "")))]))
	refresh()

func _on_map(_id: StringName) -> void:
	refresh()

func _on_loaded(_slot: int) -> void:
	refresh()

# ------------------------------------------------------------------ the calendar

## What a season of a year has, by the day: `[{day, kind, text}]`, the festivals and the added
## events first on a day, then the birthdays.
func season_rows(season: int, year: int) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for day in range(1, _length() + 1):
		for entry in events_on(day, season, year):
			out.append({"day": day, "kind": RpgUtil.to_str(entry.get("kind", "")), "text": event_name(entry)})
	return out

func is_calendar_open() -> bool:
	return _page != null and is_instance_valid(_page)

## Shows the calendar over the paused game (the wall calendar of the farmhouse) and returns
## it; the page that is open when one is.
func open_calendar() -> RpgCalendarPage:
	if is_calendar_open():
		return _page
	if _layer == null:
		_layer = CanvasLayer.new()
		_layer.name = PAGE_LAYER_NODE
		_layer.layer = PAGE_LAYER
		_layer.process_mode = Node.PROCESS_MODE_ALWAYS
		add_child(_layer)
	_page = RpgCalendarPage.new()
	_page.name = RpgCalendarPage.PAGE_NAME
	_page.events = self
	_layer.add_child(_page)
	_page.tree_exited.connect(_on_calendar_closed)
	var tree := RpgUtil.tree()
	if tree != null:
		tree.paused = true
	RpgUtil.emit(&"game_paused", [true])
	return _page

func _on_calendar_closed() -> void:
	_page = null
	var tree := RpgUtil.tree()
	if tree != null:
		tree.paused = false
	RpgUtil.emit(&"game_paused", [false])
