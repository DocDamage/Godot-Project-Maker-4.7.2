class_name RpgRealtimeText
extends RefCounted
## Text of the real-time combat set. A sentence is a translation key with an English fallback, so it
## also reads correctly where the translations are not registered yet (tests). The keys keep their
## 1.0 names (ARPG_...), so a project's translations stay valid.

const KEYS := {
	"ARPG_ITEM_GAINED": "Picked up %s x%d",
}

## The translation of `key`, else its text in `fallback`, with `args` filled in.
static func t(key: String, args: Array = [], fallback: Dictionary = KEYS) -> String:
	var text := TranslationServer.translate(key)
	if text == key and fallback.has(key):
		text = fallback[key]
	if args.is_empty() or not text.contains("%"):
		return text
	return text % args

## Display name of an item: its translated name key, else the id made readable.
static func item_name(def: RpgItemDefinition, item_id: StringName) -> String:
	if def != null and def.display_name != "":
		var text := TranslationServer.translate(def.display_name)
		if text != def.display_name:
			return text
		if not def.display_name.to_upper() == def.display_name:
			return def.display_name
	return String(item_id).capitalize()
