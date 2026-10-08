class_name RpgShopDefinition
extends Resource
## What a shop sells and buys. Files live in game/data/shops/<id>.tres; the dialogue event
## `open_shop:<id>` opens one. Buying and selling are all-or-nothing and return "" on success or the
## reason they were refused.

const SHOPS_DIR := RpgGameState.SHOPS_DIR

const OK := ""
const NOT_FOR_SALE := "not_for_sale"
const NOT_ENOUGH_GOLD := "not_enough_gold"
const NO_ROOM := "no_room"
const NOT_HELD := "not_held"
const WORTHLESS := "worthless"

@export var id: StringName
@export var title: String = "UI_SHOP"  # a tr() key
## [{item_id, price}]; a price below 0 (or none) means the item's own `value`.
@export var stock: Array[Dictionary] = []
## What the shop pays when it buys: value * sell_ratio (rounded down, at least 1).
@export var sell_ratio: float = 0.5

static func path_of(shop_id: StringName) -> String:
	return "%s/%s.tres" % [SHOPS_DIR, shop_id]

## The shop with this id, or null.
static func load_shop(shop_id: StringName) -> RpgShopDefinition:
	var path := path_of(shop_id)
	if shop_id == &"" or not ResourceLoader.exists(path):
		return null
	return load(path) as RpgShopDefinition

func sells(item_id: StringName) -> bool:
	return _entry(item_id).size() > 0

func _entry(item_id: StringName) -> Dictionary:
	for entry in stock:
		if StringName(str(entry.get("item_id", ""))) == item_id:
			return entry
	return {}

## What buying one costs: the listed price, else the item's value.
func buy_price(item_id: StringName, items: Dictionary) -> int:
	var entry := _entry(item_id)
	var listed := RpgUtil.to_int(entry.get("price", -1))
	if listed >= 0:
		return listed
	var def: RpgItemDefinition = items.get(item_id)
	return maxi(0, def.value) if def != null else 0

## What the shop pays for one (0: it will not buy it). Key and quest items are never bought.
func sell_price(item_id: StringName, items: Dictionary) -> int:
	var def: RpgItemDefinition = items.get(item_id)
	if def == null or def.category == RpgItemDefinition.Category.KEY or def.category == RpgItemDefinition.Category.QUEST:
		return 0
	if def.value <= 0:
		return 0
	return maxi(1, floori(float(def.value) * sell_ratio))

## The item ids on offer that GameState knows, in stock order.
func offered(items: Dictionary) -> Array[StringName]:
	var out: Array[StringName] = []
	for entry in stock:
		var item_id := StringName(str(entry.get("item_id", "")))
		if items.has(item_id) and not out.has(item_id):
			out.append(item_id)
	return out

func buy(game: RpgGameState, item_id: StringName, qty: int = 1) -> String:
	if qty <= 0 or not sells(item_id) or not game.items.has(item_id):
		return NOT_FOR_SALE
	var cost := buy_price(item_id, game.items) * qty
	if game.gold < cost:
		return NOT_ENOUGH_GOLD
	if game.inventory.room_for(item_id) < qty:
		return NO_ROOM
	game.inventory.add(item_id, qty)
	game.gold -= cost
	return OK

func sell(game: RpgGameState, item_id: StringName, qty: int = 1) -> String:
	if qty <= 0 or not game.inventory.has(item_id, qty):
		return NOT_HELD
	var each := sell_price(item_id, game.items)
	if each <= 0:
		return WORTHLESS
	game.inventory.remove(item_id, qty)
	game.gold += each * qty
	return OK
