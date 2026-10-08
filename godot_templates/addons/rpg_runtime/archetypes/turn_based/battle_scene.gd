class_name RpgBattleScene
extends Node2D
## The battle scene: puts the battlers on their slots, plays the hit feedback and hands the
## result back to the overworld. Built by builder/recipes/turn_based/battle_scene_recipe.gd.
##
##   %Controller (RpgBattleController), %UI (RpgBattleUi), %EnemySlots / %PartySlots (Marker2D slots)

const SMALL_FRAME_PX := 32
const SMALL_FRAME_SCALE := 2.0
const FLASH_SECONDS := 0.05
const NUMBER_RISE_PX := 18.0
const PLACEHOLDER_SIZE := Vector2(24, 32)

## Catalog asset id of the battle music (the recipe picks the first music asset called "battle").
@export var music_asset_id: String = ""

var controller: RpgBattleController = null
var ui: RpgBattleUi = null
var started := false

var _visuals: Dictionary = {}  # actor -> Node2D
var _sizes: Dictionary = {}  # actor -> Vector2, the size on screen

func _ready() -> void:
	controller = get_node_or_null("%Controller") as RpgBattleController
	ui = get_node_or_null("%UI") as RpgBattleUi
	_start_from_state.call_deferred()

## SceneRouter.push_scene hands the encounter over here.
func setup(payload: Resource) -> void:
	_begin(payload as RpgEncounterData)

## Running the scene on its own (F6) with a pending encounter in GameState.
func _start_from_state() -> void:
	if started:
		return
	var state := RpgUtil.state()
	if state != null:
		var pending: RpgEncounterData = state.get("pending_encounter")
		_begin(pending)

func _begin(data: RpgEncounterData) -> void:
	if started or data == null or controller == null or ui == null:
		return
	started = true
	controller.setup(data)
	var router := RpgUtil.router()
	var combat: Object = null
	if router != null:
		combat = router.get("combat")
	if combat != null:
		var chooser: Variant = combat.get("auto_choose")
		if chooser is Callable:
			var auto: Callable = chooser
			if auto.is_valid():
				controller.auto_choose = auto
	_build_visuals()
	ui.bind(controller, _anchor_of)
	controller.ui = ui
	controller.entries_resolved.connect(_on_entries_resolved)
	_run()

func _run() -> void:
	var audio := _audio()
	var previous_music: String = str(audio.get("current_music_id")) if audio != null else ""
	if audio != null and music_asset_id != "":
		audio.call("play_music", music_asset_id)
	if not controller.auto_choose.is_valid() and not controller.enemies.is_empty():
		await ui.show_message(RpgBattleText.t("BATTLE_APPEARS", [controller.enemies[0].display_name]))
	var result: RpgEncounterResult = await controller.run()
	await _leave(result, previous_music)

func _audio() -> Node:
	var router := RpgUtil.router()
	if router == null:
		return null
	var audio: Node = router.get("audio")
	return audio

func _leave(result: RpgEncounterResult, previous_music: String) -> void:
	var router := RpgUtil.router()
	if router == null or RpgUtil.to_int(router.call("stack_depth")) == 0:
		return  # running on its own: there is nowhere to go back to
	while router.is_busy():  # the fade-in of this scene may still be running
		await get_tree().process_frame
	var audio := _audio()
	if audio != null and music_asset_id != "":
		audio.call("play_music", previous_music if previous_music != "" else null)
	router.call("pop_scene", result)

# ---------------------------------------------------------------- visuals

func _slots(group: String) -> Array[Node2D]:
	var out: Array[Node2D] = []
	var holder := get_node_or_null("%" + group)
	if holder != null:
		for child in holder.get_children():
			if child is Node2D:
				out.append(child)
	return out

func _build_visuals() -> void:
	_place_group(controller.enemies, _slots("EnemySlots"), false)
	_place_group(controller.party, _slots("PartySlots"), true)

func _place_group(actors: Array[RpgBattleActor], slots: Array[Node2D], player_side: bool) -> void:
	for i in actors.size():
		var actor := actors[i]
		var spot := slots[mini(i, slots.size() - 1)].position if not slots.is_empty() else Vector2(80 + 60 * i, 100)
		var node := _make_visual(actor, player_side)
		node.position = spot
		node.name = "Battler_" + String(actor.id)
		add_child(node)
		_visuals[actor] = node

func _pick_animation(frames: SpriteFrames, player_side: bool) -> String:
	var names := Array(frames.get_animation_names())
	names.sort()
	var wanted: Array[String] = ["idle_down"]
	if player_side:
		wanted = ["idle_up", "idle_left"]
	for w in wanted:
		if names.has(w):
			return w
	return RpgUtil.to_str(names[0]) if not names.is_empty() else ""

func _make_visual(actor: RpgBattleActor, player_side: bool) -> Node2D:
	var frames := actor.sprite_frames
	if frames != null:
		var anim := _pick_animation(frames, player_side)
		if anim != "" and frames.get_frame_count(anim) > 0:
			var sprite := AnimatedSprite2D.new()
			sprite.sprite_frames = frames
			sprite.animation = anim
			var frame_size := frames.get_frame_texture(anim, 0).get_size()
			if maxf(frame_size.x, frame_size.y) <= SMALL_FRAME_PX:
				sprite.scale = Vector2.ONE * SMALL_FRAME_SCALE
			_sizes[actor] = frame_size * sprite.scale
			sprite.play(anim)
			return sprite
	# No art: a plain coloured shape keeps the battle playable.
	var shape := Polygon2D.new()
	var half := PLACEHOLDER_SIZE / 2.0
	shape.polygon = PackedVector2Array([-half, Vector2(half.x, -half.y), half, Vector2(-half.x, half.y)])
	shape.color = Color("#4f7fd9") if player_side else Color("#d9534f")
	_sizes[actor] = PLACEHOLDER_SIZE
	return shape

## Where the target arrow should touch `actor`: just above its sprite.
func _anchor_of(actor: RpgBattleActor) -> Vector2:
	var node: Node2D = _visuals.get(actor)
	if node == null:
		return Vector2.ZERO
	var size: Vector2 = _sizes.get(actor, PLACEHOLDER_SIZE)
	return node.global_position + Vector2(0, -size.y / 2.0 - 4.0)

func visual_of(actor: RpgBattleActor) -> Node2D:
	var node: Node2D = _visuals.get(actor)
	return node

# ---------------------------------------------------------------- hit feedback

func _on_entries_resolved(entries: Array) -> void:
	for entry: Dictionary in entries:
		var target: RpgBattleActor = entry.get("target")
		var node: Node2D = _visuals.get(target)
		if target == null or node == null:
			continue
		match str(entry.get("type", "")):
			"damage":
				RpgUtil.emit(&"attack_started", [node])
				_hit(node, target, RpgUtil.to_bool(entry.get("crit", false)))
				_float_number(node, target, str(RpgUtil.to_int(entry.get("amount", 0))), Color.WHITE)
			"heal":
				_float_number(node, target, "+%d" % RpgUtil.to_int(entry.get("amount", 0)), Color(0.5, 1.0, 0.5))
			"miss":
				_float_number(node, target, RpgBattleText.t("BATTLE_MISS_POPUP"), Color(0.8, 0.8, 0.8))
			"status":
				if entry.has("status"):
					_float_number(node, target, RpgBattleStatus.label(StringName(str(entry["status"]))), Color(0.85, 0.6, 1.0))
	ui.refresh()

## A 0.1 s white flash, a short shake on a crit and a fade when the battler falls.
func _hit(node: Node2D, target: RpgBattleActor, crit: bool) -> void:
	var tween := create_tween()
	tween.tween_property(node, "modulate", Color(3, 3, 3, 1), FLASH_SECONDS)
	tween.tween_property(node, "modulate", Color(1, 1, 1, 1), FLASH_SECONDS)
	if not target.alive:
		tween.tween_property(node, "modulate:a", 0.0 if not target.is_player_side else 0.35, 0.3)
	if crit:
		var base := node.position.x
		var shake := create_tween()
		for dx: float in [3.0, -3.0, 2.0, -2.0, 0.0]:
			shake.tween_property(node, "position:x", base + dx, 0.03)

func _float_number(node: Node2D, target: RpgBattleActor, text: String, color: Color) -> void:
	var label := Label.new()
	label.text = text
	label.modulate = color
	label.z_index = 20
	label.add_theme_color_override("font_outline_color", Color.BLACK)
	label.add_theme_constant_override("outline_size", 3)
	add_child(label)
	var size: Vector2 = _sizes.get(target, PLACEHOLDER_SIZE)
	var half_height := size.y / 2.0
	label.position = node.position + Vector2(-8, -half_height - 10)
	var tween := create_tween().set_parallel(true)
	tween.tween_property(label, "position:y", label.position.y - NUMBER_RISE_PX, 0.6)
	tween.tween_property(label, "modulate:a", 0.0, 0.6)
	tween.chain().tween_callback(label.queue_free)
