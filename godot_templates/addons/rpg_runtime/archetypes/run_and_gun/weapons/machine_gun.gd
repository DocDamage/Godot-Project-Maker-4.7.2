class_name RpgMachineGun
extends RpgGun
## The gun a soldier starts with: one bullet at a time, quickly, as far as the screen goes.

func _init() -> void:
	weapon = "machine_gun"
	rate = 8.0
	bullets_per_shot = 1
	spread_deg = 0.0
	speed_tiles = 15.0
	range_tiles = 0.0
	damage = 1
	bullet_kind = "bullet"
	pierce = false
