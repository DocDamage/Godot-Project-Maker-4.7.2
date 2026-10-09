class_name RpgLightSource
extends PointLight2D
## The light of an object tagged "light" (a torch, a lamp, a campfire; T12.62). The builder adds it
## with the radial texture it generates (res://generated/lighting/). It is off while it is outside
## the camera, and a flame flickers.

## Whether the energy wavers (torches, candles, fires; not lamps).
@export var flicker: bool = true
## The energy without flicker.
@export var base_energy: float = 1.0
## How much a flicker dims the light, 0..1.
@export var flicker_amount: float = 0.15
## How fast it wavers.
@export var flicker_speed: float = 6.0

var _notifier: VisibleOnScreenNotifier2D = null
var _time := 0.0
var _phase := 0.0

func _ready() -> void:
	energy = base_energy
	_phase = fposmod(global_position.x * 0.13 + global_position.y * 0.07, TAU)  # lights differ
	var radius := reach()
	_notifier = VisibleOnScreenNotifier2D.new()
	_notifier.name = "OnScreen"
	_notifier.rect = Rect2(-radius, -radius, radius * 2.0, radius * 2.0)
	_notifier.screen_entered.connect(set_on_screen.bind(true))
	_notifier.screen_exited.connect(set_on_screen.bind(false))
	add_child(_notifier)
	set_on_screen(_notifier.is_on_screen())

## How far the light reaches, in pixels (half the size of its scaled texture).
func reach() -> float:
	if texture == null:
		return 64.0
	return maxf(texture.get_width(), texture.get_height()) * texture_scale * 0.5

## A light outside the camera is switched off (culled) and stops flickering.
func set_on_screen(on: bool) -> void:
	enabled = on
	set_process(on and flicker)

func _process(delta: float) -> void:
	_time += delta
	energy = flicker_energy(base_energy, flicker_amount, _time * flicker_speed + _phase)

## The energy at phase `t`: a smooth, never repeating-looking waver, the same for the same t.
static func flicker_energy(base: float, amount: float, t: float) -> float:
	var wave := 0.5 + 0.5 * sin(t) * sin(t * 2.7 + 1.3)
	return base * (1.0 - clampf(amount, 0.0, 1.0) * wave)
