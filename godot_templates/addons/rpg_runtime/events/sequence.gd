class_name RpgSequence
extends Resource
## A scripted scene: a list of commands that run in order (RpgSequenceRunner). Files live in
## game/data/sequences/<id>.tres. A trigger area, an interaction or the dialogue event
## `run_sequence:<id>` starts one.
##
## A command is a Dictionary {"cmd": <name>, ...arguments}. `entity` is an entity_id in the current
## map, or "player". Tiles are the map's tile size.
##
##   move_actor  {entity, tiles: [dx, dy], speed (tiles/s, optional), wait (default true)}
##               walks along x first, then y; not stopped by walls
##   face        {entity, dir: up|down|left|right} or {entity, toward: <entity>}
##   animate     {entity, animation: <base name, e.g. "attack">, seconds (optional), wait}
##               holds "<animation>_<facing>"; an empty animation (or the end) lets it go
##   wait        {seconds}
##   fade_out    {seconds (default 0.3), wait}         fade_in {seconds, wait}
##   shake       {seconds (default 0.4), strength (px, default 3), wait} (Settings > Screen shake)
##   play_sound  {slot}
##   show_dialogue {dialogue: <id or res:// path>} or {lines: [<text keys>], speaker}
##   give_item   {item, qty (default 1)}               take_item {item, qty}
##   set_flag    {entity, key, value (default true)}
##   start_battle {enemies: [<enemy ids>], can_escape (default true)}; a defeat ends the sequence
##   change_map  {map: <res:// path>, spawn (default "default")}
##   camera_pan  {tiles: [dx, dy]} from the player, or {entity}; {seconds (default 0.5), wait}
##   camera_lock {}  the camera stays where it is while the player walks on; camera_unlock {}
##   set_var     {name, value}                         add_var {name, amount (negative subtracts)}
##   event       {event: <any dialogue event, e.g. "quest_start:errand">}
## Flow (labels are names inside this sequence):
##   label       {name}
##   goto        {label}
##   if          {condition: <dialogue condition, e.g. "var:planks>=3">, goto: <label>,
##                else: <label> (optional)}
##   call        {sequence: <id>}   runs that sequence, then carries on here
##   wait_for    {entity} waits for that actor's move started with wait: false; without an
##               entity, for every move, fade and pan that is still running
##   end         {}  stops this sequence (a called one returns to its caller)

const SEQUENCES_DIR := RpgGameState.SEQUENCES_DIR

## The command names and the arguments each one needs.
const REQUIRED := {
	"move_actor": ["entity", "tiles"],
	"face": ["entity"],
	"animate": ["entity"],
	"wait": ["seconds"],
	"fade_out": [],
	"fade_in": [],
	"shake": [],
	"play_sound": ["slot"],
	"show_dialogue": [],
	"give_item": ["item"],
	"take_item": ["item"],
	"set_flag": ["entity", "key"],
	"start_battle": ["enemies"],
	"change_map": ["map"],
	"camera_pan": [],
	"camera_lock": [],
	"camera_unlock": [],
	"set_var": ["name", "value"],
	"add_var": ["name", "amount"],
	"event": ["event"],
	"label": ["name"],
	"goto": ["label"],
	"if": ["condition", "goto"],
	"call": ["sequence"],
	"wait_for": [],
	"end": [],
}
const DIRECTIONS: Array[String] = ["up", "down", "left", "right"]

## The kinds of step an editor offers a form for (the dock's Cutscenes tab), in menu order:
## {kind, cmd, fields: [[argument, type]]}. The types: entity (an entity_id of the map, or
## "player"), pair ([dx, dy]), float, int, bool, text, dir, value (a JSON value), lines (one text
## key per line). Every other command is edited as JSON.
const STEP_KINDS: Array[Dictionary] = [
	{"kind": "move", "cmd": "move_actor", "fields": [["entity", "entity"], ["tiles", "pair"], ["speed", "float"], ["wait", "bool"]]},
	{"kind": "face", "cmd": "face", "fields": [["entity", "entity"], ["dir", "dir"], ["toward", "entity"]]},
	{"kind": "say", "cmd": "show_dialogue", "fields": [["dialogue", "text"], ["speaker", "text"], ["lines", "lines"]]},
	{"kind": "wait", "cmd": "wait", "fields": [["seconds", "float"]]},
	{"kind": "camera", "cmd": "camera_pan", "fields": [["entity", "entity"], ["tiles", "pair"], ["seconds", "float"], ["wait", "bool"]]},
	{"kind": "flag", "cmd": "set_flag", "fields": [["entity", "text"], ["key", "text"], ["value", "value"]]},
	{"kind": "give", "cmd": "give_item", "fields": [["item", "text"], ["qty", "int"]]},
	{"kind": "play sound", "cmd": "play_sound", "fields": [["slot", "text"]]},
	{"kind": "fade out", "cmd": "fade_out", "fields": [["seconds", "float"], ["wait", "bool"]]},
	{"kind": "fade in", "cmd": "fade_in", "fields": [["seconds", "float"], ["wait", "bool"]]},
]
## The arguments that name an actor of the map.
const ENTITY_KEYS: Array[String] = ["entity", "toward"]
## The commands whose `entity` is not an actor (set_flag's is the flag's owner, any name).
const NOT_ACTORS: Array[String] = ["set_flag"]

## The STEP_KINDS entry of a command name, or {}.
static func step_kind(cmd: String) -> Dictionary:
	for entry in STEP_KINDS:
		if entry["cmd"] == cmd:
			return entry
	return {}

## A new step of a STEP_KINDS kind with the arguments it needs.
static func new_step(kind: String) -> Dictionary:
	for entry in STEP_KINDS:
		if entry["kind"] != kind:
			continue
		var step := {"cmd": entry["cmd"]}
		match str(entry["cmd"]):
			"move_actor":
				step["entity"] = "player"
				step["tiles"] = [1, 0]
			"face":
				step["entity"] = "player"
				step["dir"] = "down"
			"show_dialogue":
				step["lines"] = ["..."]
			"wait":
				step["seconds"] = 1.0
			"set_flag":
				step["entity"] = "story"
				step["key"] = "flag"
			"give_item":
				step["item"] = "potion"
			"play_sound":
				step["slot"] = "sfx_chest"
		return step
	return {}

## The steps that name an actor the map does not have: "command 2 (face) names the unknown
## entity 'bob'". `entities` are the entity ids of the map; "player" is always known.
static func entity_problems(command_list: Array, entities: Array) -> Array[String]:
	var out: Array[String] = []
	for i in command_list.size():
		var command := RpgUtil.to_dict(command_list[i])
		var name := str(command.get("cmd", ""))
		if NOT_ACTORS.has(name):
			continue
		for key in ENTITY_KEYS:
			var who := str(command.get(key, ""))
			if who != "" and who != "player" and not entities.has(who):
				out.append("command %d (%s) names the unknown entity '%s'" % [i + 1, name, who])
	return out

@export var id: StringName
## Cancel skips the rest: timed steps finish at once, characters arrive, dialogues run their
## events and take the first choice. A battle is still fought.
@export var skippable: bool = false
@export var commands: Array[Dictionary] = []

## game/data/sequences/<id>.tres; an id that is already a path (res://, user://) is kept.
static func path_of(sequence_id: StringName) -> String:
	var text := String(sequence_id)
	return text if text.contains("://") else "%s/%s.tres" % [SEQUENCES_DIR, text]

## The sequence with this id, or null.
static func load_sequence(sequence_id: StringName) -> RpgSequence:
	var path := path_of(sequence_id)
	if sequence_id == &"" or not ResourceLoader.exists(path):
		return null
	return load(path) as RpgSequence

## The index of the `label` command with this name, or -1.
func label_index(label_name: String) -> int:
	return label_in(commands, label_name)

static func label_in(command_list: Array, label_name: String) -> int:
	for i in command_list.size():
		var command := RpgUtil.to_dict(command_list[i])
		if str(command.get("cmd", "")) == "label" and str(command.get("name", "")) == label_name:
			return i
	return -1

## What is wrong with the commands, one sentence each (empty when nothing is): unknown commands,
## missing arguments, jumps to labels that do not exist and directions that are not one of the four.
func problems() -> Array[String]:
	return problems_of(commands)

## problems() for a command list (static, so the editor's validator can call it).
static func problems_of(command_list: Array) -> Array[String]:
	var out: Array[String] = []
	for i in command_list.size():
		var command := RpgUtil.to_dict(command_list[i])
		var name := str(command.get("cmd", ""))
		var where := "command %d (%s)" % [i + 1, name if name != "" else "no cmd"]
		if not REQUIRED.has(name):
			out.append("%s is not a known command" % where)
			continue
		var required: Array = REQUIRED[name]
		for key: String in required:
			if not command.has(key) or str(command[key]) == "":
				out.append("%s needs '%s'" % [where, key])
		var jumps: Array[String] = []
		if name == "goto":
			jumps = ["label"]
		elif name == "if":
			jumps = ["goto", "else"]
		for key in jumps:
			var target := str(command.get(key, ""))
			if target != "" and label_in(command_list, target) < 0:
				out.append("%s jumps to the unknown label '%s'" % [where, target])
		if name == "face" and command.has("dir") and not DIRECTIONS.has(str(command["dir"])):
			out.append("%s has the direction '%s'" % [where, str(command["dir"])])
		if name == "face" and not command.has("dir") and not command.has("toward"):
			out.append("%s needs 'dir' or 'toward'" % where)
		if name == "show_dialogue" and not command.has("dialogue") and not command.has("lines"):
			out.append("%s needs 'dialogue' or 'lines'" % where)
		for key: String in ["tiles"]:
			if command.has(key) and not _is_pair(command[key]):
				out.append("%s needs '%s' as [dx, dy]" % [where, key])
	return out

static func _is_pair(value: Variant) -> bool:
	if not (value is Array):
		return false
	var pair: Array = value
	return pair.size() == 2 and typeof(pair[0]) in [TYPE_INT, TYPE_FLOAT] and typeof(pair[1]) in [TYPE_INT, TYPE_FLOAT]

## [dx, dy] of a command argument as a Vector2i (ZERO when it is missing or not two numbers).
static func tiles_of(command: Dictionary, key: String) -> Vector2i:
	var raw: Variant = command.get(key)
	if not (raw is Array):
		return Vector2i.ZERO
	var pair: Array = raw
	if pair.size() != 2:
		return Vector2i.ZERO
	return Vector2i(RpgUtil.to_int(pair[0]), RpgUtil.to_int(pair[1]))
