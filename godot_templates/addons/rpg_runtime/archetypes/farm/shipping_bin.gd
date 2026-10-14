class_name RpgShippingBin
extends StaticBody2D
## The shipping bin of a farm (T17.08): what is put into it is sold overnight at its price, and
## the morning begins with what it earned (RpgDaySummary). Layers: world (1) + interactables (5).
##
## `interact` with it while a thing that can be sold is held puts the **whole held stack** into
## it; `interact` while a tool or nothing is held takes the stack that went in last back out, so
## a mistake can be undone until the night.
##
## A farm has one bin, wherever its picture stands: what is in it is kept in the flags of the
## game state (`farm_bin.items`, rows of `{item_id, qty}` in the order they went in), so it is
## saved with the game, the save has no new key, and the night can sell it while the farmer is
## on another map (the static functions need no node).
##
## **What was shipped this season** (T17.25) is kept beside it (`farm_bin.shipped`: the season
## it is of and, an item, how many of it the nights of that season sold): the produce contest
## of a festival is judged on it. The first sale of another season begins it anew.

## What is in the bin changed (a thing went in, came out, or the night emptied it).
signal changed

const FLAG_ENTITY := "farm_bin"
const FLAG_KEY := "items"
## `{season: "<year>:<season>", items: {item id: qty}}`: what the nights of a season sold.
const SHIPPED_KEY := "shipped"

# ------------------------------------------------------------------ what is in it (no node needed)

## The rows of the bin, `{item_id: String, qty: int}`, in the order they went in.
static func contents() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var state := RpgUtil.state()
	if state == null:
		return out
	for raw: Variant in RpgUtil.to_array(state.get_flag(FLAG_ENTITY, FLAG_KEY, [])):
		var row := RpgUtil.to_dict(raw)
		var item_id := RpgUtil.to_str(row.get("item_id", ""))
		var qty := RpgUtil.to_int(row.get("qty", 0))
		if item_id != "" and qty > 0:
			out.append({"item_id": item_id, "qty": qty})
	return out

static func _store(rows: Array[Dictionary]) -> void:
	var state := RpgUtil.state()
	if state != null:
		var plain: Array = []
		plain.assign(rows)
		state.set_flag(FLAG_ENTITY, FLAG_KEY, plain)

static func is_empty() -> bool:
	return contents().is_empty()

## How many of an item are in the bin.
static func count(item_id: StringName) -> int:
	var total := 0
	for row in contents():
		if row["item_id"] == String(item_id):
			total += RpgUtil.to_int(row["qty"])
	return total

## What one of an item earns in the bin: its `value`. 0 for a thing that is not sold (a tool, a
## key or quest item, a thing without a price, an item the game does not know).
static func price_of(item_id: StringName) -> int:
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(item_id) if state != null else null
	if def == null or def.category == RpgItemDefinition.Category.KEY or def.category == RpgItemDefinition.Category.QUEST:
		return 0
	return maxi(0, def.value)

## Moves `qty` of an item from the inventory into the bin. Returns how many went in: 0 for a
## thing that is not sold or that the farmer does not have that many of.
static func put(item_id: StringName, qty: int) -> int:
	var state := RpgUtil.state()
	if state == null or qty <= 0 or price_of(item_id) <= 0 or not state.inventory.has(item_id, qty):
		return 0
	state.inventory.remove(item_id, qty)
	var rows := contents()
	var in_bin := qty
	for i in rows.size():  # one row an item, and the one that went in last is the last row
		if rows[i]["item_id"] == String(item_id):
			in_bin += RpgUtil.to_int(rows[i]["qty"])
			rows.remove_at(i)
			break
	rows.append({"item_id": String(item_id), "qty": in_bin})
	_store(rows)
	return qty

## Takes the row that went in last back into the inventory, as much of it as the bag has room
## for. Returns `{item_id, qty}` of what came out, or {} when the bin is empty or the bag full.
static func take_back() -> Dictionary:
	var state := RpgUtil.state()
	var rows := contents()
	if state == null or rows.is_empty():
		return {}
	var last: Dictionary = rows[rows.size() - 1]
	var item_id := StringName(RpgUtil.to_str(last["item_id"]))
	var held := RpgUtil.to_int(last["qty"])
	var taken: int = state.inventory.add(item_id, held)
	if taken <= 0:
		return {}
	if taken >= held:
		rows.remove_at(rows.size() - 1)
	else:
		last["qty"] = held - taken
	_store(rows)
	return {"item_id": String(item_id), "qty": taken}

## The night: everything in the bin is sold at its price and the money is added. Returns what
## the morning's summary shows: `{rows: [{item_id, qty, each, earned}], total}`, the rows in the
## order they went in. A thing that has no price any more is given back to nobody: it stays.
static func sell_all() -> Dictionary:
	var sold: Array[Dictionary] = []
	var kept: Array[Dictionary] = []
	var total := 0
	for row in contents():
		var item_id := StringName(RpgUtil.to_str(row["item_id"]))
		var qty := RpgUtil.to_int(row["qty"])
		var each := price_of(item_id)
		if each <= 0:
			kept.append(row)
			continue
		sold.append({"item_id": String(item_id), "qty": qty, "each": each, "earned": each * qty})
		total += each * qty
	var state := RpgUtil.state()
	if state != null and not sold.is_empty():
		_store(kept)
		state.gold += total
		_record(sold)
	return {"rows": sold, "total": total}

# ------------------------------------------------------------------ what a season shipped

## The season the calendar shows, as the record names it: "<year>:<season>" ("" without a
## calendar: such a game keeps no record).
static func season_key() -> String:
	var calendar := RpgCalendar.current()
	return "%d:%d" % [calendar.year, calendar.season] if calendar != null else ""

## What the nights of the season the calendar shows have sold: item id -> how many. The night
## of a day sells what was put in on that day, so a thing counts from the morning after.
static func shipped() -> Dictionary:
	var state := RpgUtil.state()
	var out := {}
	if state == null:
		return out
	var kept := RpgUtil.to_dict(state.get_flag(FLAG_ENTITY, SHIPPED_KEY, {}))
	if season_key() == "" or RpgUtil.to_str(kept.get("season", "")) != season_key():
		return out
	var items := RpgUtil.to_dict(kept.get("items", {}))
	for id: Variant in items.keys():
		if RpgUtil.to_int(items[id]) > 0:
			out[RpgUtil.to_str(id)] = RpgUtil.to_int(items[id])
	return out

## How many things the season shipped, and the dearest of them: `{count, best, price}` (`best`
## is "" and `price` 0 when nothing was shipped; a thing is priced as the bin prices it today).
static func shipped_best() -> Dictionary:
	var count := 0
	var best := ""
	var price := 0
	var items := shipped()
	var ids: Array = items.keys()
	ids.sort()
	for id: String in ids:
		count += RpgUtil.to_int(items[id])
		var each := price_of(StringName(id))
		if each > price:
			price = each
			best = id
	return {"count": count, "best": best, "price": price}

static func _record(sold: Array[Dictionary]) -> void:
	var state := RpgUtil.state()
	var key := season_key()
	if state == null or key == "":
		return
	var items := shipped()
	for row in sold:
		var id := RpgUtil.to_str(row["item_id"])
		items[id] = RpgUtil.to_int(items.get(id, 0)) + RpgUtil.to_int(row["qty"])
	state.set_flag(FLAG_ENTITY, SHIPPED_KEY, {"season": key, "items": items})

# ------------------------------------------------------------------ the bin on the map

## `interact` (RpgInteraction calls this): the held stack goes in, or the last one comes out.
func interact(_actor: Node = null) -> void:
	var mode := RpgFarmMode.current()
	if mode == null or mode.hotbar == null:
		return
	use_with(mode.hotbar.held_item(), mode.hotbar.qty_at(mode.hotbar.held))

## What `interact` does while `item_id` is held, `held_qty` of it in the held slot. Returns how
## many went in (positive), came out (negative), or 0 when nothing happened.
func use_with(item_id: StringName, held_qty: int) -> int:
	if item_id != &"" and price_of(item_id) > 0:
		var went := put(item_id, maxi(1, held_qty))
		if went > 0:
			RpgUtil.notify(RpgFarmStrings.t("FARM_BIN_PUT", [_stack_text(item_id, went)]))
			changed.emit()
		return went
	if is_empty():
		RpgUtil.notify(RpgFarmStrings.t("FARM_BIN_EMPTY"))
		return 0
	var back := take_back()
	if back.is_empty():
		RpgUtil.notify(RpgFarmStrings.t("FARM_FULL"))
		return 0
	var qty := RpgUtil.to_int(back["qty"])
	RpgUtil.notify(RpgFarmStrings.t("FARM_BIN_TOOK", [_stack_text(StringName(RpgUtil.to_str(back["item_id"])), qty)]))
	changed.emit()
	return -qty

## "Turnip x3", or "Turnip" for one.
static func _stack_text(item_id: StringName, qty: int) -> String:
	var item_name := RpgFarmStrings.item_name(item_id)
	return item_name if qty == 1 else "%s x%d" % [item_name, qty]
