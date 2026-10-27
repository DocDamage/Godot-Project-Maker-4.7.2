class_name RpgFarmChildren
extends Node
## Children (1.5.0, T18.17). A child `Children` of the farm's mode, at work when the mode's
## `children` is on (the option *Children* of a farm with marriage); in any other farm it does
## nothing.
##
## * **The question.** From ASK_AFTER_DAYS after the wedding, on a morning when the spouse has
##   ASK_HEARTS hearts, the spouse asks (a line with two choices in the dialogue box, when the
##   farmer is next in the farmhouse); a no is asked again ASK_AFTER_DAYS later. A yes, and a
##   child is born CHILD_DAYS later, in the morning. At most MAX_CHILDREN.
## * **A name**: the newborn is named in the naming box (RpgNamingDialog) with the next name of
##   NAMES; *OK* keeps it.
## * **Growing.** A baby (younger than TODDLER_DAYS) lies in the crib of the farmhouse (its node
##   `Crib`; a farmhouse built before has none, and the baby lies on the spouse's side of the bed):
##   it can be held and talked to. Then a child walks the farmhouse, and the yard before it by day
##   (6:00 to EVENING_HOUR).
## * **The picture** is the scene of a child of the packs (`child_scene`, which the mode's recipe
##   names), else the spouse's own scene, smaller (STAND_IN_SCALE): a villager of the pack's style
##   and size, on squares or on diamonds as the farm is.
## * **The state** is in the flags of the game (`farm_children`: `asked`, `due`, `kids` [{id,
##   name, born}]), so it is saved, and the People page lists the family.

const NODE_NAME := "Children"
const FLAG_ENTITY := "farm_children"
const ASK_AFTER_DAYS := 7
const ASK_HEARTS := 10
const CHILD_DAYS := 14
const TODDLER_DAYS := 14
const MAX_CHILDREN := 2
const EVENING_HOUR := 18
const STAND_IN_SCALE := 0.7
const NAMES: Array[String] = ["Robin", "Ash", "Wren", "Rowan", "Sage", "Juniper"]
const YES_EVENT := "farm_child_yes"
const NODE_PREFIX := "Child_"

## True: the farm has children (the mode sets it).
var enabled := false
## The scene of a child of the packs, or "" (the mode sets it).
var child_scene := ""

var _shown: Array[Node] = []
var _asking := false
var _rng := RandomNumberGenerator.new()  # where a child wanders: never the game's seeded numbers
var _turn := 0.0

static func current() -> RpgFarmChildren:
	var mode := RpgFarmMode.current()
	return mode.family if mode != null else null

func attach() -> void:
	if not enabled:
		return
	var calendar := RpgCalendar.current()
	if calendar != null and not calendar.day_began.is_connected(_on_morning):
		calendar.day_began.connect(_on_morning)
	var bus := RpgUtil.events()
	if bus != null:
		if not bus.map_entered.is_connected(_on_map):
			bus.map_entered.connect(_on_map)
		if not bus.dialogue_event.is_connected(_on_dialogue_event):
			bus.dialogue_event.connect(_on_dialogue_event)

# ------------------------------------------------------------------ the state

static func _flag(key: String, fallback: Variant) -> Variant:
	var state := RpgUtil.state()
	return state.get_flag(FLAG_ENTITY, key, fallback) if state != null else fallback

static func _put(key: String, value: Variant) -> void:
	var state := RpgUtil.state()
	if state != null:
		state.set_flag(FLAG_ENTITY, key, value)

## The children: [{id, name, born}] (`born` the index of the day of the birth).
static func kids() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in RpgUtil.to_array(_flag("kids", [])):
		out.append(RpgUtil.to_dict(raw).duplicate())
	return out

## The day the next child is due, or -1.
static func due() -> int:
	return RpgUtil.to_int(_flag("due", -1), -1)

static func _today() -> int:
	var calendar := RpgCalendar.current()
	return calendar.today() if calendar != null else 0

## How many days old a child is.
static func age_of(kid: Dictionary) -> int:
	return _today() - RpgUtil.to_int(kid.get("born", 0))

## True for a baby (in the crib), false for a child that walks.
static func is_baby(kid: Dictionary) -> bool:
	return age_of(kid) < TODDLER_DAYS

# ------------------------------------------------------------------ the question

## True when the spouse asks this morning: married long enough, the hearts, no child on the way,
## room for one more, and not asked within ASK_AFTER_DAYS.
func should_ask() -> bool:
	var marriage := RpgMarriage.current()
	var friends := RpgFriendship.current()
	if not enabled or marriage == null or friends == null or marriage.spouse() == "":
		return false
	if due() >= 0 or kids().size() >= MAX_CHILDREN:
		return false
	var today := _today()
	var state := RpgUtil.state()
	var wed := RpgUtil.to_int(state.get_flag(RpgMarriage.FLAG_ENTITY, RpgMarriage.WED_KEY, -1), -1) if state != null else -1
	if wed < 0 or today < wed + ASK_AFTER_DAYS:
		return false
	var asked := RpgUtil.to_int(_flag("asked", -1), -1)
	if asked >= 0 and today < asked + ASK_AFTER_DAYS:
		return false
	return friends.hearts(marriage.spouse()) >= ASK_HEARTS

## The spouse asks (the dialogue box); the answer comes as the dialogue event YES_EVENT.
func ask() -> bool:
	var box := RpgUtil.service(&"rpg_dialogue_box")
	_put("asked", _today())
	if box == null or not box.has_method("open") or box.call("is_open"):
		_asking = true  # asked when the box is free again (the next map)
		return false
	_asking = false
	var line := RpgDialogueLine.new()
	line.id = &"ask"
	line.speaker = RpgFriendship.current().display_name(RpgMarriage.current().spouse()) if RpgFriendship.current() != null else ""
	line.text = RpgFarmStrings.t("FARM_CHILD_ASK")
	var yes := RpgDialogueChoice.new()
	yes.text = RpgFarmStrings.t("FARM_CHILD_YES")
	yes.next = &"yes"
	var no := RpgDialogueChoice.new()
	no.text = RpgFarmStrings.t("FARM_CHILD_NOT_YET")
	no.next = &"no"
	var choices: Array[RpgDialogueChoice] = [yes, no]
	line.choices = choices
	var agreed := RpgDialogueLine.new()
	agreed.id = &"yes"
	agreed.text = RpgFarmStrings.t("FARM_CHILD_AGREED")
	agreed.events = PackedStringArray(["emit:" + YES_EVENT])
	var later := RpgDialogueLine.new()  # never shown: its condition is false, the box closes
	later.id = &"no"
	later.condition = "flag:%s.%s" % [FLAG_ENTITY, YES_EVENT]
	var res := RpgDialogueResource.new()
	var lines: Array[RpgDialogueLine] = [line, agreed, later]
	res.lines = lines
	box.call("open", res, null)
	return true

## A yes: a child is due CHILD_DAYS from today.
func agree() -> void:
	if due() < 0 and kids().size() < MAX_CHILDREN:
		_put("due", _today() + CHILD_DAYS)

func _on_dialogue_event(event_name: String, _arg: String) -> void:
	if event_name == YES_EVENT:
		agree()

# ------------------------------------------------------------------ the morning

func _on_morning(_day: int) -> void:
	if not enabled:
		return
	if due() >= 0 and _today() >= due():
		born()
	elif should_ask():
		ask()
	_refresh()

## A child is born: it joins the family with the next name of NAMES, the naming box asks for its
## own when the game is shown. Returns its row.
func born() -> Dictionary:
	var family := kids()
	var kid := {"id": family.size() + 1, "name": NAMES[family.size() % NAMES.size()], "born": _today()}
	family.append(kid)
	_put("kids", family)
	_put("due", -1)
	RpgUtil.notify(RpgFarmStrings.t("FARM_CHILD_BORN", [kid["name"]]))
	if is_inside_tree() and RpgUtil.tree() != null and RpgUtil.tree().current_scene != null:
		var box := RpgNamingDialog.open(RpgFarmStrings.t("FARM_CHILD"), str(kid["name"]))
		box.named.connect(func(text: String) -> void: rename(RpgUtil.to_int(kid["id"]), text))
	return kid

func rename(id: int, text: String) -> bool:
	var family := kids()
	for kid in family:
		if RpgUtil.to_int(kid["id"]) == id and text.strip_edges() != "":
			kid["name"] = text.strip_edges()
			_put("kids", family)
			_refresh()
			return true
	return false

## A child that walks turns now and then: it goes a little way and stands.
func _process(delta: float) -> void:
	_turn -= delta
	if _turn > 0.0 or _shown.is_empty():
		return
	_turn = _rng.randf_range(0.8, 2.0)
	for node in _shown:
		if is_instance_valid(node) and node is RpgActor and not RpgUtil.to_bool(node.get_meta(&"child_baby", true)):
			var dirs: Array[Vector2] = [Vector2.ZERO, Vector2.LEFT, Vector2.RIGHT, Vector2.UP, Vector2.DOWN]
			(node as RpgActor).move_dir(dirs[_rng.randi_range(0, dirs.size() - 1)])

## True for a child node that walks (not a baby in the crib).
static func walks(node: Node) -> bool:
	return node != null and not RpgUtil.to_bool(node.get_meta(&"child_baby", true))

# ------------------------------------------------------------------ on the maps

func _on_map(_map_id: StringName) -> void:
	if _asking:
		ask()
	_refresh()

func _refresh() -> void:
	var router := RpgUtil.router()
	show_on(router.current_map if router != null else null)

## Shows the children on `map`: in the farmhouse the babies in the crib and the children walking;
## on the farm by day the children in the yard. Returns the nodes.
func show_on(map: Node) -> Array[Node]:
	for node in _shown:
		if is_instance_valid(node):
			node.queue_free()
	_shown.clear()
	if not enabled or map == null:
		return _shown
	var marriage := RpgMarriage.current()
	var in_house := marriage != null and marriage.is_house(map)
	var calendar := RpgCalendar.current()
	var by_day := calendar != null and calendar.hour() < EVENING_HOUR
	var outside := not in_house and RpgUtil.to_str(map.get("map_id")) == "farm" and by_day
	if not in_house and not outside:
		return _shown
	var holder := map.get_node_or_null("YSorted/Entities")
	if holder == null:
		holder = map
	var index := 0
	for kid in kids():
		var baby := is_baby(kid)
		if outside and baby:
			continue
		var node := make_node(kid)
		if node == null:
			continue
		holder.add_child(node)
		var at := _crib_spot(map) if baby else _walk_spot(map, index, outside)
		if node is Node2D:
			(node as Node2D).global_position = at
		node.set_meta(&"child_baby", baby)
		_shown.append(node)
		index += 1
	return _shown

## The node of a child: the child scene of the build, else the spouse's scene, smaller.
func make_node(kid: Dictionary) -> Node:
	var path := child_scene if child_scene != "" and ResourceLoader.exists(child_scene) else ""
	var scale := 1.0
	if path == "":
		var marriage := RpgMarriage.current()
		var friends := RpgFriendship.current()
		var id := marriage.spouse() if marriage != null else ""
		path = RpgUtil.to_str(friends.person(id).get("scene", "")) if friends != null and id != "" else ""
		scale = STAND_IN_SCALE
	var packed := load(path) as PackedScene if path != "" and ResourceLoader.exists(path) else null
	var node: Node = packed.instantiate() if packed != null else Node2D.new()
	node.name = "%s%d" % [NODE_PREFIX, RpgUtil.to_int(kid["id"])]
	if node is Node2D:
		(node as Node2D).scale = Vector2(scale, scale)
	if &"entity_id" in node:
		node.set(&"entity_id", "child_%d" % RpgUtil.to_int(kid["id"]))
	if &"dialogue" in node:
		node.set(&"dialogue", _dialogue(kid))
	for each: Node in node.get_children():
		if each is RpgSchedule:
			node.remove_child(each)
			each.queue_free()  # a child keeps no villager's day
	return node

func _dialogue(kid: Dictionary) -> RpgDialogueResource:
	var line := RpgDialogueLine.new()
	line.speaker = str(kid["name"])
	line.text = RpgFarmStrings.t("FARM_CHILD_BABY" if is_baby(kid) else "FARM_CHILD_TALK")
	var res := RpgDialogueResource.new()
	var lines: Array[RpgDialogueLine] = [line]
	res.lines = lines
	return res

## Where a baby lies: on the crib of the farmhouse, else on the spouse's side of the bed, else
## beside the bed the farmer wakes at.
static func _crib_spot(map: Node) -> Vector2:
	for wanted: String in ["Crib", "Bed2", "Bed"]:
		var found := map.find_child(wanted, true, false) as Node2D
		if found != null:
			return found.global_position + Vector2(0.0, -4.0)
	return RpgUtil.world_position(map as Node2D) if map is Node2D else Vector2.ZERO

## Where a child walks: the middle of the farmhouse's floor (a little apart for a second one), or
## before the door of the house in the farm's yard.
static func _walk_spot(map: Node, index: int, outside: bool) -> Vector2:
	var layer := RpgMarriage._layer_of(map)
	var tile := float(RpgUtil.map_tile_px(map))
	if outside:
		for node in map.find_children("*", "Node2D", true, false):
			if node is RpgSpawnPoint and String(node.name).contains("house"):
				return (node as Node2D).global_position + Vector2(tile * (index + 1), tile)
	if layer != null:
		var rect := layer.get_used_rect()
		var cell := rect.position + rect.size / 2 + Vector2i(index, 0)
		return layer.to_global(layer.map_to_local(cell))
	return Vector2(tile * (index + 2), tile * 2.0)
