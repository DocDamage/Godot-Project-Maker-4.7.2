class_name RpgRunAndGunHud
extends RpgArcadeHud
## The HUD of a run and gun: the arcade HUD with the weapon in hand, the grenades left and,
## for a soldier that takes more than one hit, its health.

func _process(_delta: float) -> void:
	show_soldier(_soldier())

func _soldier() -> RpgSoldier:
	var mode := RpgArcadeMode.current()
	if mode is RpgRunAndGunMode:
		var found := (mode as RpgRunAndGunMode).soldier
		return found if found != null and is_instance_valid(found) else null
	return null

## Fills the rows from `soldier` (none takes them away).
func show_soldier(soldier: RpgSoldier) -> void:
	set_row("weapon", RpgRunAndGunStrings.weapon_name(soldier.weapon()) if soldier != null and soldier.weapon() != "" else "")
	set_row("grenades", RpgRunAndGunStrings.t("RNG_GRENADES", [soldier.grenades]) if soldier != null else "")
	var forgiving := soldier != null and soldier.max_health > 1
	set_row("health", RpgRunAndGunStrings.t("RNG_HEALTH", [soldier.health]) if forgiving else "")
