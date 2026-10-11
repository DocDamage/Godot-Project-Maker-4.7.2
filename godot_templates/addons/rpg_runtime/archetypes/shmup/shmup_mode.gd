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

func bind_stage(next: RpgArcadeStage) -> void:
	ship = _find_ship(next)
	if ship != null and not ship.destroyed.is_connected(_on_ship_destroyed):
		ship.destroyed.connect(_on_ship_destroyed)
	super.bind_stage(next)

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
