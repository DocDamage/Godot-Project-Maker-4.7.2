class_name RpgShmupMode
extends RpgArcadeMode
## The combat mode of a shoot-em-up: the arcade run (RpgArcadeMode) with a ship. The game is
## seen from the top and scrolls up (`vertical`), or from the side and scrolls right
## (`horizontal`); RpgShmupMath says what follows from that for the ship, the scroller and the
## play area.

@export var orientation: String = "vertical"

## The ship of the stage that is played, or null.
var ship: RpgShmupShip = null

func _ready() -> void:
	super._ready()
	life_lost.connect(_on_life_lost)
	continued.connect(_on_continued)

func bind_stage(next: RpgArcadeStage) -> void:
	ship = _find_ship(next)
	if ship != null and not ship.destroyed.is_connected(_on_ship_destroyed):
		ship.destroyed.connect(_on_ship_destroyed)
	# before the run hears of it: the ship of the stage is still there to be asked
	next.cleared.connect(_remember_weapon)
	super.bind_stage(next)
	_give_weapon()

## The ship's weapon as the run keeps it (`spread:2`), so that the next stage, and a saved game
## that is continued, begin with it.
func _remember_weapon() -> void:
	if ship == null or not is_instance_valid(ship) or ship.weapon() == null:
		return
	weapon = "%s:%d" % [ship.weapon().kind, ship.weapon().level]

## Gives the ship of the stage that begins the weapon of the run ("" is the first weapon).
func _give_weapon() -> void:
	if weapon == "" or ship == null or ship.weapon() == null:
		return
	var parts := weapon.split(":")
	var gun := ship.weapon()
	gun.set_kind(parts[0])
	if parts.size() > 1:
		gun.level = clampi(parts[1].to_int(), 1, RpgShmupWeapon.MAX_LEVEL)

## Continue after the last life: the stage begins again with the first weapon, as after a death.
func _on_continued() -> void:
	weapon = ""

func _find_ship(inside: Node) -> RpgShmupShip:
	for node in inside.find_children("*", "CharacterBody2D", true, false):
		if node is RpgShmupShip:
			return node as RpgShmupShip
	return null

func _on_ship_destroyed() -> void:
	await player_died()

func _on_life_lost(_left: int) -> void:
	if ship != null and is_instance_valid(ship):
		ship.respawn()
