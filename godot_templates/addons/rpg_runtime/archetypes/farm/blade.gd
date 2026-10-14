class_name RpgFarmBlade
extends RpgHitbox
## The farmer's weapon as a hitbox (T17.24): the hitbox of the real-time combat set
## (combat/realtime/hitbox.gd: player hitbox layer 7, it looks for the enemy hurtboxes on 10),
## switched on for one swing by `swing`. The weapon is held, not worn, so what it adds to the
## attack is `bonus` (the `attack` modifiers of the item swung), added to the damage of the
## farmer's own stats. RpgFarmFight makes it, a child of the farmer called `Blade`.

## How long a swing can hit.
const SWING_S := 0.22

## What the weapon swung adds to the damage.
var bonus := 0

var _left := 0.0

## The `add` of the `attack` modifiers of an item: what it adds when it is swung.
static func bonus_of(def: RpgItemDefinition) -> int:
	var out := 0.0
	if def == null:
		return 0
	for raw: Variant in def.modifiers:
		var mod := RpgUtil.to_dict(raw)
		if RpgUtil.to_str(mod.get("stat", "")) == "attack":
			out += RpgUtil.to_float(mod.get("add", 0.0))
	return roundi(out)

## One swing towards `facing`: the area is aimed and can hit for SWING_S (each hurtbox once).
## `toward` (a direction on the screen, T17.14) aims it at the cell the farmer faces on diamonds,
## which the four names of a facing do not point at; ZERO aims it by the facing.
func swing(facing: String, with_bonus: int, toward: Vector2 = Vector2.ZERO) -> void:
	bonus = with_bonus
	aim(facing)
	if toward != Vector2.ZERO:
		var way := toward.normalized()
		position = center + Vector2(way.x * reach.x, way.y * reach.y)
	active = false
	active = true
	_left = SWING_S

func _physics_process(delta: float) -> void:
	super._physics_process(delta)
	if _left <= 0.0:
		return
	_left -= delta
	if _left <= 0.0:
		active = false

func build_info(hurtbox: RpgHurtbox) -> RpgDamageInfo:
	var info := super.build_info(hurtbox)
	info.amount += maxi(0, bonus)
	return info
