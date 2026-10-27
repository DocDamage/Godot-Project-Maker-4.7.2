class_name RpgBattleController
extends Node
## The battle state machine. It knows nothing about nodes: a UI (optional) is asked for commands
## and shows the log, `auto_choose` replaces the UI for tests and the smoke run.
##
##   INIT -> ROUND_START -> PLAYER_CHOOSE -> ENEMY_CHOOSE -> EXECUTE -> CHECK
##        -> (ROUND_START | VICTORY | DEFEAT | ESCAPED) -> END
##
## With no UI and a synchronous `auto_choose` the whole battle runs inside one call of run().

enum State { INIT, ROUND_START, PLAYER_CHOOSE, ENEMY_CHOOSE, EXECUTE, CHECK, VICTORY, DEFEAT, ESCAPED, END }

signal state_changed(new_state: int)
## Emitted for every resolved action, before the UI shows it (the scene plays hit effects here).
signal entries_resolved(entries: Array)
signal finished(result: RpgEncounterResult)

const COMMANDS_DIR := "res://game/data/battle_commands"
const SKILLS_DIR := "res://game/data/skills"
const HERO_PATH := "res://game/data/actors/hero.tres"
const COMMAND_ORDER: Array[StringName] = [&"attack", &"defend", &"item", &"skill", &"run"]
const MAX_ROUNDS := 500  # a runaway guard: a battle that goes on this long is a bug
const MAX_PER_SIDE := 4
const HEAL_BELOW := 0.25

const AttackCommand := preload("commands/attack_command.gd")
const DefendCommand := preload("commands/defend_command.gd")
const ItemCommand := preload("commands/item_command.gd")
const SkillCommand := preload("commands/skill_command.gd")
const RunCommand := preload("commands/run_command.gd")

var data: RpgEncounterData
## GameState.rng; tests hand over a subclass with fixed rolls.
var rng: RpgRng = null
## Optional UI: request_command(actor, battle) -> Dictionary, show_log(entries),
## show_message(text) and show_rewards(result, level_ups); all of them may await.
var ui: RpgBattleUi = null
## Replaces the UI: called as auto_choose.call(actor, battle), returns {command_id, target_index}
## (target_index counts the living candidates of that command).
var auto_choose: Callable = Callable()
var party: Array[RpgBattleActor] = []
var enemies: Array[RpgBattleActor] = []
var commands: Array[RpgBattleCommand] = []
## {id: RpgSkillDefinition} from game/data/skills (tests hand theirs over).
var skills: Dictionary = {}
var can_escape := true
var escaped := false
var state: State = State.INIT
var round_number := 0
var history: Array[Dictionary] = []  # every log entry of the battle
var level_ups: Array[Dictionary] = []  # [{actor, level}] after a victory
var result: RpgEncounterResult = null

var _choices: Dictionary = {}  # actor -> {command, targets, item_id, skill_id}
var _state_node: Node = null
var _idle: RpgBattleCommand = null  # the "turn" of a battler that cannot act (asleep)

## Builds the battlers from the encounter data and GameState.
func setup(p_data: RpgEncounterData, p_rng: RpgRng = null) -> void:
	data = p_data
	_state_node = RpgUtil.state()
	rng = p_rng
	if rng == null and _state_node != null:
		rng = _state_node.get("rng")
	if rng == null:
		rng = RpgRng.new()
	can_escape = data.can_escape if data != null else true
	if commands.is_empty():
		commands = load_commands()
	if skills.is_empty():
		skills = RpgSkillDefinition.load_dir(SKILLS_DIR)
	party = _build_party()
	enemies = _build_enemies(data.enemies if data != null else [])

## Hands over ready-made battlers (tests).
func set_actors(p_party: Array[RpgBattleActor], p_enemies: Array[RpgBattleActor]) -> void:
	party = p_party
	enemies = p_enemies
	if commands.is_empty():
		commands = load_commands()
	if skills.is_empty():
		skills = RpgSkillDefinition.load_dir(SKILLS_DIR)
	if _state_node == null:
		_state_node = RpgUtil.state()
	if rng == null:
		rng = RpgRng.new()

## game/data/battle_commands/*.tres in the standard order, then any extra ones by id. A missing
## file falls back to the built-in command.
static func load_commands() -> Array[RpgBattleCommand]:
	var by_id: Dictionary = {}
	var dir := DirAccess.open(COMMANDS_DIR)
	if dir != null:
		var files := dir.get_files()
		files.sort()
		for f in files:
			var res := load(COMMANDS_DIR + "/" + f.trim_suffix(".remap")) as RpgBattleCommand
			if res != null and not by_id.has(res.id):
				by_id[res.id] = res
	var out: Array[RpgBattleCommand] = []
	for command_id in COMMAND_ORDER:
		if by_id.has(command_id):
			out.append(by_id[command_id])
		else:
			out.append(_builtin(command_id))
	var extra: Array[StringName] = []
	for command_id: StringName in by_id.keys():
		if not COMMAND_ORDER.has(command_id):
			extra.append(command_id)
	extra.sort()
	for command_id in extra:
		out.append(by_id[command_id])
	return out

static func _builtin(command_id: StringName) -> RpgBattleCommand:
	match command_id:
		&"attack":
			return AttackCommand.new()
		&"defend":
			return DefendCommand.new()
		&"item":
			return ItemCommand.new()
		&"skill":
			return SkillCommand.new()
		_:
			return RunCommand.new()

func command_by_id(command_id: StringName) -> RpgBattleCommand:
	for c in commands:
		if c.id == command_id:
			return c
	return null

func skill(skill_id: StringName) -> RpgSkillDefinition:
	if skill_id == &"" or not skills.has(skill_id):
		return null
	var found: RpgSkillDefinition = skills[skill_id]
	return found

## The skills an actor can choose from: what its definition lists for its level (the player side),
## or the skills its behavior names (enemies). Unknown ids are left out.
func skills_of(actor: RpgBattleActor) -> Array[RpgSkillDefinition]:
	var out: Array[RpgSkillDefinition] = []
	var ids: Array[StringName] = []
	if actor.is_player_side:
		var def := actor.actor_definition()
		if def != null:
			ids = def.skills_at(actor.stats.level)
		if _state_node != null and _state_node.has_method(&"learned_battle_skills"):
			for learned: Variant in RpgUtil.to_array(_state_node.call(&"learned_battle_skills", actor.id)):
				if not ids.has(StringName(str(learned))):
					ids.append(StringName(str(learned)))  # what its skill trees taught (1.5.0)
	else:
		var weights: Dictionary = actor.behavior.get("turn_based", {})
		for key: Variant in weights.keys():
			ids.append(StringName(str(key)))
		var rules: Array = actor.behavior.get("turn_based_rules", [])
		for rule: Variant in rules:
			if rule is Dictionary:
				var rule_dict: Dictionary = rule
				ids.append(StringName(str(rule_dict.get("use", ""))))
	for skill_id in ids:
		var found := skill(skill_id)
		if found != null and not out.has(found):
			out.append(found)
	return out

## Whom a command aims at: a skill's own `targets`, else the command's.
func targets_of(command: RpgBattleCommand, skill_id: StringName = &"") -> int:
	if command != null and command.id == &"skill":
		var chosen := skill(skill_id)
		if chosen != null:
			return chosen.targets
	return command.targets if command != null else RpgBattleCommand.TARGET_ONE_ENEMY

# ---------------------------------------------------------------- queries used by commands

func opponents_of(actor: RpgBattleActor) -> Array[RpgBattleActor]:
	return enemies if actor.is_player_side else party

func allies_of(actor: RpgBattleActor) -> Array[RpgBattleActor]:
	return party if actor.is_player_side else enemies

static func living(actors: Array[RpgBattleActor]) -> Array[RpgBattleActor]:
	var out: Array[RpgBattleActor] = []
	for a in actors:
		if a.alive:
			out.append(a)
	return out

static func _one(actor: RpgBattleActor) -> Array[RpgBattleActor]:
	var out: Array[RpgBattleActor] = [actor]
	return out

## The inventory an actor's items come from: GameState's for the player side, its own for enemies.
func inventory_of(actor: RpgBattleActor) -> RpgInventory:
	if actor.is_player_side and _state_node != null:
		var inventory: RpgInventory = _state_node.get("inventory")
		return inventory
	return actor.inventory

## Who a command (with the skill for the skill command) can be aimed at, for `actor`.
func candidates(actor: RpgBattleActor, command: RpgBattleCommand, skill_id: StringName = &"") -> Array[RpgBattleActor]:
	match targets_of(command, skill_id):
		RpgBattleCommand.TARGET_SELF:
			return _one(actor)
		RpgBattleCommand.TARGET_ONE_ALLY, RpgBattleCommand.TARGET_ALL_ALLIES:
			return living(allies_of(actor))
		_:
			return living(opponents_of(actor))

static func aims_at_all(kind: int) -> bool:
	return kind == RpgBattleCommand.TARGET_ALL_ENEMIES or kind == RpgBattleCommand.TARGET_ALL_ALLIES

# ---------------------------------------------------------------- the machine

func _set_state(s: State) -> void:
	state = s
	state_changed.emit(int(s))

func _decided() -> bool:
	return escaped or living(enemies).is_empty() or living(party).is_empty()

## Runs the battle to its end and returns the result (also emitted as `finished`).
func run() -> RpgEncounterResult:
	_set_state(State.INIT)
	if party.is_empty() or enemies.is_empty():
		push_error("[RPG-COMBAT] a battle needs at least one battler on each side")
		return _end(RpgEncounterResult.Outcome.ESCAPED)
	var outcome := RpgEncounterResult.Outcome.ESCAPED
	while true:
		round_number += 1
		_set_state(State.ROUND_START)
		for a in party + enemies:
			a.defending = false
		_choices.clear()
		_set_state(State.PLAYER_CHOOSE)
		for a in living(party):
			if a.can_act():
				_choices[a] = await _choose_player(a)
			else:
				_choices[a] = _idle_choice(a)
		_set_state(State.ENEMY_CHOOSE)
		for a in living(enemies):
			_choices[a] = _choose_enemy(a) if a.can_act() else _idle_choice(a)
		_set_state(State.EXECUTE)
		await _execute_round()
		if not _decided():
			await _end_round()
		_set_state(State.CHECK)
		if living(enemies).is_empty():
			outcome = RpgEncounterResult.Outcome.VICTORY
			break
		if living(party).is_empty():
			outcome = RpgEncounterResult.Outcome.DEFEAT
			break
		if escaped:
			outcome = RpgEncounterResult.Outcome.ESCAPED
			break
		if round_number >= MAX_ROUNDS:
			push_error("[RPG-COMBAT] the battle did not end after %d rounds" % MAX_ROUNDS)
			break
	match outcome:
		RpgEncounterResult.Outcome.VICTORY:
			_set_state(State.VICTORY)
			await _victory()
		RpgEncounterResult.Outcome.DEFEAT:
			_set_state(State.DEFEAT)
			await _show_message(RpgBattleText.t("BATTLE_DEFEATED"))
		_:
			_set_state(State.ESCAPED)
	return _end(outcome)

func _end(outcome: RpgEncounterResult.Outcome) -> RpgEncounterResult:
	if outcome != RpgEncounterResult.Outcome.DEFEAT and _state_node != null and _state_node.has_method("revive_party"):
		_state_node.call("revive_party")  # a member who fell is back on their feet, at 1 HP (defeat: the policy decides)
	if result == null:
		result = RpgEncounterResult.new()
		result.outcome = outcome
		result.entity_id = data.entity_id if data != null else ""
	_set_state(State.END)
	finished.emit(result)
	return result

# ---------------------------------------------------------------- choosing

func _auto_active() -> bool:
	return auto_choose.is_valid()

func _choose_player(actor: RpgBattleActor) -> Dictionary:
	var raw: Variant = null
	if _auto_active():
		raw = auto_choose.call(actor, self)
	elif ui != null:
		raw = await ui.request_command(actor, self)
	var chosen: Dictionary = {}
	if raw is Dictionary:
		chosen = raw
	return _sanitize(actor, chosen)

## Turns {command_id, target_index, item_id, skill_id} into a usable choice. Anything unknown or
## not allowed (a skill the actor does not know or cannot pay for) becomes a plain attack on the
## first enemy.
func _sanitize(actor: RpgBattleActor, raw: Dictionary) -> Dictionary:
	var command := command_by_id(StringName(str(raw.get("command_id", "attack"))))
	var skill_id := StringName(str(raw.get("skill_id", "")))
	if command != null and command.id == &"skill" and not _may_use_skill(actor, command, skill_id):
		command = null
	if command == null or not command.can_use(actor, self):
		command = command_by_id(&"attack")
		raw = {}
		skill_id = &""
	var list := candidates(actor, command, skill_id)
	var index := clampi(RpgUtil.to_int(raw.get("target_index", 0)), 0, maxi(0, list.size() - 1))
	var picked: Array[RpgBattleActor] = []
	if aims_at_all(targets_of(command, skill_id)):
		picked = list
	elif not list.is_empty():
		picked = _one(list[index])
	return {"command": command, "targets": picked, "item_id": StringName(str(raw.get("item_id", ""))), "skill_id": skill_id}

func _may_use_skill(actor: RpgBattleActor, command: RpgBattleCommand, skill_id: StringName) -> bool:
	var chosen := skill(skill_id)
	if chosen == null or not command.has_method("usable_skills"):
		return false
	var usable: Array = command.call("usable_skills", actor, self)
	return usable.has(chosen)

## The turn of a battler that cannot act: it is skipped (and the log says why).
func _idle_choice(actor: RpgBattleActor) -> Dictionary:
	if _idle == null:
		_idle = RpgBattleCommand.new()
		_idle.id = &"idle"
	return {"command": _idle, "targets": _one(actor), "item_id": &"", "skill_id": &""}

## Enemy AI: the rules of behavior.turn_based_rules first (RpgBattleAi); then heal when below 25%
## HP and holding a healing item; otherwise roll the weights in behavior.turn_based
## ({"attack": 1.0, "defend": 0.0}; a key may be a skill id) and aim at a random living
## player-side actor. What the actor cannot do (a skill without the MP) becomes an attack.
func _choose_enemy(actor: RpgBattleActor) -> Dictionary:
	var scripted := RpgBattleAi.from_rules(actor, self)
	if not scripted.is_empty():
		return scripted
	var item_id := _heal_item(actor)
	if item_id != &"" and float(actor.stats.hp) < float(actor.stats.max_hp) * HEAL_BELOW:
		return {"command": command_by_id(&"item"), "targets": _one(actor), "item_id": item_id, "skill_id": &""}
	var weights: Dictionary = actor.behavior.get("turn_based", {"attack": 1.0, "defend": 0.0})
	var choice := RpgBattleAi.plan(actor, self, _roll_weighted(weights), "random")
	if choice.is_empty():
		choice = RpgBattleAi.plan(actor, self, &"attack", "random")
	if choice.is_empty():
		var nobody: Array[RpgBattleActor] = []
		choice = {"command": command_by_id(&"attack"), "targets": nobody, "item_id": &"", "skill_id": &""}
	return choice

func _roll_weighted(weights: Dictionary) -> StringName:
	var keys: Array = weights.keys()
	keys.sort()
	var total := 0.0
	for k: Variant in keys:
		total += maxf(0.0, RpgUtil.to_float(weights[k]))
	if total <= 0.0:
		return &"attack"
	var roll: float = rng.randf() * total
	for k: Variant in keys:
		roll -= maxf(0.0, RpgUtil.to_float(weights[k]))
		if roll < 0.0:
			return StringName(str(k))
	return StringName(str(keys[keys.size() - 1]))

func _heal_item(actor: RpgBattleActor) -> StringName:
	if actor.inventory == null:
		return &""
	for slot in actor.inventory.slots:
		var item_id: StringName = slot["item_id"]
		var def := actor.inventory.definition(item_id)
		if def != null and def.use_effect == &"heal" and RpgUtil.to_int(slot["qty"]) > 0:
			return item_id
	return &""

# ---------------------------------------------------------------- executing

func _execute_round() -> void:
	var entries: Array = []
	for actor: RpgBattleActor in _choices.keys():
		entries.append({"actor": actor, "command": _choices[actor]["command"]})
	for entry: Dictionary in RpgTurnManager.order(entries):
		var actor: RpgBattleActor = entry["actor"]
		if not actor.alive:
			continue
		var choice: Dictionary = _choices[actor]
		var log_entries: Array[Dictionary] = []
		if not actor.can_act():
			log_entries.append(RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_ASLEEP", [actor.display_name]), actor))
		else:
			var command: RpgBattleCommand = choice["command"]
			var chosen: Array[RpgBattleActor] = choice["targets"]
			var skill_id: StringName = choice.get("skill_id", &"")
			var targets := _live_targets(actor, command, chosen, skill_id)
			actor.chosen_item = choice["item_id"]
			actor.chosen_skill = skill_id
			log_entries = command.execute(actor, targets, self)
			actor.chosen_item = &""
			actor.chosen_skill = &""
		await _log(log_entries)
		if _decided():
			break

## Poison and regen, and the statuses count a round down, for everyone still standing.
func _end_round() -> void:
	for actor: RpgBattleActor in living(party) + living(enemies):
		var log_entries := RpgBattleEffects.end_of_round(actor)
		if not log_entries.is_empty():
			await _log(log_entries)
		if _decided():
			return

func _log(log_entries: Array[Dictionary]) -> void:
	history.append_array(log_entries)
	entries_resolved.emit(log_entries)
	if ui != null and not _auto_active():
		await ui.show_log(log_entries)

## The chosen targets that still stand; when none does, the first living candidate takes over (all
## of them for a command that aims at a whole side).
func _live_targets(actor: RpgBattleActor, command: RpgBattleCommand, chosen: Array[RpgBattleActor], skill_id: StringName = &"") -> Array[RpgBattleActor]:
	var out := living(chosen)
	var kind := targets_of(command, skill_id)
	if out.is_empty() and kind != RpgBattleCommand.TARGET_SELF:
		var fallback := candidates(actor, command, skill_id)
		if aims_at_all(kind):
			out = fallback
		elif not fallback.is_empty():
			out = _one(fallback[0])
	return out

# ---------------------------------------------------------------- rewards

func _victory() -> void:
	result = RpgEncounterResult.new()
	result.outcome = RpgEncounterResult.Outcome.VICTORY
	result.entity_id = data.entity_id if data != null else ""
	var loot: Dictionary = {}  # item id -> qty, in first-seen order
	for e in enemies:
		var def := e.definition as RpgEnemyDefinition
		if def == null:
			continue
		result.xp += def.xp_reward
		result.gold += def.gold_reward
		if _state_node != null and _state_node.has_method(&"note_defeat"):
			_state_node.call(&"note_defeat", def.id)  # the counters of achievements (1.5.0)
		if def.loot != null:
			for drop in def.loot.roll(rng):
				loot[drop["item_id"]] = RpgUtil.to_int(loot.get(drop["item_id"], 0)) + RpgUtil.to_int(drop["qty"])
	for item_id: Variant in loot.keys():
		result.items.append({"item_id": item_id, "qty": loot[item_id]})
	_apply_rewards()
	if ui != null and not _auto_active():
		await ui.show_rewards(result, level_ups)

func _apply_rewards() -> void:
	for member in living(party):
		var before := member.stats.level
		var gained := _grant_xp(member, result.xp)
		if gained > 0:
			level_ups.append({"actor": member, "level": before + gained})
			RpgUtil.notify(RpgBattleText.t("BATTLE_LEVEL_UP", [member.display_name, before + gained]))
	if _state_node != null:
		_state_node.set("gold", RpgUtil.to_int(_state_node.get("gold")) + result.gold)
		if _state_node.has_method(&"give_items"):
			_state_node.call(&"give_items", result.items)  # what does not fit waits for room
		else:
			var inv: RpgInventory = _state_node.get("inventory")
			for drop in result.items:
				var drop_id: StringName = drop["item_id"]
				inv.add(drop_id, RpgUtil.to_int(drop["qty"]))

## The player and the members go through GameState so experience_gained / level_up are emitted.
func _grant_xp(member: RpgBattleActor, xp: int) -> int:
	if _state_node != null and member.is_player_side and RpgUtil.to_bool(_state_node.call("in_party", member.id)):
		return RpgUtil.to_int(_state_node.call("give_experience_to", member.id, xp))
	return member.stats.add_experience(xp)

func _show_message(text: String) -> void:
	if ui != null and not _auto_active():
		await ui.show_message(text)

# ---------------------------------------------------------------- building the sides

func _build_party() -> Array[RpgBattleActor]:
	var out: Array[RpgBattleActor] = []
	if _state_node == null:
		return out
	var hero: RpgActorDefinition = null
	if ResourceLoader.exists(HERO_PATH):
		hero = load(HERO_PATH) as RpgActorDefinition
	var hero_name := hero.display_name if hero != null and hero.display_name != "" else "Hero"
	var player_id: StringName = _state_node.get("player_actor_id")
	var player_stats: RpgStats = _state_node.get("player_stats")
	var game := RpgUtil.state()
	var player := RpgBattleActor.make(player_id, hero_name, player_stats, true)
	if hero != null:
		player.definition = hero
		player.sprite_frames = hero.sprite_frames
		player.portrait = hero.portrait
	out.append(player)
	var members: Array = _state_node.get("party")
	for member: Dictionary in members:
		if out.size() >= MAX_PER_SIDE:
			break
		var member_id: StringName = member["actor_id"]
		var member_stats: RpgStats = member["stats"]
		var member_actor := RpgBattleActor.make(member_id, game.actor_name(member_id) if game != null else String(member_id).capitalize(), member_stats, true)
		var member_def: RpgActorDefinition = game.actor_definition(member_id) if game != null else null
		if member_def != null:
			member_actor.definition = member_def
			member_actor.sprite_frames = member_def.sprite_frames
			member_actor.portrait = member_def.portrait
		out.append(member_actor)
	return out

func _build_enemies(defs: Array) -> Array[RpgBattleActor]:
	var out: Array[RpgBattleActor] = []
	var totals: Dictionary = {}
	for d: RpgEnemyDefinition in defs:
		totals[d] = RpgUtil.to_int(totals.get(d, 0)) + 1
	var seen: Dictionary = {}
	for d: RpgEnemyDefinition in defs:
		if out.size() >= MAX_PER_SIDE:
			break
		var def := d
		if def == null:
			continue
		var n := RpgUtil.to_int(seen.get(def, 0))
		seen[def] = n + 1
		var base_name := def.display_name if def.display_name != "" else String(def.id).capitalize()
		var suffix := "" if RpgUtil.to_int(totals[def]) == 1 else " " + char(65 + n)
		var stats := RpgStats.new()
		if def.base_stats != null:
			stats = def.base_stats.duplicate(true) as RpgStats
		stats.hp = stats.max_hp
		var actor := RpgBattleActor.make(StringName("%s_%d" % [def.id, n]), base_name + suffix, stats, false)
		actor.definition = def
		actor.sprite_frames = def.sprite_frames
		actor.portrait = def.portrait
		actor.behavior = def.behavior.duplicate(true)
		var pockets: Array = def.behavior.get("items", [])
		_give_items(actor, pockets)
		out.append(actor)
	return out

func _give_items(actor: RpgBattleActor, items: Array) -> void:
	if items.is_empty():
		return
	actor.inventory = RpgInventory.new()
	if _state_node != null:
		actor.inventory.registry = _state_node.get("items")
	for entry: Variant in items:  # slots are filled directly: an enemy's pockets are not news for the bus
		var item_id := StringName(str(entry))
		var qty := 1
		if entry is Dictionary:
			var pocket: Dictionary = entry
			item_id = StringName(str(pocket.get("item_id", "")))
			qty = RpgUtil.to_int(pocket.get("qty", 1))
		if item_id != &"" and qty > 0:
			actor.inventory.slots.append({"item_id": item_id, "qty": qty})
