class_name RpgCondition
extends RefCounted
## Condition mini-language, a pure function of GameState.
##
##   expr := term (("and" | "or") term)*      term := ["not"] atom
##
## Evaluated left to right with NO operator precedence. Atoms:
##   flag:<entity>.<key>    item:<id>[>=N]    gold>=N    level>=N    quest:<id>=<state>
##   quest_active:<id>    quest_done:<id>    quest_stage:<id>:<stage>    party:<actor id>
##   var:<name><op><N>    (op is one of >= <= == != > <; a variable never set is 0)
## Unknown atoms are false and log "[RPG-DLG] unknown condition atom".

## The comparison operators of var:, longest first so that ">=" is not read as ">".
const VAR_OPS: Array[String] = [">=", "<=", "==", "!=", ">", "<"]

static func evaluate(expr: String) -> bool:
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
		var value := _atom(tokens[i])
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

static func _atom(atom: String) -> bool:
	var state := RpgUtil.state()
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
	if atom.begins_with("var:"):
		return _compare_var(state, atom)
	if atom.begins_with("quest_active:"):
		return state.quest_is_active(StringName(atom.trim_prefix("quest_active:")))
	if atom.begins_with("quest_done:"):
		return state.quest_is_done(StringName(atom.trim_prefix("quest_done:")))
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

static func _unknown(atom: String) -> bool:
	push_error("[RPG-DLG] unknown condition atom '%s'" % atom)
	return false
