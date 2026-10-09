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
	"quest_stage:", "quest:",
]

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
	if atom.begins_with("party:") or atom.begins_with("quest_active:") or atom.begins_with("quest_done:"):
		return "" if atom.get_slice(":", 1) != "" else "'%s' needs an id" % atom
	if atom.begins_with("var:"):
		var body := atom.trim_prefix("var:")
		for op in VAR_OPS:
			var at := body.find(op)
			if at > 0:
				return "" if body.substr(at + op.length()).is_valid_int() else "'%s' needs a number" % atom
		return "var needs <name><op><N>: '%s'" % atom
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
