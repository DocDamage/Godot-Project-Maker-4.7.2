class_name RpgBattleActor
extends RefCounted
## One combatant of a battle. The player side shares the live GameState stats; enemies get a copy.
## Statuses live here and end with the battle.

var id: StringName
var display_name: String
var stats: RpgStats  # copy for enemies; the live GameState stats for the player
var is_player_side: bool = false
var defending := false
var sprite_frames: SpriteFrames
var portrait: Texture2D
var definition: Resource = null  # the RpgActorDefinition (an RpgEnemyDefinition for an enemy)
var behavior: Dictionary = {}
var inventory: RpgInventory = null  # enemy-side items (the player side uses GameState.inventory)
var chosen_item: StringName = &""  # set by the controller right before an item command runs
var chosen_skill: StringName = &""  # same, for the skill command
var statuses: Dictionary = {}  # status -> rounds left (0 = until the battle ends)
var used_rules: Dictionary = {}  # enemy AI: index of a `once` rule -> true
var alive: bool:
	get:
		return stats != null and stats.hp > 0

## A stat as combat sees it: the player side wears its equipment, enemies use their stats as they are.
## Speed counts haste and slow.
func stat(stat_name: StringName) -> int:
	var value := stat_f(stat_name)
	if stat_name == &"speed":
		value *= speed_factor()
	return roundi(value)

## The same without rounding (for shares such as `evade`).
func stat_f(stat_name: StringName) -> float:
	var state := RpgUtil.state() if is_player_side else null
	if state != null:
		return state.effective_stat(stats, stat_name)
	return stats.get_stat(stat_name)

## The most hit points this combatant can have (the player side counts its equipment).
func max_hp() -> int:
	return RpgUtil.max_hp(stats) if is_player_side else stats.max_hp

func max_mp() -> int:
	return RpgUtil.max_mp(stats) if is_player_side else stats.max_mp

## Takes up to `amount` HP (never below 0). Returns what was taken.
func take_damage(amount: int) -> int:
	var dealt := clampi(amount, 0, maxi(0, stats.hp))
	stats.hp -= dealt
	return dealt

## Gives up to `amount` HP (never above the most). Returns what was restored.
func restore_hp(amount: int) -> int:
	var healed := clampi(amount, 0, maxi(0, max_hp() - stats.hp))
	stats.hp += healed
	return healed

func restore_mp(amount: int) -> int:
	var restored := clampi(amount, 0, maxi(0, max_mp() - stats.mp))
	stats.mp += restored
	return restored

## Pays `cost` MP. An enemy without MP (max_mp 0) casts for free. False when there is not enough.
func pay_mp(cost: int) -> bool:
	if not can_pay(cost):
		return false
	if not free_casting():
		stats.mp -= maxi(0, cost)
	return true

func can_pay(cost: int) -> bool:
	return free_casting() or stats.mp >= cost

func free_casting() -> bool:
	return not is_player_side and stats.max_mp <= 0

# ---------------------------------------------------------------- traits (definition + equipment)

## The definitions of what the actor wears (the player side only).
func worn() -> Array[RpgItemDefinition]:
	var out: Array[RpgItemDefinition] = []
	var state := RpgUtil.state() if is_player_side else null
	if state == null:
		return out
	var slots: Dictionary = state.equipped_items(id)
	for slot: Variant in slots.keys():
		var item_def: RpgItemDefinition = state.items.get(slots[slot])
		if item_def != null:
			out.append(item_def)
	return out

func actor_definition() -> RpgActorDefinition:
	return definition as RpgActorDefinition

static func _rate_in(rates: Dictionary, element: StringName) -> Variant:
	if rates.has(element):
		return RpgUtil.to_float(rates[element])
	if rates.has(String(element)):
		return RpgUtil.to_float(rates[String(element)])
	return null

## How hard `element` hits this actor: the lowest rate its definition and its equipment list, 1.0
## when none does (2 weak, 0.5 resists, 0 immune, negative absorbs).
func element_rate(element: StringName) -> float:
	if element == &"":
		return 1.0
	var listed: Array[float] = []
	var def := actor_definition()
	if def != null:
		var own: Variant = _rate_in(def.element_rates, element)
		if own != null:
			listed.append(RpgUtil.to_float(own))
	for item in worn():
		var rate: Variant = _rate_in(item.element_rates, element)
		if rate != null:
			listed.append(RpgUtil.to_float(rate))
	if listed.is_empty():
		return 1.0
	var lowest: float = listed[0]
	for rate in listed:
		lowest = minf(lowest, rate)
	return lowest

func is_immune(status: StringName) -> bool:
	var def := actor_definition()
	if def != null and def.status_immune.has(status):
		return true
	for item in worn():
		if item.status_immune.has(status):
			return true
	return false

## The element of a plain attack: the weapon's, else the actor's.
func attack_element() -> StringName:
	for item in worn():
		if item.category == RpgItemDefinition.Category.WEAPON and item.element != &"":
			return item.element
	var def := actor_definition()
	return def.attack_element if def != null else &""

## {status, chance} a plain attack inflicts: the weapon's, else the actor's ({} for none).
func attack_status() -> Dictionary:
	for item in worn():
		if item.category == RpgItemDefinition.Category.WEAPON and item.attack_status != &"":
			return {"status": item.attack_status, "chance": item.attack_status_chance}
	var def := actor_definition()
	if def != null and def.attack_status != &"":
		return {"status": def.attack_status, "chance": def.attack_status_chance}
	return {}

# ---------------------------------------------------------------- statuses

func has_status(status: StringName) -> bool:
	return statuses.has(status)

## Puts the status on (or renews it). False when it cannot take hold: fallen, immune or unknown.
## Haste and slow cancel each other.
func add_status(status: StringName) -> bool:
	if not alive or not RpgBattleStatus.is_known(status) or is_immune(status):
		return false
	var opposite: StringName = {&"haste": &"slow", &"slow": &"haste"}.get(status, &"")
	if opposite != &"":
		statuses.erase(opposite)
	statuses[status] = RpgBattleStatus.rounds_of(status)
	return true

func remove_status(status: StringName) -> bool:
	return statuses.erase(status)

## The statuses in TABLE order (what the panel shows).
func status_list() -> Array[StringName]:
	var out: Array[StringName] = []
	for status in RpgBattleStatus.names():
		if statuses.has(status):
			out.append(status)
	return out

func _any(key: String) -> bool:
	for status: StringName in statuses.keys():
		if RpgUtil.to_bool(RpgBattleStatus.field(status, key, false)):
			return true
	return false

func _product(key: String) -> float:
	var out := 1.0
	for status: StringName in statuses.keys():
		out *= RpgUtil.to_float(RpgBattleStatus.field(status, key, 1.0))
	return out

## False while a status (sleep) takes the turn away.
func can_act() -> bool:
	return alive and not _any("skip")

## False while silenced.
func can_cast() -> bool:
	return not _any("mute")

func hit_factor() -> float:
	return _product("hit")

func speed_factor() -> float:
	return _product("speed")

## Ends the statuses a hit ends (sleep). Returns them.
func wake() -> Array[StringName]:
	var out: Array[StringName] = []
	for status in status_list():
		if RpgUtil.to_bool(RpgBattleStatus.field(status, "wake", false)):
			statuses.erase(status)
			out.append(status)
	return out

static func make(actor_id: StringName, actor_name: String, actor_stats: RpgStats, player_side: bool) -> RpgBattleActor:
	var a := RpgBattleActor.new()
	a.id = actor_id
	a.display_name = actor_name
	a.stats = actor_stats
	a.is_player_side = player_side
	return a
