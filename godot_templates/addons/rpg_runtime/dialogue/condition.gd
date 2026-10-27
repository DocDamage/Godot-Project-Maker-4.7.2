class_name RpgCondition
extends RefCounted
## Condition mini-language, a pure function of GameState.
##
##   expr := term (("and" | "or") term)*      term := ["not"] atom
##
## Evaluated left to right with NO operator precedence. Atoms:
##   flag:<entity>.<key>    item:<id>[>=N]    gold>=N    level>=N    quest:<id>=<state>
##   quest_active:<id>    quest_done:<id>    quest_stage:<id>:<stage>    party:<actor id>
##   quest_failed:<id>    quest_available:<id> (not started, and what it requires holds)
##   quest_ready:<id>     (its stage waits to be turned in and its condition holds)
##   count:<name>>=N      (a counter of GameState.counters is at least N: count:defeated:wolf>=5,
##                         count:items:log>=30; a counter never counted is 0)
##   achievement:<id>     (the achievement is unlocked)
##   var:<name><op><N>    (op is one of >= <= == != > <; a variable never set is 0)
##   ability:<id>         (the player has the ability; the metroidvania, T14.05)
##   friendship:<id>>=N   (the person has at least N hearts; the farm, T17.09. False in a game
##                         without friendships)
##   birthday:<id>   festival   festival_tomorrow   event:<kind>
##                        (today is the person's birthday; today, or tomorrow, is a festival or
##                         another day for everybody; today has an event of the kind, such as
##                         event:egg_hunt or event:wedding. The farm, T17.25. False in a game
##                         without festivals)
##   courting:<id>   engaged:<id>   spouse:<id>
##                        (the farmer courts the person, is engaged to it, is married to it;
##                         each is true at one stage only. The farm, T17.26: read from the flags
##                         of the game, `farm_marriage`. False in a game without marriage)
## Unknown atoms are false and log "[RPG-DLG] unknown condition atom".

## The comparison operators of var:, longest first so that ">=" is not read as ">".
const VAR_OPS: Array[String] = [">=", "<=", "==", "!=", ">", "<"]

static func evaluate(expr: String) -> bool:
	return evaluate_on(expr, RpgUtil.state())

## evaluate() against `state` (the dialogue tab's test state, T12.61, or the game's).
static func evaluate_on(expr: String, state: RpgGameState) -> bool:
	var tokens := _tokens(expr)
	if tokens.is_empty():
		return true
	var result := false
	var op := ""
	var i := 0
	var first := true
	while i < tokens.size():
		var negate := false
		while i < tokens.size() and tokens[i] == "not":
			negate = not negate
			i += 1
		if i >= tokens.size():
			push_error("[RPG-DLG] condition ends after 'not': %s" % expr)
			return false
		var value := _atom(tokens[i], state)
		i += 1
		if negate:
			value = not value
		if first:
			result = value
			first = false
		elif op == "and":
			result = result and value
		else:
			result = result or value
		if i < tokens.size():
			op = tokens[i]
			if op != "and" and op != "or":
				push_error("[RPG-DLG] expected 'and' or 'or' in condition: %s" % expr)
				return false
			i += 1
			if i >= tokens.size():
				push_error("[RPG-DLG] condition ends after '%s': %s" % [op, expr])
				return false
	return result

## True when the expression uses both "and" and "or" (no precedence, so it is easy to misread).
static func mixes_operators(expr: String) -> bool:
	var tokens := _tokens(expr)
	return tokens.has("and") and tokens.has("or")

static func _tokens(expr: String) -> PackedStringArray:
	return expr.strip_edges().split(" ", false)

## The atom prefixes the language knows (for the editor's checks and completion).
const ATOMS: Array[String] = [
	"flag:", "item:", "gold>=", "level>=", "party:", "var:", "quest_active:", "quest_done:",
	"quest_stage:", "quest_failed:", "quest_available:", "quest_ready:", "quest:", "ability:", "count:", "achievement:", "friendship:", "birthday:", "festival",
	"festival_tomorrow", "event:", "courting:", "engaged:", "spouse:",
]
## The atoms of a farm's marriage (T17.26), each with the id of a person.
const MARRIAGE_ATOMS: Array[String] = ["courting:", "engaged:", "spouse:"]
## The flags of the game a farm's marriage keeps its state in (RpgMarriage.FLAG_ENTITY).
const MARRIAGE_FLAGS := "farm_marriage"
## The atoms of a farm's events (T17.25) that are a word and no more.
const EVENT_WORDS: Array[String] = ["festival", "festival_tomorrow"]

## What is wrong with `expr` without evaluating it: unknown or malformed atoms, a dangling
## operator. Empty when the condition is well formed (T12.61: flagged inline in the dock).
static func problems(expr: String) -> PackedStringArray:
	var found: PackedStringArray = []
	var tokens := _tokens(expr)
	var expect_atom := true
	for token in tokens:
		if expect_atom:
			if token == "not":
				continue
			var why := atom_problem(token)
			if why != "":
				found.append(why)
			expect_atom = false
		elif token == "and" or token == "or":
			expect_atom = true
		else:
			found.append("expected 'and' or 'or' before '%s'" % token)
	if not tokens.is_empty() and expect_atom:
		found.append("the condition ends after '%s'" % tokens[tokens.size() - 1])
	if mixes_operators(expr):
		found.append("mixes 'and' and 'or' (read left to right, no precedence)")
	return found

## Why one atom is not understood, or "".
static func atom_problem(atom: String) -> String:
	if atom.begins_with("flag:"):
		var dot := atom.trim_prefix("flag:").rfind(".")
		return "" if dot > 0 else "flag needs <entity>.<key>: '%s'" % atom
	if atom.begins_with("item:"):
		var body := atom.trim_prefix("item:")
		if body.get_slice(">=", 0) == "" or (body.contains(">=") and not body.get_slice(">=", 1).is_valid_int()):
			return "item needs <id>[>=N]: '%s'" % atom
		return ""
	for prefix: String in ["gold>=", "level>="]:
		if atom.begins_with(prefix):
			return "" if atom.trim_prefix(prefix).is_valid_int() else "'%s' needs a number" % atom
	if atom.begins_with("party:") or atom.begins_with("quest_active:") or atom.begins_with("quest_done:") or atom.begins_with("ability:"):
		return "" if atom.get_slice(":", 1) != "" else "'%s' needs an id" % atom
	if atom.begins_with("quest_failed:") or atom.begins_with("quest_available:") or atom.begins_with("quest_ready:") or atom.begins_with("achievement:"):
		return "" if atom.get_slice(":", 1) != "" else "'%s' needs an id" % atom
	if atom.begins_with("count:"):
		var body := atom.trim_prefix("count:")
		var at := body.rfind(">=")
		return "" if at > 0 and body.substr(at + 2).is_valid_int() else "count needs <name>>=N: '%s'" % atom
	if EVENT_WORDS.has(atom):
		return ""
	if atom.begins_with("birthday:") or atom.begins_with("event:") or _is_marriage(atom):
		return "" if atom.get_slice(":", 1) != "" else "'%s' needs an id" % atom
	if atom.begins_with("var:"):
		var body := atom.trim_prefix("var:")
		for op in VAR_OPS:
			var at := body.find(op)
			if at > 0:
				return "" if body.substr(at + op.length()).is_valid_int() else "'%s' needs a number" % atom
		return "var needs <name><op><N>: '%s'" % atom
	if atom.begins_with("friendship:"):
		var body := atom.trim_prefix("friendship:")
		var at := body.find(">=")
		return "" if at > 0 and body.substr(at + 2).is_valid_int() else "friendship needs <id>>=N: '%s'" % atom
	if atom.begins_with("quest_stage:"):
		return "" if atom.trim_prefix("quest_stage:").split(":").size() == 2 else "quest_stage needs <id>:<stage>: '%s'" % atom
	if atom.begins_with("quest:"):
		return "" if atom.contains("=") else "quest needs <id>=<state>: '%s'" % atom
	return "unknown condition '%s'" % atom

static func _atom(atom: String, state: RpgGameState) -> bool:
	if state == null:
		push_error("[RPG-DLG] GameState is not available to evaluate '%s'" % atom)
		return false
	if atom.begins_with("flag:"):
		var body := atom.trim_prefix("flag:")
		var dot := body.rfind(".")
		if dot <= 0:
			return _unknown(atom)
		return RpgUtil.to_bool(state.get_flag(body.substr(0, dot), body.substr(dot + 1), false))
	if atom.begins_with("item:"):
		var body := atom.trim_prefix("item:")
		var need := 1
		if body.contains(">="):
			need = int(body.get_slice(">=", 1))
			body = body.get_slice(">=", 0)
		return state.inventory.count(StringName(body)) >= need
	if atom.begins_with("gold>="):
		return RpgUtil.to_int(state.gold) >= RpgUtil.to_int(atom.trim_prefix("gold>="))
	if atom.begins_with("level>="):
		return RpgUtil.to_int(state.player_stats.level) >= RpgUtil.to_int(atom.trim_prefix("level>="))
	if atom.begins_with("party:"):
		return state.in_party(StringName(atom.trim_prefix("party:")))
	if atom.begins_with("ability:"):
		return state.has_ability(StringName(atom.trim_prefix("ability:")))
	if atom.begins_with("var:"):
		return _compare_var(state, atom)
	if atom.begins_with("friendship:"):
		return _friendship(state, atom)
	if EVENT_WORDS.has(atom) or atom.begins_with("birthday:") or atom.begins_with("event:"):
		return _farm_event(state, atom)
	if _is_marriage(atom):
		return _marriage(state, atom)
	if atom.begins_with("quest_active:"):
		return state.quest_is_active(StringName(atom.trim_prefix("quest_active:")))
	if atom.begins_with("quest_done:"):
		return state.quest_is_done(StringName(atom.trim_prefix("quest_done:")))
	if atom.begins_with("quest_failed:"):
		return state.quest_is_failed(StringName(atom.trim_prefix("quest_failed:")))
	if atom.begins_with("quest_available:"):
		return state.quest_available(StringName(atom.trim_prefix("quest_available:")))
	if atom.begins_with("quest_ready:"):
		return state.quest_ready(StringName(atom.trim_prefix("quest_ready:")))
	if atom.begins_with("achievement:"):
		return state.achievement_unlocked(StringName(atom.trim_prefix("achievement:")))
	if atom.begins_with("count:"):
		var body := atom.trim_prefix("count:")
		var at := body.rfind(">=")
		if at <= 0 or not body.substr(at + 2).is_valid_int():
			return _unknown(atom)
		return state.counter(body.substr(0, at)) >= body.substr(at + 2).to_int()
	if atom.begins_with("quest_stage:"):
		var parts := atom.trim_prefix("quest_stage:").split(":")
		if parts.size() != 2:
			return _unknown(atom)
		return state.quest_state(StringName(parts[0])) == parts[1]
	if atom.begins_with("quest:"):
		var body := atom.trim_prefix("quest:")
		if not body.contains("="):
			return _unknown(atom)
		return str(state.quests.get(body.get_slice("=", 0), "")) == body.get_slice("=", 1)
	return _unknown(atom)

## var:<name><op><N>, e.g. var:bridge_planks>=3.
static func _compare_var(state: RpgGameState, atom: String) -> bool:
	var body := atom.trim_prefix("var:")
	for op in VAR_OPS:
		var at := body.find(op)
		if at <= 0:
			continue
		var right := body.substr(at + op.length())
		if not right.is_valid_int():
			return _unknown(atom)
		var value := state.get_var(body.substr(0, at))
		var wanted := right.to_int()
		match op:
			">=":
				return value >= wanted
			"<=":
				return value <= wanted
			"==":
				return value == wanted
			"!=":
				return value != wanted
			">":
				return value > wanted
			_:
				return value < wanted
	return _unknown(atom)

## friendship:<id>>=<N>, e.g. friendship:anna>=4: the hearts of a person. The friendships are a
## child of the game state that only a farm has (RpgFriendship, found by its name: the script is
## not in the project of another kind); without it nobody has a heart.
static func _friendship(state: RpgGameState, atom: String) -> bool:
	var body := atom.trim_prefix("friendship:")
	var at := body.find(">=")
	if at <= 0 or not body.substr(at + 2).is_valid_int():
		return _unknown(atom)
	var friendship := state.get_node_or_null(RpgGameState.FRIENDSHIP_NODE)
	if friendship == null or not friendship.has_method(&"hearts"):
		return false
	return RpgUtil.to_int(friendship.call(&"hearts", body.substr(0, at))) >= body.substr(at + 2).to_int()

## birthday:<id>, festival, festival_tomorrow, event:<kind>: the days of a farm's year that are
## not like the others. The events are a part of a farm's mode that the game state carries as a
## meta (RpgFarmEvents, found by that name: the script is not in the project of another kind);
## without it no day is a birthday or a festival.
static func _farm_event(state: RpgGameState, atom: String) -> bool:
	if not state.has_meta(FARM_EVENTS_META):
		return false
	var events: Variant = state.get_meta(FARM_EVENTS_META)
	if not is_instance_valid(events) or not (events is Node):
		return false
	var node: Node = events
	if atom == "festival":
		return node.has_method(&"is_festival") and RpgUtil.to_bool(node.call(&"is_festival"))
	if atom == "festival_tomorrow":
		return node.has_method(&"festival_tomorrow") and not RpgUtil.to_dict(node.call(&"festival_tomorrow")).is_empty()
	var id := atom.get_slice(":", 1)
	if id == "":
		return _unknown(atom)
	if atom.begins_with("birthday:"):
		return node.has_method(&"is_birthday") and RpgUtil.to_bool(node.call(&"is_birthday", id))
	return node.has_method(&"has_kind") and RpgUtil.to_bool(node.call(&"has_kind", id))

static func _is_marriage(atom: String) -> bool:
	for prefix in MARRIAGE_ATOMS:
		if atom.begins_with(prefix):
			return true
	return false

## courting:<id>, engaged:<id>, spouse:<id>: the stage of the farmer's marriage with a person,
## from the flags a farm's marriage keeps (`farm_marriage`: `courting` a list of ids, `engaged`
## and `spouse` an id each). Courting is true until the pendant is taken, engaged until the
## wedding's night; a game without marriage has no such flags, and every atom is false.
static func _marriage(state: RpgGameState, atom: String) -> bool:
	var id := atom.get_slice(":", 1)
	if id == "":
		return _unknown(atom)
	var spouse := RpgUtil.to_str(state.get_flag(MARRIAGE_FLAGS, "spouse", ""))
	var engaged := RpgUtil.to_str(state.get_flag(MARRIAGE_FLAGS, "engaged", ""))
	if atom.begins_with("spouse:"):
		return spouse == id
	if atom.begins_with("engaged:"):
		return engaged == id
	var courting := RpgUtil.to_array(state.get_flag(MARRIAGE_FLAGS, "courting", []))
	return courting.has(id) and spouse != id and engaged != id

## The meta of the game state a farm's events are found under (RpgFarmEvents.STATE_META).
const FARM_EVENTS_META := &"rpg_farm_events"

static func _unknown(atom: String) -> bool:
	push_error("[RPG-DLG] unknown condition atom '%s'" % atom)
	return false
