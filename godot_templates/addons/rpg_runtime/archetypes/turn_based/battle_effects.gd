class_name RpgBattleEffects
extends RefCounted
## What attacks, skills and statuses do to a battler, as log entries (RpgBattleCommand.entry). The
## commands call these; the numbers come from RpgBattleMath with the battle's rng.

static func _t(key: String, args: Array = []) -> String:
	return RpgBattleText.t(key, args)

static func _entry(type: String, text: String, target: RpgBattleActor = null, amount: int = 0, crit: bool = false) -> Dictionary:
	return RpgBattleCommand.entry(type, text, target, amount, crit)

## A plain attack: the hit roll, the damage roll, the element of the weapon (or the actor) and the
## status it may carry.
static func attack(user: RpgBattleActor, target: RpgBattleActor, battle: RpgBattleController) -> Array[Dictionary]:
	return strike(user, target, battle, 0, user.attack_element(), user.attack_status(), true)

## A physical hit with `power` added to the attack. A sleeping target is always hit. `plain` picks
## the log line of a plain attack ("X attacks Y for N damage") over a skill's ("Y takes N damage").
static func strike(user: RpgBattleActor, target: RpgBattleActor, battle: RpgBattleController, power: int, element: StringName, status: Dictionary, plain: bool = false) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var chance := 1.0
	if target.can_act():
		chance = RpgBattleMath.hit_chance(user.stat(&"speed"), target.stat(&"speed"), target.stat_f(&"evade"), user.hit_factor())
	if not RpgBattleMath.roll_hit(chance, battle.rng):
		out.append(_entry("miss", _t("BATTLE_MISS", [user.display_name, target.display_name]), target))
		return out
	var roll := RpgBattleMath.roll_damage(user.stat(&"attack") + power, target.stat(&"defense"), target.defending, battle.rng)
	var crit := RpgUtil.to_bool(roll["crit"])
	var state := RpgUtil.state()
	if user.is_player_side and state != null:
		state.wear_stats(user.stats, &"weapon")  # only gear with a durability wears (1.5.0)
	var key := "BATTLE_SKILL_HIT"
	var args: Array = [target.display_name]
	if plain:
		key = "BATTLE_ATTACK_CRIT" if crit else "BATTLE_ATTACK_HIT"
		args = [user.display_name, target.display_name]
	out.append_array(damage(target, RpgUtil.to_int(roll["amount"]), element, crit, key, args))
	if not status.is_empty():
		out.append_array(inflict(target, StringName(str(status.get("status", ""))), RpgUtil.to_float(status.get("chance", 1.0)), battle, true))
	return out

## Deals `amount` (before the element) to the target. The line `key` gets `args` and then the HP
## taken. An immune target takes nothing, one that absorbs is healed; a weak spot, a resisted
## element, waking up and falling are logged after the hit.
static func damage(target: RpgBattleActor, amount: int, element: StringName, crit: bool, key: String, args: Array) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var rate := target.element_rate(element)
	var scaled := RpgBattleMath.apply_rate(amount, rate)
	if scaled == 0:
		out.append(_entry("text", _t("BATTLE_IMMUNE", [target.display_name]), target))
		return out
	if scaled < 0:
		var absorbed := target.restore_hp(-scaled)
		out.append(_entry("heal", _t("BATTLE_ABSORBS", [target.display_name, absorbed]), target, absorbed))
		return out
	var dealt := target.take_damage(scaled)
	var line_args := args.duplicate()
	line_args.append(dealt)
	out.append(_entry("damage", _t(key, line_args), target, dealt, crit))
	if rate > 1.0:
		out.append(_entry("text", _t("BATTLE_WEAK")))
	elif rate < 1.0:
		out.append(_entry("text", _t("BATTLE_RESISTED", [target.display_name])))
	if target.is_player_side:
		RpgUtil.emit(&"player_damaged", [dealt])
		var state := RpgUtil.state()
		if state != null and dealt > 0:
			state.wear_from_hit(target.stats)
	if target.alive and dealt > 0 and not target.wake().is_empty():
		out.append(_entry("status", _t("BATTLE_WAKES", [target.display_name]), target))
	out.append_array(fall_check(target))
	return out

## The "is defeated" line when the target has fallen (its statuses go with it).
static func fall_check(target: RpgBattleActor) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if not target.alive:
		target.statuses.clear()
		out.append(_entry("status", _t("BATTLE_DEFEATED_NAME", [target.display_name]), target))
	return out

## Restores HP (and logs it).
static func heal(target: RpgBattleActor, amount: int) -> Array[Dictionary]:
	var healed := target.restore_hp(amount)
	return [_entry("heal", _t("BATTLE_HEALED", [target.display_name, healed]), target, healed)]

## Tries to put `status` on the target with `chance`. `quiet`: say nothing when it does not take hold
## (an attack's side effect); otherwise "no effect".
static func inflict(target: RpgBattleActor, status: StringName, chance: float, battle: RpgBattleController, quiet: bool = false) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if status == &"" or not target.alive:
		return out
	if not target.is_immune(status) and RpgBattleMath.roll_chance(chance, battle.rng) and target.add_status(status):
		var e := _entry("status", RpgBattleStatus.on_text(status, target.display_name), target)
		e["status"] = status
		out.append(e)
	elif not quiet:
		out.append(_entry("text", _t("BATTLE_NO_EFFECT"), target))
	return out

## Removes the listed statuses (empty or "all" = every harmful one). One line per status removed.
static func cure(target: RpgBattleActor, cures: Array[StringName]) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var everything := cures.is_empty() or cures.has(&"all")
	for status in target.status_list():
		var listed := cures.has(status) or (everything and RpgBattleStatus.is_bad(status))
		if listed and target.remove_status(status):
			out.append(_entry("status", _t("BATTLE_CURED", [target.display_name, RpgBattleStatus.label(status)]), target))
	return out

## What one skill does to one target.
static func use_skill(user: RpgBattleActor, target: RpgBattleActor, skill: RpgSkillDefinition, battle: RpgBattleController) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if not target.alive:
		return out
	var element := skill.element
	var side := {} if skill.status == &"" else {"status": skill.status, "chance": skill.status_chance}
	match skill.kind:
		RpgSkillDefinition.Kind.PHYSICAL:
			out.append_array(strike(user, target, battle, skill.power, element if element != &"" else user.attack_element(), side))
			side = {}  # strike has tried it (unless the hit missed)
		RpgSkillDefinition.Kind.MAGIC:
			var amount := RpgBattleMath.roll_magic(skill.power, user.stat(&"magic"), target.stat(&"resistance"), battle.rng)
			out.append_array(damage(target, amount, element, false, "BATTLE_SKILL_HIT", [target.display_name]))
		RpgSkillDefinition.Kind.HEAL:
			out.append_array(heal(target, RpgBattleMath.roll_heal(skill.power, user.stat(&"magic"), battle.rng)))
	if not side.is_empty():
		out.append_array(inflict(target, skill.status, skill.status_chance, battle, skill.kind != RpgSkillDefinition.Kind.STATUS))
	if not skill.cures.is_empty():
		var cured := cure(target, skill.cures)
		out.append_array(cured)
		if cured.is_empty() and skill.kind == RpgSkillDefinition.Kind.STATUS and skill.status == &"":
			out.append(_entry("text", _t("BATTLE_NO_EFFECT"), target))
	return out

## The end of a round for one battler: poison and regen, then every status counts a round down.
static func end_of_round(actor: RpgBattleActor) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if not actor.alive:
		return out
	for status in actor.status_list():
		var tick := RpgUtil.to_float(RpgBattleStatus.field(status, "tick", 0.0))
		if tick == 0.0 or not actor.alive:
			continue
		var amount := maxi(1, floori(actor.max_hp() * absf(tick)))
		if tick < 0.0:
			var dealt := actor.take_damage(amount)
			out.append(_entry("damage", _t("BATTLE_TICK_DAMAGE", [actor.display_name, dealt, RpgBattleStatus.label(status)]), actor, dealt))
			if actor.is_player_side:
				RpgUtil.emit(&"player_damaged", [dealt])
			out.append_array(fall_check(actor))
		else:
			var healed := actor.restore_hp(amount)
			if healed > 0:
				out.append(_entry("heal", _t("BATTLE_HEALED", [actor.display_name, healed]), actor, healed))
	for status in actor.status_list():
		var left := RpgUtil.to_int(actor.statuses[status])
		if left <= 0:
			continue  # until the battle ends
		if left > 1:
			actor.statuses[status] = left - 1
			continue
		actor.remove_status(status)
		var key := "BATTLE_WAKES" if RpgUtil.to_bool(RpgBattleStatus.field(status, "wake", false)) else "BATTLE_STATUS_ENDS"
		var args: Array = [actor.display_name] if key == "BATTLE_WAKES" else [actor.display_name, RpgBattleStatus.label(status)]
		out.append(_entry("status", _t(key, args), actor))
	return out
