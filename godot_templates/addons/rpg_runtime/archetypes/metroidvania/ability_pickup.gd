class_name RpgAbilityPickup
extends RpgSideInteractable
## An ability lying in a room. Touching it (or interacting with it) grants the ability, plays
## `sfx_ability`, shows a toast with the name and how to use it, and removes the pickup for good:
## the flag `<entity_id>.collected` is saved, and a pickup whose ability the player already has
## does not come back either.

@export var ability: StringName = &""

var _taken := false

func _ready() -> void:
	body_entered.connect(_on_body_entered)
	var state := RpgUtil.state()
	if state != null and ability != &"" and state.has_ability(ability):
		queue_free()  # granted another way (the guardian, a cutscene): nothing left to pick up
		return
	var sprite := get_node_or_null("Sprite") as Sprite2D
	if sprite != null and sprite.texture == null:
		sprite.texture = RpgAbilities.glyph_texture(ability)
	if sprite != null and is_inside_tree():
		var rest := sprite.position.y
		var tween := create_tween().set_loops()
		tween.tween_property(sprite, "position:y", rest - 2.0, 0.6).set_trans(Tween.TRANS_SINE)
		tween.tween_property(sprite, "position:y", rest + 1.0, 0.6).set_trans(Tween.TRANS_SINE)

func _on_body_entered(body: Node) -> void:
	if body.is_in_group("player"):
		collect()

func _use(_actor: Node) -> void:
	collect()

## Grants the ability once. False when it was taken already or there is no saved game.
func collect() -> bool:
	if _taken or ability == &"":
		return false
	var state := RpgUtil.state()
	if state == null:
		return false
	_taken = true
	state.grant(ability)
	if entity_id != "":
		state.set_flag(entity_id, "collected", true)
	var router := RpgUtil.router()
	var audio: Node = router.audio if router != null else null
	if audio != null and audio.has_method("play"):
		audio.call("play", &"sfx_ability")
	RpgUtil.notify(RpgAbilities.toast(ability))
	queue_free()
	return true
