class_name RpgPlayerController
extends CharacterBody2D
## M1 player: 4/8-direction movement from the move_* input actions and facing-based animation.
## M6 replaces this with the component actor (T6.05).

@export var speed: float = 80.0
@export var visual_path: NodePath = ^"Visual"
var facing: String = "down"
var _driver: RpgAnimationDriver = RpgAnimationDriver.new()

func _ready() -> void:
	_driver.sprite = get_node_or_null(visual_path) as AnimatedSprite2D
	if _driver.sprite == null:
		push_error("[RPG-PLAYER] visual_path does not point to an AnimatedSprite2D")

func _physics_process(_delta: float) -> void:
	var dir := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	velocity = dir * speed
	move_and_slide()
	if dir != Vector2.ZERO:
		facing = RpgAnimationDriver.dir_to_facing(dir)
		_driver.play("walk", facing)
	else:
		_driver.play("idle", facing)
