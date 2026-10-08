class_name RpgBattleAi
extends RefCounted
## Scripted enemy turns: the rules in behavior.turn_based_rules, tried in order; the first that
## holds (and wins its chance roll) is used. When none does, the controller rolls the weights.
##
##   {"when": "hp<50 and every:2", "use": "fire", "target": "weakest", "chance": 0.5, "once": true}
##
## `use` is a command id (attack, defend) or a skill id. `when` atoms, joined with "and":
##   hp<50  mp>=4  foe_hp<30  round>=3   (hp and foe_hp are percents; < <= > >= == !=)
##   every:3  alone  ally_down  has:<status>  foe_has:<status>  foe_lacks:<status>  always
## and the dialogue conditions (flag:..., var:..., quest_done:...). `target`: random (default),
## weakest, strongest, self. A status skill aims at someone who does not have the status yet.

const TARGET_MODES: Array[String] = ["", "random", "weakest", "strongest", "self"]
const COMPARED: Array[String] = ["foe_hp", "hp", "mp", "round"]
const OPS: Array[String] = ["<=", ">=", "==", "!=", "<", ">"]
const STORY_PREFIXES: Array[String] = ["flag:", "item:", "gold>=", "level>=", "party:", "var:", "quest", "not "]

## The choice of the first rule that holds, or {} (the controller falls back on the weights).
static func from_rules(actor: RpgBattleActor, battle: RpgBattleController) -> Dictionary:
	var rules: Array = actor.behavior.get("turn_based_rules", [])
	for i in rules.size():
		if not (rules[i] is Dictionary):
			continue
		var rule: Dictionary = rules[i]
		var once := RpgUtil.to_bool(rule.get("once", false))
		if once and actor.used_rules.has(i):
			continue
		if not holds(str(rule.get("when", "")), actor, battle):
			continue
		if not RpgBattleMath.roll_chance(RpgUtil.to_float(rule.get("chance", 1.0)), battle.rng):
			continue
		var choice := plan(actor, battle, StringName(str(rule.get("use", ""))), str(rule.get("target", "")))
		if choice.is_empty():
			continue
		if once:
			actor.used_rules[i] = true
		return choice
	return {}

## {command, targets, item_id, skill_id} for using `use` (a command or a skill id), or {} when the
## actor cannot (no such thing, not enough MP, silenced, nobody to aim at).
static func plan(actor: RpgBattleActor, battle: RpgBattleController, use: StringName, mode: String) -> Dictionary:
	var command := battle.command_by_id(use)
	var skill_id := &""
	if command == null:
		var skill := battle.skill(use)
		command = battle.command_by_id(&"skill")
		if skill == null or command == null or not actor.can_cast() or not actor.can_pay(skill.mp_cost):
			return {}
		skill_id = use
	elif command.id in [&"item", &"run", &"skill"] or not command.can_use(actor, battle):
		return {}
	var kind := battle.targets_of(command, skill_id)
	var list := battle.candidates(actor, command, skill_id)
	var picked: Array[RpgBattleActor] = []
	if kind == RpgBattleCommand.TARGET_SELF:
		picked.append(actor)
	elif kind == RpgBattleCommand.TARGET_ALL_ENEMIES or kind == RpgBattleCommand.TARGET_ALL_ALLIES:
		picked = list
	else:
		var skill := battle.skill(skill_id)
		if skill != null and skill.kind == RpgSkillDefinition.Kind.STATUS and skill.status != &"":
			list = _lacking(list, skill.status)
		var target := pick(list, mode, actor, battle)
		if target != null:
			picked.append(target)
	if picked.is_empty():
		return {}
	return {"command": command, "targets": picked, "item_id": &"", "skill_id": skill_id}

static func _lacking(list: Array[RpgBattleActor], status: StringName) -> Array[RpgBattleActor]:
	var out: Array[RpgBattleActor] = []
	for a in list:
		if not a.has_status(status):
			out.append(a)
	return out

static func _hp_share(a: RpgBattleActor) -> float:
	return float(a.stats.hp) / float(maxi(1, a.max_hp()))

## One of `list` by `mode` (random draws from the battle's rng; ties go to the first).
static func pick(list: Array[RpgBattleActor], mode: String, actor: RpgBattleActor, battle: RpgBattleController) -> RpgBattleActor:
	if list.is_empty():
		return null
	match mode:
		"self":
			return actor if list.has(actor) else null
		"weakest", "strongest":
			var best: RpgBattleActor = list[0]
			for a in list:
				var share := _hp_share(a)
				if (mode == "weakest" and share < _hp_share(best)) or (mode == "strongest" and share > _hp_share(best)):
					best = a
			return best
	var drawn: RpgBattleActor = battle.rng.pick(list)
	return drawn

## True when every atom of `when` holds ("" and "always" always do).
static func holds(when: String, actor: RpgBattleActor, battle: RpgBattleController) -> bool:
	for raw in when.split(" and ", false):
		var atom := raw.strip_edges()
		if atom == "" or atom == "always":
			continue
		if not _atom(atom, actor, battle):
			return false
	return true

static func _atom(atom: String, actor: RpgBattleActor, battle: RpgBattleController) -> bool:
	var allies := battle.allies_of(actor)
	var foes := RpgBattleController.living(battle.opponents_of(actor))
	match atom:
		"alone":
			return RpgBattleController.living(allies).size() <= 1
		"ally_down":
			return RpgBattleController.living(allies).size() < allies.size()
	if atom.begins_with("every:"):
		var n := atom.trim_prefix("every:").to_int()
		return n > 0 and battle.round_number % n == 0
	if atom.begins_with("has:"):
		return actor.has_status(StringName(atom.trim_prefix("has:")))
	if atom.begins_with("foe_has:") or atom.begins_with("foe_lacks:"):
		var lacks := atom.begins_with("foe_lacks:")
		var status := StringName(atom.get_slice(":", 1))
		for f in foes:
			if f.has_status(status) != lacks:
				return true
		return false
	var compared := _compare(atom)
	if not compared.is_empty():
		var value := _value_of(str(compared["what"]), actor, foes, battle)
		return _test(value, str(compared["op"]), RpgUtil.to_int(compared["n"]))
	return RpgCondition.evaluate(atom)

## {what, op, n} for "hp<50" and the like, else {}.
static func _compare(atom: String) -> Dictionary:
	for what in COMPARED:
		if not atom.begins_with(what):
			continue
		var rest := atom.trim_prefix(what).strip_edges()
		for op in OPS:
			if rest.begins_with(op):
				var number := rest.trim_prefix(op).strip_edges()
				if number.is_valid_int():
					return {"what": what, "op": op, "n": number.to_int()}
		return {}
	return {}

static func _value_of(what: String, actor: RpgBattleActor, foes: Array[RpgBattleActor], battle: RpgBattleController) -> int:
	match what:
		"hp":
			return floori(_hp_share(actor) * 100.0)
		"mp":
			return actor.stats.mp
		"foe_hp":
			var lowest := 100
			for f in foes:
				lowest = mini(lowest, floori(_hp_share(f) * 100.0))
			return lowest
	return battle.round_number

static func _test(value: int, op: String, n: int) -> bool:
	match op:
		"<":
			return value < n
		"<=":
			return value <= n
		">":
			return value > n
		">=":
			return value >= n
		"==":
			return value == n
	return value != n

## Problems of a rule list as text: what the content check reports. `known_uses` holds the command
## and skill ids that exist.
static func problems_of(rules: Variant, known_uses: Array) -> PackedStringArray:
	var out := PackedStringArray()
	if rules == null:
		return out
	if not (rules is Array):
		out.append("turn_based_rules is not a list")
		return out
	var list: Array = rules
	for i in list.size():
		if not (list[i] is Dictionary):
			out.append("rule %d is not a dictionary" % (i + 1))
			continue
		var rule: Dictionary = list[i]
		var use := str(rule.get("use", ""))
		if use == "":
			out.append("rule %d has no 'use'" % (i + 1))
		elif not known_uses.has(StringName(use)):
			out.append("rule %d uses '%s', which is neither a command nor a skill" % [i + 1, use])
		var mode := str(rule.get("target", ""))
		if not TARGET_MODES.has(mode):
			out.append("rule %d: unknown target '%s'" % [i + 1, mode])
		for raw in str(rule.get("when", "")).split(" and ", false):
			var atom := raw.strip_edges()
			if not _atom_known(atom):
				out.append("rule %d: unknown condition '%s'" % [i + 1, atom])
	return out

static func _atom_known(atom: String) -> bool:
	if atom in ["", "always", "alone", "ally_down"]:
		return true
	for prefix: String in ["has:", "foe_has:", "foe_lacks:"]:
		if atom.begins_with(prefix):
			return RpgBattleStatus.is_known(StringName(atom.trim_prefix(prefix)))
	if atom.begins_with("every:"):
		return atom.trim_prefix("every:").is_valid_int()
	if not _compare(atom).is_empty():
		return true
	for prefix in STORY_PREFIXES:
		if atom.begins_with(prefix):
			return true
	return false
