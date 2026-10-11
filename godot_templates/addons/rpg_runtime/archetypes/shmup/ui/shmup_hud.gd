class_name RpgShmupHud
extends RpgArcadeHud
## The HUD of a shoot-em-up: the arcade HUD with two rows of its own, the bombs left and the
## weapon with its level.

func _process(_delta: float) -> void:
	show_ship(_ship())

func _ship() -> RpgShmupShip:
	var mode := RpgArcadeMode.current()
	if mode is RpgShmupMode:
		var found := (mode as RpgShmupMode).ship
		return found if found != null and is_instance_valid(found) else null
	return null

## Fills the rows from `ship` (none takes them away).
func show_ship(ship: RpgShmupShip) -> void:
	var blast := ship.bomb() if ship != null else null
	var gun := ship.weapon() if ship != null else null
	set_row("bombs", RpgShmupStrings.t("SHM_BOMBS", [blast.count]) if blast != null else "")
	set_row("weapon", RpgShmupStrings.t("SHM_WEAPON", [RpgShmupStrings.weapon_name(gun.kind), gun.level]) if gun != null else "")
