class_name RpgShmupStarfield
extends Node2D
## A field of stars drawn in code: the background of a stage whose packs have no picture for
## one. The same stars every time (they come from `star_seed`), `area` px large, to be repeated
## by the Parallax2D it sits in.

@export var area: Vector2 = Vector2(320, 180)
@export var count: int = 60
@export var star_seed: int = 1
@export var color: Color = Color(0.85, 0.9, 1.0)

## Where the stars are and how bright each is: [[position, brightness 0..1], ...].
func stars() -> Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = star_seed
	var out: Array = []
	for i in maxi(0, count):
		var at := Vector2(floorf(rng.randf() * area.x), floorf(rng.randf() * area.y))
		out.append([at, 0.35 + 0.65 * rng.randf()])
	return out

func _draw() -> void:
	for star: Array in stars():
		var at: Vector2 = star[0]
		var bright: float = star[1]
		draw_rect(Rect2(at, Vector2.ONE), Color(color.r, color.g, color.b, bright))
