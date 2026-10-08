class_name RpgBattleStatus
extends RefCounted
## The statuses of the turn-based battle. They live on the RpgBattleActor (status -> rounds left)
## and end with the battle. `rounds` 0 = until the battle ends. Fields of TABLE:
##   rounds  how long it lasts       tick   share of max HP at the end of each round (- = damage)
##   skip    the actor loses turns    wake   a hit ends it      mute   no skills
##   hit     hit chance factor        speed  speed factor       bad    a cure removes it
##   on      the log line when it takes hold (BattleText key, %s = the name)

const TABLE := {
	&"poison": {"rounds": 0, "tick": -0.125, "bad": true, "on": "BATTLE_POISONED"},
	&"regen": {"rounds": 4, "tick": 0.1, "bad": false, "on": "BATTLE_REGEN_ON"},
	&"sleep": {"rounds": 3, "skip": true, "wake": true, "bad": true, "on": "BATTLE_ASLEEP_ON"},
	&"silence": {"rounds": 3, "mute": true, "bad": true, "on": "BATTLE_SILENCED"},
	&"blind": {"rounds": 3, "hit": 0.5, "bad": true, "on": "BATTLE_BLINDED"},
	&"haste": {"rounds": 4, "speed": 1.5, "bad": false, "on": "BATTLE_HASTED"},
	&"slow": {"rounds": 4, "speed": 0.5, "bad": true, "on": "BATTLE_SLOWED"},
}

static func is_known(status: StringName) -> bool:
	return TABLE.has(status)

static func names() -> Array[StringName]:
	var out: Array[StringName] = []
	for status: StringName in TABLE.keys():
		out.append(status)
	return out

static func field(status: StringName, key: String, default: Variant = null) -> Variant:
	var entry: Dictionary = TABLE.get(status, {})
	return entry.get(key, default)

static func rounds_of(status: StringName) -> int:
	return RpgUtil.to_int(field(status, "rounds", 3))

static func is_bad(status: StringName) -> bool:
	return RpgUtil.to_bool(field(status, "bad", true))

## The short shown name: BATTLE_STATUS_<NAME> ("Poison").
static func label(status: StringName) -> String:
	return RpgBattleText.t("BATTLE_STATUS_" + String(status).to_upper())

## The log line when the status takes hold of `who`.
static func on_text(status: StringName, who: String) -> String:
	return RpgBattleText.t(str(field(status, "on", "")), [who])
