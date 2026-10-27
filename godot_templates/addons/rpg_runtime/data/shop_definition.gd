class_name RpgShopDefinition
extends Resource
## What a shop sells and buys. Files live in game/data/shops/<id>.tres; the dialogue event
## `open_shop:<id>` opens one. Buying and selling are all-or-nothing and return "" on success or the
## reason they were refused.
##
## 1.5.0: a stock row may have a `qty` (how many the shop has until it restocks); `restock_minutes`
## and `restock_each_day` say when it restocks; `funds` is the gold it has to buy with; `wares` is
## a loot table rolled at each restock for more rows; what you sell can be bought back (`buyback`)
## for what the shop paid, until it restocks. What a shop has sold, its gold, its rolled wares and
## what can be bought back are kept in GameState.shops[id] (saved). A shop that uses none of it
## keeps no state but what can be bought back.

const SHOPS_DIR := RpgGameState.SHOPS_DIR

const OK := ""
const NOT_FOR_SALE := "not_for_sale"
const NOT_ENOUGH_GOLD := "not_enough_gold"
const NO_ROOM := "no_room"
const NOT_HELD := "not_held"
const WORTHLESS := "worthless"
## The row's `qty` (or its rolled wares) is used up until the shop restocks.
const SOLD_OUT := "sold_out"
## The shop's `funds` do not cover what it would pay.
const SHOP_CANNOT_PAY := "shop_cannot_pay"
## How many sales a shop keeps for buying back (the latest first).
const BUYBACK_MAX := 8
## Mending a piece worn down to nothing costs this share of its value (less wear, less gold).
const REPAIR_SHARE := 0.5
## Nothing to mend: the piece is not worn, or the shop does not repair.
const NOT_WORN := "not_worn"

@export var id: StringName
@export var title: String = "UI_SHOP"  # a tr() key
## [{item_id, price}]; a price below 0 (or none) means the item's own `value`.
@export var stock: Array[Dictionary] = []
## What the shop pays when it buys: value * sell_ratio (rounded down, at least 1).
@export var sell_ratio: float = 0.5
## The item categories the shop buys, by name ("CONSUMABLE", "WEAPON", "ARMOR", "ACCESSORY",
## "MATERIAL"); empty (the default, and a shop made by 1.0) buys them all. Key and quest items are
## never bought, whatever this says.
@export var buys: Array[String] = []
## Minutes of play between restocks (0: none by the clock of play).
@export var restock_minutes: int = 0
## True: the shop restocks every morning of a game with a calendar (a farm's).
@export var restock_each_day: bool = false
## The gold the shop has to buy with, back to this at each restock; what you pay it adds to it.
## -1 (the default): it never runs out.
@export var funds: int = -1
## Rolled at each restock (with GameState.rng): its items are on offer after `stock`, at their
## own value, as many as were rolled.
@export var wares: RpgLootTable = null
## True (the default): what you sell can be bought back for what the shop paid, until it restocks.
@export var buyback: bool = true
## True: the shop mends worn gear for gold (1.5.0, T18.04): what is worn and what is in the bag,
## for a share of the item's value by its wear (repair_rows, repair).
@export var repairs: bool = false

## The categories `buys` may name, in the order the dock shows them.
const CATEGORIES: Array[String] = ["CONSUMABLE", "WEAPON", "ARMOR", "ACCESSORY", "MATERIAL"]

static func path_of(shop_id: StringName) -> String:
	return "%s/%s.tres" % [SHOPS_DIR, shop_id]

## The shop with this id, or null.
static func load_shop(shop_id: StringName) -> RpgShopDefinition:
	var path := path_of(shop_id)
	if shop_id == &"" or not ResourceLoader.exists(path):
		return null
	return load(path) as RpgShopDefinition

## What is said instead of showing the wares when the shop cannot be entered now, or "" (every
## shop but one with opening hours: the farm's, RpgFarmShop, T17.08).
func closed_reason() -> String:
	return ""

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

## Whether the shop takes items of this category at all (`buys`; never key or quest items).
func buys_category(category: RpgItemDefinition.Category) -> bool:
	if category == RpgItemDefinition.Category.KEY or category == RpgItemDefinition.Category.QUEST:
		return false
	if buys.is_empty():
		return true
	var wanted: String = RpgItemDefinition.Category.find_key(category)
	for entry in buys:
		if entry.to_upper() == wanted:
			return true
	return false

## What the shop pays for one (0: it will not buy it). Key and quest items are never bought.
func sell_price(item_id: StringName, items: Dictionary) -> int:
	var def: RpgItemDefinition = items.get(item_id)
	if def == null or not buys_category(def.category):
		return 0
	if def.value <= 0:
		return 0
	return maxi(1, floori(float(def.value) * sell_ratio))

# ------------------------------------------------------------------ stock, gold, buyback (1.5.0)

## When the shop restocks: the day of the calendar (restock_each_day), else the stretch of
## `restock_minutes` of play, else 0 (it never does).
func period(game: RpgGameState) -> int:
	var calendar := RpgCalendar.current()
	if restock_each_day and calendar != null:
		return calendar.today()
	if restock_minutes > 0:
		return floori(game.playtime_s / 60.0 / float(restock_minutes))
	return 0

## The shop's state in `game` ({period, sold: {item id: n}, funds, wares: [{item_id, qty}],
## buyback: [{item_id, qty, price}]}), restocked when its period has turned: what was sold is back,
## its gold is `funds` again, the wares are rolled anew and nothing can be bought back. Made (and
## stocked) on first use.
func status(game: RpgGameState) -> Dictionary:
	var key := String(id)
	var now := period(game)
	var current: Variant = game.shops.get(key)
	if current is Dictionary and RpgUtil.to_int(RpgUtil.to_dict(current).get("period", 0)) == now:
		return current
	var rolled: Array = []
	if wares != null:
		for row in wares.roll(game.rng):
			rolled.append({"item_id": str(row["item_id"]), "qty": RpgUtil.to_int(row["qty"])})
	var fresh := {"period": now, "sold": {}, "funds": funds, "wares": rolled, "buyback": []}
	game.shops[key] = fresh
	return fresh

## How many of `item_id` the shop has left until it restocks; -1 for no end.
func left_of(game: RpgGameState, item_id: StringName) -> int:
	var entry := _entry(item_id)
	var have := -1
	if not entry.is_empty():
		if not entry.has("qty"):
			return -1
		have = maxi(0, RpgUtil.to_int(entry["qty"]))
	elif wares != null:
		have = _rolled(game, item_id)
	if have < 0:
		return -1
	var sold := RpgUtil.to_dict(status(game).get("sold", {}))
	return maxi(0, have - RpgUtil.to_int(sold.get(String(item_id), 0)))

func _rolled(game: RpgGameState, item_id: StringName) -> int:
	var total := -1
	for raw: Variant in RpgUtil.to_array(status(game).get("wares", [])):
		var row := RpgUtil.to_dict(raw)
		if StringName(str(row.get("item_id", ""))) == item_id:
			total = maxi(total, 0) + RpgUtil.to_int(row.get("qty", 0))
	return total

## True when the item is among the wares rolled for this period.
func is_ware(game: RpgGameState, item_id: StringName) -> bool:
	return wares != null and _entry(item_id).is_empty() and _rolled(game, item_id) >= 0

## The gold the shop has now; -1 when it never runs out.
func funds_of(game: RpgGameState) -> int:
	if funds < 0:
		return -1
	return RpgUtil.to_int(status(game).get("funds", funds))

## What can be bought back, the latest sale first: [{item_id, qty, price}] (price: the whole row).
func buyback_rows(game: RpgGameState) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if not buyback:
		return out
	for raw: Variant in RpgUtil.to_array(status(game).get("buyback", [])):
		out.append(RpgUtil.to_dict(raw))
	return out

## Buys back sale `index` of buyback_rows() for what the shop paid. All or nothing.
func buy_back(game: RpgGameState, index: int) -> String:
	var rows := buyback_rows(game)
	if index < 0 or index >= rows.size():
		return NOT_FOR_SALE
	var row := rows[index]
	var item_id := StringName(str(row.get("item_id", "")))
	var qty := RpgUtil.to_int(row.get("qty", 1))
	var cost := RpgUtil.to_int(row.get("price", 0))
	if game.gold < cost:
		return NOT_ENOUGH_GOLD
	if game.inventory.room_for(item_id) < qty:
		return NO_ROOM
	game.inventory.add(item_id, qty)
	game.gold -= cost
	var st := status(game)
	var kept: Array = RpgUtil.to_array(st["buyback"])
	kept.remove_at(index)
	st["buyback"] = kept
	_take_gold(game, -cost)
	return OK

## The shop's purse after it paid `amount` (a negative amount: it was paid).
func _take_gold(game: RpgGameState, amount: int) -> void:
	if funds < 0:
		return
	var st := status(game)
	st["funds"] = RpgUtil.to_int(st.get("funds", funds)) - amount

## The item ids on offer now: offered(), then the wares rolled for this period.
func offered_now(game: RpgGameState) -> Array[StringName]:
	var out := offered(game.items)
	if wares == null:
		return out
	for raw: Variant in RpgUtil.to_array(status(game).get("wares", [])):
		var item_id := StringName(str(RpgUtil.to_dict(raw).get("item_id", "")))
		if game.items.has(item_id) and not out.has(item_id):
			out.append(item_id)
	return out

## The item ids on offer that GameState knows, in stock order.
func offered(items: Dictionary) -> Array[StringName]:
	var out: Array[StringName] = []
	for entry in stock:
		var item_id := StringName(str(entry.get("item_id", "")))
		if items.has(item_id) and not out.has(item_id):
			out.append(item_id)
	return out

func buy(game: RpgGameState, item_id: StringName, qty: int = 1) -> String:
	if qty <= 0 or not (sells(item_id) or is_ware(game, item_id)) or not game.items.has(item_id):
		return NOT_FOR_SALE
	var left := left_of(game, item_id)
	if left >= 0 and left < qty:
		return SOLD_OUT
	var cost := buy_price(item_id, game.items) * qty
	if game.gold < cost:
		return NOT_ENOUGH_GOLD
	if game.inventory.room_for(item_id) < qty:
		return NO_ROOM
	game.inventory.add(item_id, qty)
	game.gold -= cost
	if left >= 0:
		var sold := RpgUtil.to_dict(status(game)["sold"])
		sold[String(item_id)] = RpgUtil.to_int(sold.get(String(item_id), 0)) + qty
		status(game)["sold"] = sold
	_take_gold(game, -cost)
	return OK

## {item id: how many} of everything in the bag that the shop buys: what Sell all sells. What
## someone wears is not in the bag, so equipped gear stays.
func sell_all_items(game: RpgGameState) -> Dictionary:
	var out: Dictionary = {}
	for slot in game.inventory.slots:
		var item_id: StringName = slot["item_id"]
		if not out.has(item_id) and sell_price(item_id, game.items) > 0:
			out[item_id] = game.inventory.count(item_id)
	return out

## The gold Sell all would pay (no more than the shop has).
func sell_all_value(game: RpgGameState) -> int:
	var total := 0
	var held := sell_all_items(game)
	for item_id: StringName in held:
		total += sell_price(item_id, game.items) * RpgUtil.to_int(held[item_id])
	var purse := funds_of(game)
	return mini(total, purse) if purse >= 0 else total

## Sells everything sell_all_items() lists (what the shop can pay for). Returns the gold paid.
func sell_all(game: RpgGameState) -> int:
	var before := game.gold
	var held := sell_all_items(game)
	for item_id: StringName in held:
		sell(game, item_id, RpgUtil.to_int(held[item_id]))
	return game.gold - before

func sell(game: RpgGameState, item_id: StringName, qty: int = 1) -> String:
	if qty <= 0 or not game.inventory.has(item_id, qty):
		return NOT_HELD
	var each := sell_price(item_id, game.items)
	if each <= 0:
		return WORTHLESS
	var paid := each * qty
	var purse := funds_of(game)
	if purse >= 0 and purse < paid:
		return SHOP_CANNOT_PAY
	game.inventory.remove(item_id, qty)
	game.gold += paid
	if buyback:
		var st := status(game)
		var kept: Array = RpgUtil.to_array(st["buyback"])
		kept.push_front({"item_id": String(item_id), "qty": qty, "price": paid})
		st["buyback"] = kept.slice(0, BUYBACK_MAX)
	_take_gold(game, paid)
	return OK

# ------------------------------------------------------------------ repair (1.5.0, T18.04)

## What mending `wear` of an item of `durability` costs: REPAIR_SHARE of its value by the share
## worn, at least 1 (0 for a piece that is not worn).
static func repair_cost(def: RpgItemDefinition, wear: int) -> int:
	if def == null or def.durability <= 0 or wear <= 0:
		return 0
	return maxi(1, ceili(float(maxi(0, def.value)) * REPAIR_SHARE * float(mini(wear, def.durability)) / float(def.durability)))

## What the shop can mend now, the worn pieces first: [{item_id, wear, durability, price}] with
## {actor_id, slot} for a piece someone wears, {bag_index} for one in the bag. Empty when the
## shop does not repair.
func repair_rows(game: RpgGameState) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if not repairs:
		return out
	var actors: Array = game.equipment.keys()
	actors.sort()
	for actor_key: Variant in actors:
		var worn := RpgUtil.to_dict(game.equipment[actor_key])
		var slots: Array = worn.keys()
		slots.sort()
		for slot_key: Variant in slots:
			var wear := game.wear_of(StringName(str(actor_key)), StringName(str(slot_key)))
			var def: RpgItemDefinition = game.items.get(StringName(str(worn[slot_key])))
			if wear[1] > 0 and wear[0] > 0:
				out.append({"item_id": str(worn[slot_key]), "wear": wear[0], "durability": wear[1], "price": repair_cost(def, wear[0]), "actor_id": str(actor_key), "slot": str(slot_key)})
	for i in game.inventory.slots.size():
		var item_id := StringName(str(game.inventory.slots[i]["item_id"]))
		var def: RpgItemDefinition = game.items.get(item_id)
		var wear := RpgUtil.to_int(game.inventory.data_at(i).get("wear", 0))
		if def != null and def.durability > 0 and wear > 0:
			out.append({"item_id": String(item_id), "wear": wear, "durability": def.durability, "price": repair_cost(def, wear), "bag_index": i})
	return out

## Mends row `index` of repair_rows() for its price. All or nothing.
func repair(game: RpgGameState, index: int) -> String:
	var rows := repair_rows(game)
	if index < 0 or index >= rows.size():
		return NOT_WORN
	var row := rows[index]
	var cost := RpgUtil.to_int(row["price"])
	if game.gold < cost:
		return NOT_ENOUGH_GOLD
	if row.has("bag_index"):
		game.inventory.mend_at(RpgUtil.to_int(row["bag_index"]))
	else:
		game.mend(StringName(str(row["actor_id"])), StringName(str(row["slot"])))
	game.gold -= cost
	_take_gold(game, -cost)
	return OK

# ------------------------------------------------------------------ the dock (1.5.0)

## What is wrong with stock row `index`, as the validator says it (VAL-034), or "": an item that
## `known` (item ids, e.g. the files of game/data/items) does not have.
func row_problem(index: int, known: Array) -> String:
	if index < 0 or index >= stock.size():
		return ""
	var item_id := str(stock[index].get("item_id", ""))
	if item_id == "":
		return "row %d sells no item" % (index + 1)
	if not known.has(item_id) and not known.has(StringName(item_id)):
		return "row %d sells '%s', which has no file in %s" % [index + 1, item_id, RpgGameState.ITEMS_DIR]
	return ""

## The problems of every stock row (see row_problem).
func stock_problems(known: Array) -> Array[String]:
	var out: Array[String] = []
	for i in stock.size():
		var problem := row_problem(i, known)
		if problem != "":
			out.append(problem)
	return out

## The shop as plain data, and back (the dock's JSON export and import). `wares` is written as
## its entries.
func to_dict() -> Dictionary:
	var out := {"id": String(id), "title": title, "stock": stock.duplicate(true), "sell_ratio": sell_ratio, "buys": Array(buys), "restock_minutes": restock_minutes, "restock_each_day": restock_each_day, "funds": funds, "buyback": buyback, "repairs": repairs}
	if wares != null:
		out["wares"] = {"entries": wares.entries.duplicate(true)}
	return out

## Sets what `data` names (keys it lacks keep their values); a subclass reads its own keys too.
func apply_dict(data: Dictionary) -> void:
	id = StringName(str(data.get("id", id)))
	title = str(data.get("title", title))
	if data.get("stock") is Array:
		stock.clear()
		for raw: Variant in RpgUtil.to_array(data["stock"]):
			if raw is Dictionary:
				stock.append(RpgUtil.to_dict(raw).duplicate(true))
	sell_ratio = RpgUtil.to_float(data.get("sell_ratio", sell_ratio))
	if data.get("buys") is Array:
		buys.clear()
		for word: Variant in RpgUtil.to_array(data["buys"]):
			buys.append(str(word))
	restock_minutes = RpgUtil.to_int(data.get("restock_minutes", restock_minutes))
	restock_each_day = RpgUtil.to_bool(data.get("restock_each_day", restock_each_day), restock_each_day)
	funds = RpgUtil.to_int(data.get("funds", funds))
	buyback = RpgUtil.to_bool(data.get("buyback", buyback), buyback)
	repairs = RpgUtil.to_bool(data.get("repairs", repairs), repairs)
	if data.has("wares"):
		var table: Variant = data["wares"]
		wares = null
		if table is Dictionary and RpgUtil.to_dict(table).get("entries") is Array:
			wares = RpgLootTable.new()
			for raw: Variant in RpgUtil.to_array(RpgUtil.to_dict(table)["entries"]):
				if raw is Dictionary:
					wares.entries.append(RpgUtil.to_dict(raw).duplicate(true))

static func from_dict(data: Dictionary) -> RpgShopDefinition:
	var made := RpgShopDefinition.new()
	made.apply_dict(data)
	return made
