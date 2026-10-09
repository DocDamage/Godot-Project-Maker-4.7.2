class_name RpgArpgText
extends RefCounted
## Text of the action-RPG archetype. Every sentence is a translation key; the English text in
## RpgArpgStrings.KEYS is the fallback, so the text also reads correctly where the translations are
## not registered yet (tests).

static func t(key: String, args: Array = []) -> String:
	return RpgRealtimeText.t(key, args, RpgArpgStrings.KEYS)

## Display name of an item: its translated name key, else the id made readable.
static func item_name(def: RpgItemDefinition, item_id: StringName) -> String:
	return RpgRealtimeText.item_name(def, item_id)
