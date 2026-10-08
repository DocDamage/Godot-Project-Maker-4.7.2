class_name RpgDialogueRunner
extends RefCounted
## Walks an RpgDialogueResource. Owned by the DialogueBox.
##
## Events (strings, never eval'd): set_flag:<entity>.<key>=<value>, give_item:<id>[:qty],
## take_item:<id>[:qty], give_gold:N, open_shop:<id> (the shop opens when the dialogue closes), quest_start:<id>,
## quest_stage:<id>:<stage>, quest_complete:<id>, set_quest:<id>=<state>, heal_full, emit:<name>[:arg].

const MAX_JUMPS := 1000

var resource: RpgDialogueResource
var _index := -1
var _current: RpgDialogueLine = null
var _finished := true

func start(res: RpgDialogueResource) -> void:
	resource = res
	_current = null
	_finished = false
	_index = -1
	if res == null or res.lines.is_empty():
		_finished = true
		return
	_goto(0)

func current() -> RpgDialogueLine:
	return _current

func is_finished() -> bool:
	return _finished

## The choices of the current line whose condition holds.
func visible_choices() -> Array[RpgDialogueChoice]:
	var out: Array[RpgDialogueChoice] = []
	if _current == null:
		return out
	for c in _current.choices:
		if c.condition == "" or RpgCondition.evaluate(c.condition):
			out.append(c)
	return out

## Moves on. Does nothing while the current line offers choices (use choose()).
func advance() -> void:
	if _finished or _current == null:
		return
	if not visible_choices().is_empty():
		return
	_follow(_current.next)

func choose(i: int) -> void:
	var options := visible_choices()
	if _finished or i < 0 or i >= options.size():
		return
	_follow(options[i].next)

func _follow(target: StringName) -> void:
	if target != &"":
		var idx := _index_of(target)
		if idx < 0:
			push_error("[RPG-DLG] jump target '%s' not found" % target)
			_end()
			return
		_goto(idx)
	else:
		_goto(_index + 1)

func _index_of(line_id: StringName) -> int:
	for i in resource.lines.size():
		if resource.lines[i].id == line_id:
			return i
	return -1

## Shows the first line at or after `idx` whose condition holds; ends when there is none.
func _goto(idx: int) -> void:
	var jumps := 0
	var i := idx
	while i < resource.lines.size():
		var line := resource.lines[i]
		if line.condition == "" or RpgCondition.evaluate(line.condition):
			_index = i
			_current = line
			for event in line.events:
				execute_event(event)
			return
		# A skipped line is passed over, never jumped from.
		i += 1
		jumps += 1
		if jumps > MAX_JUMPS:
			push_error("[RPG-DLG] more than %d lines skipped without one being shown" % MAX_JUMPS)
			break
	_end()

func _end() -> void:
	_current = null
	_finished = true

## Runs one event string. Returns false for an unknown or malformed event.
static func execute_event(event: String) -> bool:
	var state := RpgUtil.state()
	if state == null:
		push_error("[RPG-DLG] GameState is not available for event '%s'" % event)
		return false
	var name := event.get_slice(":", 0)
	var arg := event.substr(name.length() + 1) if event.contains(":") else ""
	match name:
		"set_flag":
			var left := arg.get_slice("=", 0)
			var value_text := arg.substr(left.length() + 1) if arg.contains("=") else "true"
			var dot := left.rfind(".")
			if dot <= 0:
				return _bad(event)
			state.set_flag(left.substr(0, dot), left.substr(dot + 1), _parse_value(value_text))
		"give_item":
			var id := arg.get_slice(":", 0)
			var qty := int(arg.get_slice(":", 1)) if arg.contains(":") else 1
			if id == "":
				return _bad(event)
			state.inventory.add(StringName(id), qty)
		"take_item":
			var id := arg.get_slice(":", 0)
			var qty := int(arg.get_slice(":", 1)) if arg.contains(":") else 1
			if id == "":
				return _bad(event)
			state.inventory.remove(StringName(id), qty)
		"give_gold":
			if not arg.is_valid_int():
				return _bad(event)
			state.gold = RpgUtil.to_int(state.gold) + RpgUtil.to_int(arg)
		"set_quest":
			if not arg.contains("="):
				return _bad(event)
			state.quests[arg.get_slice("=", 0)] = arg.get_slice("=", 1)
		"quest_start":
			if arg == "":
				return _bad(event)
			state.quest_start(StringName(arg))
		"quest_stage":
			if arg.get_slice(":", 0) == "" or not arg.contains(":"):
				return _bad(event)
			state.quest_set_stage(StringName(arg.get_slice(":", 0)), StringName(arg.get_slice(":", 1)))
		"quest_complete":
			if arg == "":
				return _bad(event)
			state.quest_complete(StringName(arg))
		"heal_full":
			state.player_stats.hp = RpgUtil.max_hp(state.player_stats)
		"open_shop":
			if arg == "":
				return _bad(event)
			RpgUtil.emit(&"shop_requested", [StringName(arg)])
		"emit":
			var ev_name := arg.get_slice(":", 0)
			var ev_arg := arg.substr(ev_name.length() + 1) if arg.contains(":") else ""
			RpgUtil.emit(&"dialogue_event", [ev_name, ev_arg])
		_:
			return _bad(event)
	return true

static func _bad(event: String) -> bool:
	push_error("[RPG-DLG] unknown or malformed event '%s'" % event)
	return false

static func _parse_value(text: String) -> Variant:
	if text == "true":
		return true
	if text == "false":
		return false
	if text.is_valid_int():
		return int(text)
	if text.is_valid_float():
		return float(text)
	return text
