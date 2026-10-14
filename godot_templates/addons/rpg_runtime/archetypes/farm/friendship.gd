class_name RpgFriendship
extends Node
## How well the farmer knows the people of the village (T17.09): points a person, shown as
## hearts (ten, 250 points each). Talking to somebody once a day gives a few; a gift, at most
## two a week, gives by taste: each person loves, likes or dislikes some items
## (`game/data/people.json`), and everything else is taken politely.
##
## It is not an autoload: the farm's mode makes it with `RpgFriendship.ensure()` (a child of
## GameState, as the calendar is) and everybody finds it with `RpgFriendship.current()`, which
## is null in a game without it. It is saved under the optional key `friendship`, written only
## by a game that has it. The day's and the week's counters are reset by the calendar
## (`day_began`; a week begins on weekday 0).
##
## **A birthday** (T17.25: `birthday` of a person's entry, known to RpgFarmEvents): the first
## gift of that day counts BIRTHDAY_FACTOR times when the person loves or likes it or takes it
## politely, and it is not one of the week's two. A disliked gift is a disliked gift on any
## day: it costs what it always costs, but it is the day's gift all the same. A second gift on
## the birthday is a gift like any other.
##
## **Marriage** (T17.26, RpgMarriage) sets `cap_of`, the most points a person can have (eight
## hearts for somebody who can be courted and is not yet), and takes a bouquet or a pendant
## that is given (`gift` hands it over), which is no gift of taste.
##
## It also knows the people themselves (`people`, from the file), gives their schedules to the
## NPCs that carry an RpgSchedule without entries (`RpgSchedule.source`), and counts a talk
## when the player interacts with the NPC of a person (`Events.interaction_started`).

## The points, the hearts or what is known of a person changed.
signal changed(person: String)

const NODE_NAME := "Friendship"
## The key of a saved game that holds the friendships.
const SAVE_KEY := "friendship"
## The user's file of the running game. Set by the farm's mode from its `data_dir`, which the
## recipe gives it: a runtime script names no path of the game itself.
static var people_path := ""
## Who says how many points a person can have at most: `func(id: String) -> int`; MAX_POINTS
## for everybody while nobody sets it (only RpgMarriage does).
static var cap_of: Callable = Callable()
const HEARTS := 10
const HEART_POINTS := 250
const MAX_POINTS := HEARTS * HEART_POINTS
## What talking gives, once a day.
const TALK_POINTS := 20
## What a gift gives by taste.
const LOVE_POINTS := 80
const LIKE_POINTS := 45
const NEUTRAL_POINTS := 20
const DISLIKE_POINTS := -20
const GIFTS_PER_WEEK := 2
## How many times the first gift of a person's birthday counts (not a disliked one).
const BIRTHDAY_FACTOR := 5
## The tastes, as `taste_of` and `gift` name them and as people.json lists them.
const LOVES := "loves"
const LIKES := "likes"
const DISLIKES := "dislikes"
const NEUTRAL := "neutral"
const TASTES: Array[String] = [LOVES, LIKES, DISLIKES]

## Person id -> its entry of people.json, and the ids in the order of the file.
var people: Dictionary = {}
var order: Array[String] = []
## Person id -> points (0 to MAX_POINTS).
var points: Dictionary = {}
## Who the farmer has talked to or given something, in the order they were met.
var met: Array[String] = []
## Who was talked to today.
var talked: Array[String] = []
## Person id -> the gifts of this week.
var gifts: Dictionary = {}
## Person id -> the ids of the items that were given (their taste for these is known).
var known: Dictionary = {}

var _calendar: RpgCalendar = null

# ------------------------------------------------------------------ finding it

## The friendships of the running game, or null: only a farm has them.
static func current() -> RpgFriendship:
	var state := RpgUtil.state()
	return state.get_node_or_null(NODE_NAME) as RpgFriendship if state != null else null

## The friendships of the running game, made when there are none yet (a child of GameState, so
## they are there on every map and are saved with the game), with the people of
## game/data/people.json. Null without a GameState.
static func ensure() -> RpgFriendship:
	var state := RpgUtil.state()
	if state == null:
		return null
	var found := state.get_node_or_null(NODE_NAME) as RpgFriendship
	if found == null:
		found = RpgFriendship.new()
		found.name = NODE_NAME
		state.add_child(found)
		found.add_file(people_path)
	found.bind()
	return found

func _ready() -> void:
	bind()

## Listens to the calendar and to the player's interactions and offers the schedules. Safe to
## call again: `ensure` does, so a calendar made after the friendships is found too.
func bind() -> void:
	var calendar := RpgCalendar.current()
	if calendar != null and calendar != _calendar:
		_calendar = calendar
		if not calendar.day_began.is_connected(_on_day_began):
			calendar.day_began.connect(_on_day_began)
	var bus := RpgUtil.events()
	if bus != null and not bus.interaction_started.is_connected(_on_interaction):
		bus.interaction_started.connect(_on_interaction)
	RpgSchedule.source = schedule_of

func _exit_tree() -> void:
	if RpgSchedule.source == schedule_of:
		RpgSchedule.source = Callable()

# ------------------------------------------------------------------ the people

## Adds the people of a file that are not there yet. A file that is missing or is no list of
## people adds nothing.
func add_file(path: String) -> void:
	if not FileAccess.file_exists(path):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	add_list(RpgUtil.to_array(RpgUtil.to_dict(RpgUtil.restore_numbers(parsed)).get("people", [])))

## Adds entries (what a test has instead of a file). An entry without an id, or whose id is
## there already, is left out. The file is read as it is (no planned list fills it in), so a
## person is gone when their entry is deleted; an entry that says `"removed": true`, the mark
## the farm's other lists take a thing away with, is nobody either.
func add_list(entries: Array) -> void:
	for raw: Variant in entries:
		var entry := RpgUtil.to_dict(raw)
		var id := RpgUtil.to_str(entry.get("id", ""))
		if id == "" or people.has(id) or RpgUtil.to_bool(entry.get("removed", false)):
			continue
		people[id] = entry
		order.append(id)

## The entry of a person, or {}.
func person(id: String) -> Dictionary:
	return RpgUtil.to_dict(people.get(id, {}))

## The name of a person as a sentence shows it: its `name` (a translation key or plain text),
## else its id made readable.
func display_name(id: String) -> String:
	var text := RpgUtil.to_str(person(id).get("name", ""))
	if text == "":
		return id.capitalize()
	return String(TranslationServer.translate(text))

## The schedule of a person: the entries of an RpgSchedule (`RpgSchedule.source`).
func schedule_of(id: String) -> Array:
	return RpgUtil.to_array(person(id).get("schedule", []))

## The person an NPC is: the `person` of its schedule, else its `entity_id`; "" for a node that
## is nobody of the file.
func person_of(node: Node) -> String:
	if node == null:
		return ""
	var schedule := node.get_node_or_null(RpgSchedule.NODE_NAME) as RpgSchedule
	var id := schedule.person if schedule != null else ""
	if id == "" and &"entity_id" in node:
		id = RpgUtil.to_str(node.get(&"entity_id"))
	return id if people.has(id) else ""

## What a person thinks of an item: LOVES, LIKES, DISLIKES or NEUTRAL.
func taste_of(id: String, item_id: StringName) -> String:
	var entry := person(id)
	for taste in TASTES:
		for listed: Variant in RpgUtil.to_array(entry.get(taste, [])):
			if RpgUtil.to_str(listed) == String(item_id):
				return taste
	return NEUTRAL

## The points a gift of a taste gives.
static func gift_points(taste: String) -> int:
	match taste:
		LOVES:
			return LOVE_POINTS
		LIKES:
			return LIKE_POINTS
		DISLIKES:
			return DISLIKE_POINTS
	return NEUTRAL_POINTS

## The points the gift of a birthday gives: BIRTHDAY_FACTOR times those of the taste, but a
## disliked gift takes what it always takes.
static func birthday_points(taste: String) -> int:
	var usual := gift_points(taste)
	return usual * BIRTHDAY_FACTOR if usual > 0 else usual

# ------------------------------------------------------------------ points and hearts

func points_of(id: String) -> int:
	return RpgUtil.to_int(points.get(id, 0))

## The hearts of a person, 0 to 10: a heart every 250 points.
func hearts(id: String) -> int:
	return clampi(points_of(id) / HEART_POINTS, 0, HEARTS)

func has_met(id: String) -> bool:
	return met.has(id)

## Gives (or takes) points; they stay within 0 and MAX_POINTS. Returns the points after.
func add_points(id: String, amount: int) -> int:
	if id == "":
		return 0
	var most := MAX_POINTS
	if cap_of.is_valid():
		most = clampi(RpgUtil.to_int(cap_of.call(id), MAX_POINTS), 0, MAX_POINTS)
	# what is above the cap already (points of a game before marriage) is not taken away
	points[id] = clampi(points_of(id) + amount, 0, maxi(most, points_of(id)))
	changed.emit(id)
	return points_of(id)

## The farmer talks to a person: met from now on, and TALK_POINTS the first time of a day.
## Returns the points it gave.
func talk(id: String) -> int:
	if id == "":
		return 0
	bind()
	_meet(id)
	if talked.has(id):
		return 0
	talked.append(id)
	add_points(id, TALK_POINTS)
	return TALK_POINTS

func gifts_left(id: String) -> int:
	return maxi(0, GIFTS_PER_WEEK - RpgUtil.to_int(gifts.get(id, 0)))

## The farmer gives a person one of an item. Returns what the person thinks of it (LOVES,
## LIKES, DISLIKES or NEUTRAL), or "" when nothing was given: the person had two gifts this
## week, or (`take`) the bag does not hold the item. The item leaves the bag (`take`), the
## points change by the taste, and the taste for this item is known from now on. The first gift
## of the person's birthday counts as the top of the file says, and is none of the week's two.
func gift(id: String, item_id: StringName, take: bool = true) -> String:
	if id == "" or item_id == &"":
		return ""
	bind()
	var marriage := RpgMarriage.current()
	if marriage != null and marriage.is_token(item_id):
		return marriage.give(id, item_id, take)
	var events := RpgFarmEvents.current()
	var birthday := events != null and events.birthday_gift_open(id)
	if not birthday and gifts_left(id) <= 0:
		RpgUtil.notify(RpgFarmStrings.t("FARM_GIFT_ENOUGH", [display_name(id)]))
		return ""
	if take:
		var state := RpgUtil.state()
		if state == null or not state.inventory.has(item_id):
			return ""
		state.inventory.remove(item_id, 1)
	_meet(id)
	if birthday:
		events.note_birthday_gift(id)
	else:
		gifts[id] = RpgUtil.to_int(gifts.get(id, 0)) + 1
	var given: Array = RpgUtil.to_array(known.get(id, []))
	if not given.has(String(item_id)):
		given.append(String(item_id))
	known[id] = given
	var taste := taste_of(id, item_id)
	add_points(id, birthday_points(taste) if birthday else gift_points(taste))
	var said := RpgFarmStrings.t("FARM_GIFT_" + taste.to_upper(), [display_name(id)])
	RpgUtil.notify(RpgFarmStrings.t("FARM_GIFT_BIRTHDAY", [said]) if birthday else said)
	return taste

## The items of a taste the farmer knows of (those that were given), in the order of the file.
func known_of(id: String, taste: String) -> Array[String]:
	var out: Array[String] = []
	var given := RpgUtil.to_array(known.get(id, []))
	if taste == NEUTRAL:
		for item: Variant in given:
			if taste_of(id, StringName(RpgUtil.to_str(item))) == NEUTRAL:
				out.append(RpgUtil.to_str(item))
		return out
	for listed: Variant in RpgUtil.to_array(person(id).get(taste, [])):
		if given.has(RpgUtil.to_str(listed)):
			out.append(RpgUtil.to_str(listed))
	return out

func _meet(id: String) -> void:
	if not met.has(id):
		met.append(id)
		changed.emit(id)

func _on_interaction(target: Node) -> void:
	var id := person_of(target)
	if id == "":
		return
	var schedule := target.get_node_or_null(RpgSchedule.NODE_NAME) as RpgSchedule
	if schedule == null or not schedule.away():
		talk(id)

## A new day: everybody can be talked to again, and on the first day of a week given to again.
func _on_day_began(_day: int) -> void:
	talked.clear()
	if _calendar != null and _calendar.weekday() == 0:
		gifts.clear()

# ------------------------------------------------------------------ a new game and the save

## Nobody is met. The people stay.
func reset() -> void:
	points.clear()
	met.clear()
	talked.clear()
	gifts.clear()
	known.clear()

## What a saved game holds of the friendships.
func to_dict() -> Dictionary:
	return {
		"points": points.duplicate(),
		"met": met.duplicate(),
		"talked": talked.duplicate(),
		"gifts": gifts.duplicate(),
		"known": known.duplicate(true),
	}

## Takes the `friendship` key of a saved game. A save without it (or with something else there)
## is a game in which nobody is met; what is no number or no list is left out. No signal.
func from_dict(raw: Variant) -> void:
	reset()
	var data := RpgUtil.to_dict(raw)
	var saved_points := RpgUtil.to_dict(data.get("points"))
	for id: Variant in saved_points.keys():
		points[RpgUtil.to_str(id)] = clampi(RpgUtil.to_int(saved_points[id]), 0, MAX_POINTS)
	for id: Variant in RpgUtil.to_array(data.get("met")):
		if not met.has(RpgUtil.to_str(id)):
			met.append(RpgUtil.to_str(id))
	for id: Variant in RpgUtil.to_array(data.get("talked")):
		if not talked.has(RpgUtil.to_str(id)):
			talked.append(RpgUtil.to_str(id))
	var saved_gifts := RpgUtil.to_dict(data.get("gifts"))
	for id: Variant in saved_gifts.keys():
		gifts[RpgUtil.to_str(id)] = maxi(0, RpgUtil.to_int(saved_gifts[id]))
	var saved_known := RpgUtil.to_dict(data.get("known"))
	for id: Variant in saved_known.keys():
		var items: Array = []
		for item: Variant in RpgUtil.to_array(saved_known[id]):
			items.append(RpgUtil.to_str(item))
		known[RpgUtil.to_str(id)] = items
