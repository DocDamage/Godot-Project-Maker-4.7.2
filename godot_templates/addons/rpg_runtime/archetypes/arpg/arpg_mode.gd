class_name RpgArpgMode
extends RpgCombatMode
## The action-RPG archetype's combat mode, SceneRouter.combat. Combat happens on the map itself, so
## there are no encounters: is_in_combat() is always false. What the mode owns is what the shared
## code needs from an archetype: the defeat policy, the quick item (HUD and inventory menu) and the
## "Set quick item" button of the inventory menu.

const FLAG_ENTITY := "arpg_hud"
const FLAG_KEY := "quick_item"

signal quick_item_changed(item_id: StringName)
## A follower was hurt, went down or got up (the HUD's member bars).
signal party_health_changed

func is_in_combat() -> bool:
	return false

func start_encounter(_data: RpgEncounterData) -> void:
	push_warning("[RPG-COMBAT] the action RPG has no encounters; enemies fight on the map")

# ---------------------------------------------------------------- defeat

## The save slot written last, or 0 when there is none.
static func latest_save_slot() -> int:
	return RpgDefeatPolicy.latest_save_slot()

## The defeat policy is shared with the turn-based archetype (RpgDefeatPolicy): the game-over
## screen, or at once the newest save / the start of the map in smoke tests.
func apply_defeat() -> void:
	await RpgDefeatPolicy.show_game_over()

# ---------------------------------------------------------------- followers (T13.15)

## Called by RpgFollowers for every follower it makes: the first RpgAssist.MAX_ASSISTS of them help
## in a fight. `member` is the party entry {actor_id, stats}.
func customize_follower(node: Node2D, member: Dictionary, index: int) -> void:
	if index >= RpgAssist.MAX_ASSISTS or node.get_node_or_null(RpgAssist.NODE_NAME) != null:
		return
	var router := RpgUtil.router()
	var tile := float(RpgUtil.map_tile_px(router.current_map)) if router != null and router.current_map != null else 16.0
	var member_stats: RpgStats = member.get("stats")
	var assist := RpgAssist.attach(node, member_stats, tile)
	assist.health.changed.connect(_on_member_health)
	assist.downed.connect(party_health_changed.emit)
	assist.recovered.connect(party_health_changed.emit)

func _on_member_health(_hp: int, _max_hp: int) -> void:
	party_health_changed.emit()

# ---------------------------------------------------------------- quick item

## The first consumable in the inventory that has a use effect, or &"".
func default_quick_item() -> StringName:
	var state := RpgUtil.state()
	if state == null:
		return &""
	for slot in state.inventory.slots:
		var def: RpgItemDefinition = state.items.get(slot["item_id"])
		if def != null and def.category == RpgItemDefinition.Category.CONSUMABLE and def.use_effect != &"":
			return slot["item_id"]
	return &""

## The selected quick item while the player still has some, else the default one.
func quick_item() -> StringName:
	var state := RpgUtil.state()
	if state == null:
		return &""
	var chosen := StringName(str(state.get_flag(FLAG_ENTITY, FLAG_KEY, "")))
	if chosen != &"" and state.inventory.count(chosen) > 0:
		return chosen
	return default_quick_item()

## Selects the quick item. False when the item is unknown.
func set_quick_item(item_id: StringName) -> bool:
	var state := RpgUtil.state()
	if state == null or not state.items.has(item_id):
		return false
	state.set_flag(FLAG_ENTITY, FLAG_KEY, String(item_id))
	quick_item_changed.emit(item_id)
	return true

## Uses one of the quick item on the player. False (with a toast) when nothing happened.
func use_quick_item() -> bool:
	var state := RpgUtil.state()
	if state == null:
		return false
	var id := quick_item()
	if id == &"":
		RpgUtil.notify(RpgArpgText.t("ARPG_QUICK_EMPTY"))
		return false
	if not state.inventory.use(id, state.player_stats):
		RpgUtil.notify(RpgArpgText.t("ARPG_QUICK_FAILED"))
		return false
	return true

# ---------------------------------------------------------------- inventory menu

## Called by the inventory menu when it opens: adds the "Set quick item" button.
func customize_inventory_menu(menu: Control) -> void:
	if not menu.has_method("add_extra_button"):
		return
	var button := Button.new()
	button.name = "SetQuick"
	button.text = RpgArpgText.t("ARPG_SET_QUICK")
	button.pressed.connect(_on_set_quick_pressed.bind(menu))
	menu.call("add_extra_button", button)

func _on_set_quick_pressed(menu: Control) -> void:
	var id: StringName = menu.call("selected_item")
	var state := RpgUtil.state()
	if id == &"" or state == null or not set_quick_item(id):
		RpgUtil.notify(RpgArpgText.t("ARPG_QUICK_NONE"))
		return
	var def: RpgItemDefinition = state.items.get(id)
	RpgUtil.notify(RpgArpgText.t("ARPG_QUICK_SET", [RpgArpgText.item_name(def, id)]))
