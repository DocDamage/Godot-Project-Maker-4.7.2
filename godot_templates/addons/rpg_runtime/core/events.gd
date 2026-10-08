class_name RpgEvents
extends Node
## Autoload "Events": the signal bus. Signals only, no logic.

# World
signal map_entered(map_id: StringName)
signal entity_state_changed(entity_id: String, key: String, value: Variant)
signal variable_changed(var_name: StringName, value: int)
# Interaction
signal interaction_started(target: Node)
signal interaction_finished(target: Node)
# Dialogue
signal dialogue_started(resource: Resource)
signal dialogue_finished(resource: Resource)
signal dialogue_event(name: String, arg: String)
# Sequences (cutscenes)
signal sequence_requested(sequence_id: StringName)
signal sequence_started(sequence_id: StringName)
signal sequence_finished(sequence_id: StringName)
# Items / economy
signal item_added(item_id: StringName, qty: int)
signal item_removed(item_id: StringName, qty: int)
signal gold_changed(new_total: int)
signal quest_changed(quest_id: StringName, state: String)
signal shop_requested(shop_id: StringName)
signal equipment_changed(actor_id: StringName, slot: StringName)
signal party_changed
# Actors / progression
signal player_damaged(amount: int)
signal player_healed(amount: int)
signal experience_gained(actor_id: StringName, amount: int)
signal level_up(actor_id: StringName, new_level: int)
signal entity_defeated(entity_id: String)
# Encounters
signal encounter_requested(data: Resource)
signal encounter_finished(result: Resource)
# UI
signal notify(text: String)  # toast
signal game_paused(paused: bool)
# Feedback (sound and effects listen to these; nothing in the game state depends on them)
signal chest_opened(entity_id: String)
signal door_used(entity_id: String)
signal switch_toggled(entity_id: String, on: bool)
signal gate_changed(entity_id: String, open: bool)
signal attack_started(actor: Node)
# Save
signal game_saved(slot: int)
signal game_loaded(slot: int)
