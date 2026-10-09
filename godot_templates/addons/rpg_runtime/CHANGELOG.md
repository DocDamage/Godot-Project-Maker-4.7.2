# Changelog

## 1.1.0

**Compatibility with 1.0.** The save version stays 1 and a 1.0 save loads. Every new key is
optional: a quest stage's `next`, `title` and `rewards`, the `sfx_step_<surface>` and custom
sound slots, `rpggen/surfaces.json`, `rpggen/audio_loops.json` and `rpggen/world_plan.json` (a
project without the file behaves as in 1.0). No script moved or was renamed. A scene made by 1.0
keeps working as it is: a shop scene without the Sell all button, a HUD scene without the
members' bars (they are added at run time), a starter map whose houses share one interior, and a
project with `field_1`. One behaviour changes: **music loops** (in 1.0 a track played once).

* Dialogue: `RpgDialogueRunner.event_refs(event)` and an optional `ids` argument of
  `event_problem` (unknown shop, quest and actor ids). New event `play_sound:<slot>`.
* Followers in the action RPG: `RpgFollowers` asks the combat mode to `customize_follower(node,
  member, index)` and leaves a follower whose meta `held` is true where it is (its place on the
  trail goes to meta `home`). `RpgAssist` (`archetypes/arpg/components/assist.gd`): the first two
  followers walk to an enemy within 3 tiles of the player and swing every 1.2 s with the
  member's attack, stay within 6 tiles, and are down for 5 s at 0 HP. `RpgArpgMode`
  signal `party_health_changed`; the HUD shows a bar per member.
* Sound: any slot named `music_<name>` or `sfx_<name>`; `RpgSoundBank.surface_of`,
  `has_step_surfaces`, `step_slot`; `RpgMovement.surface_at` (a tile's `footstep` custom data,
  else its asset's `surface:<name>` tag). Loop points: `RpgAudio.apply_loop(stream, {start_ms,
  end_ms})`, `loop_of(path)`; `play_music` applies the loop of `rpggen/audio_loops.json` (a WAV
  loops between both points; Ogg Vorbis and MP3 return to the start point from their end).
* Quests: `RpgQuestDefinition.next_of`, `edges`, `problems`, `reached(state)`, `to_dict`,
  `from_dict`; a stage may name its `next` stage (or `done`) and have `rewards`, given when its
  condition finishes it.
* Sequences: `RpgSequence.STEP_KINDS`, `step_kind`, `new_step`, `entity_problems`;
  `RpgSequenceRunner.sequence_from(commands)`, and while the editor's debugger is attached the
  message `rpg_sequence:run` plays the commands the dock's Cutscenes tab sends.
* World map: with `rpggen/world_plan.json` the first entry is **World** (`RpgWorldMapMenu.
  overview`: a box per area where the plan put it, lit when visited, a mark per door pair); an
  area is listed by its name. New text key `UI_WORLD_OVERVIEW`.
* Enemy definitions of recolour variants (the builder's enemy recipes): the variant's name and
  its source's stats times the variant's multipliers.
* Shops: `RpgShopMenu` rows have a quantity (`max_quantity`, `quantity_of`, `set_quantity`,
  `change_quantity`; `transact(item, qty)`), and a **Sell all** button (`sell_all()`).
  `RpgShopDefinition.buys` (categories, empty = all), `buys_category`, `sell_all_items`,
  `sell_all_value`, `sell_all`. New text keys: `UI_SHOP_QUANTITY_HINT`, `UI_SELL_ALL`,
  `UI_SELL_ALL_CONFIRM`, `UI_SOLD_ALL`. A shop resource and a shop scene made by 1.0 keep working.
* Builder: `interior_recipe` version 3 seeds one interior per house of the starter map;
  `second_map_recipe` version 3 builds the areas of a world plan (and `field_1` without one);
  `audio_bus_recipe` version 4 writes the surfaces and loops tables; `ui_recipes` version 13.

## 1.0.0

* First stable release. The runtime is unchanged in behavior from 0.3.0; the version number now
  matches rpggen 1.0.0, the diagnostic bundle and the Windows export preset that ship with it.
* Regenerating a project made with 0.x asks for confirmation once (`--accept-runtime-upgrade`
  or the dialog in the wizard) because the major version changed.
* Before the release (M11): the action-RPG **heavy attack** (`secondary_attack`: 1.75x damage,
  1.5x knockback, slower swing); chests built from a two-frame strip, sheet or an `open`
  animation show their open picture; the action-RPG HUD uses a nine-sliced UI bar from the pack
  when there is one and sits on the project theme's panel.
* Sound slots: a sound bank (`rpggen/sound_bank.json`), `RpgAudio.play`, `play_ui_slot` and
  `play_music_slot` (silent no-ops for an unset slot), sounds for pick-ups, hits, attacks,
  level-ups, saving, chests, doors, menus (cursor, confirm, cancel) and footsteps, the map music
  of the map root, the battle music and the title music. New events: `chest_opened`,
  `door_used` and `attack_started`.
* A game-over screen (`RpgGameOver`, `RpgDefeatPolicy` shared by both archetypes): continue from
  the newest save, try the map again or quit to the title; smoke runs skip it.
* Autosave: a fourth save slot 0 beside slots 1 to 3, written when a map is entered (never during
  a battle, dialogue or fade, and at most every 10 s), listed first in the load menu; the
  Settings menu can turn it off. Slot numbers 1 to 3 are unchanged, save version stays 1.
* A second outdoor map `field_1.tscn` behind a gap in the east wall of a new starter map; screen
  shake and hit-stop on a landed heavy attack (Settings > Screen shake); a key prompt over what the
  player can interact with; the game version on the title screen; the map and play time in the
  pause menu.
* Review follow-ups (M12): a save over a **damaged** slot file no longer replaces the last good
  backup with it (the backup is made only from a file that verifies, and the new save is moved
  into place by renaming it over the old one); four messages that bypassed translation (a damaged
  save, a save from a newer version, "cannot use that now" and the chest text) now use the keys
  `UI_SAVE_DAMAGED_LOADED_BACKUP`, `UI_SAVE_FROM_NEWER_VERSION`, `UI_CANNOT_USE_NOW`,
  `UI_CHEST_FOUND` and `UI_CHEST_EMPTY`. Projects made earlier fall back to the English text.
* Fixed while running M11 against Godot 4.7.2: the interact prompt shows `E`, not
  `E - Physical`; `RpgAudio` lets go of its streams when it leaves the tree.
* Save and load screens (M12): a slot reads "Slot 2 — Village · Lv 3 · 1:12 played · 12 Oct 14:05"
  (the map's name, level, play time and the local time of saving); the header gained the optional
  fields `saved_unix` and `map_name` (a translation key from the new `RpgMapRoot.display_name`
  export, default `MAP_<ID>`; a map without a translation shows its file name), so
  `save_version` stays 1 and older saves still read (they show no date). Saving over a used slot
  asks for confirmation with the focus on "No"; a 160x90 picture of the screen is kept beside the
  slot (`slot_N.png`, not when headless) and shown on its button; the slot loops use
  `SaveManager.SLOTS`. New keys: `UI_LV`, `UI_PLAYED`, `UI_OVERWRITE_SAVE`, `UI_YES`, `UI_NO` and
  `UI_MONTH_1` to `UI_MONTH_12`. Fixed: a toast that was dropped to make room no longer logs an
  error when its timer ends.
* Equipment (M12): `GameState.equipment` ({actor id: {weapon, armor, accessory}}, keyed by actor for
  party members), `equip`, `unequip`, `equipped_modifiers`, `stat_of` / `effective_stat` and
  `equip_preview`. Items of the categories WEAPON, ARMOR and ACCESSORY go to their slot; the old
  piece returns to the inventory. Both combat systems read attack, defense (and, turn-based,
  speed) through `get_stat` with the worn modifiers (`RpgBattleActor.stat`, the hitbox and the
  hurtbox); enemies wear nothing. The inventory menu has an Equip button and the status menu lists
  the slots; both open `RpgEquipPicker`, which shows the stat changes (green gain, red loss) of
  the focused choice before it is confirmed. The save has the optional key `equipment` (an older
  save loads with empty slots; `save_version` stays 1). New keys: `UI_EQUIP`, `UI_EQUIPMENT`,
  `UI_TAKE_OFF`, `UI_SLOT_WEAPON`, `UI_SLOT_ARMOR`, `UI_SLOT_ACCESSORY`, `UI_NO_CHANGE`,
  `UI_NOTHING_TO_EQUIP`, `UI_CANNOT_EQUIP` and `UI_MOVE_SPEED`.
* Party members (M12, turn-based): `GameState.join_party` / `leave_party` (at most `MAX_PARTY` = 4
  characters, the player included; a member is built from `game/data/actors/<id>.tres`),
  `party_ids`, `in_party`, `actor_definition` / `actor_name`, `give_experience_to`, `revive_party`
  and `heal_party_full`. Dialogue events `join_party:<id>` and `leave_party:<id>`, the condition
  `party:<id>`, and the new event `party_changed`. In battle every member acts (the controller
  already built the party from `GameState.party`; it now uses their names and art), experience is
  shared (`give_experience` now grants it to the whole party), and a fallen member stands up at
  1 HP after a victory or an escape; the defeat policy revives or heals the whole party. The
  battle UI marks whose turn it is (small text for a party of three or more), and the
  inventory menu asks on whom to use an item (`UI_USE_ON`). The status menu pages through the members with its own
  equipment. `heal_full` heals everyone. The party was already in the save. The action RPG has no
  followers in 1.0. New keys: `UI_PARTY_JOINED` and `UI_PARTY_LEFT`. New turn-based projects get the
  actor "Mira" (`companion.tres`) and a villager choice that brings her along.
* Imported maps (M12): the generator builds the Tiled and LDtk maps of a pack that the user ticks
  as `game/maps/imported/<pack>/<map>.tscn`, or as the starter map. No runtime script changed; the
  smoke steps that fight the demo's enemy pass with a note in a project whose starter map was
  imported.
* Quest journal (M12): `RpgQuestDefinition` (`game/data/quests/<id>.tres`: a title key, ordered
  `stages` [{id, description key, complete_when condition}] and `rewards` {gold, experience,
  items}). `GameState.quests[id]` holds the current stage id, or `"done"`, so saves are unchanged
  (and the older `set_quest:` / `quest:` still work on the same dictionary). `quest_start`,
  `quest_set_stage`, `quest_complete` (rewards once), `refresh_quests` (a stage whose
  `complete_when` holds moves on by itself, and the last one completes the quest; it runs on flag,
  item, gold, level-up, dialogue and load events) and `journal_ids`. Dialogue events
  `quest_start:<id>`, `quest_stage:<id>:<stage>` and `quest_complete:<id>`; conditions
  `quest_active:<id>`, `quest_done:<id>` and `quest_stage:<id>:<stage>`; a toast for every
  start, stage change and completion; new event `quest_changed`. The pause menu has a Journal
  button (`journal_menu.tscn`: Active and Completed tabs, the stages of the quest in focus).
  New keys: `UI_JOURNAL`, `UI_QUESTS_ACTIVE`, `UI_QUESTS_DONE`, `UI_NO_QUESTS_ACTIVE`,
  `UI_NO_QUESTS_DONE`, `UI_QUEST_NEW`, `UI_QUEST_UPDATED` and `UI_QUEST_DONE`. New projects get the
  quest "The villager's errand" (talk, open the chest if the map has one, tell the villager).
* Shops (M12): `RpgShopDefinition` (`game/data/shops/<id>.tres`: `stock` = [{item_id, price}] where
  a price below 0 means the item's `value`, and `sell_ratio`, default 0.5) with all-or-nothing
  `buy` / `sell` that return `""` or why they were refused (not enough gold, no room in the bag,
  not held, worthless; key and quest items are never bought). The dialogue event `open_shop:<id>`
  sends `Events.shop_requested`; `RpgUiController` opens `RpgShopMenu` (a new generated scene
  `shop_menu.tscn`) when the dialogue closes, with the game paused. The menu has Buy and Sell tabs,
  one button per item, the gold you have and the item's description, and one focus ring for the
  gamepad. `RpgInventory.room_for(item_id)`. New keys: `UI_SHOP`, `UI_BUY`, `UI_SELL`,
  `UI_GOLD_SHORT`, `UI_BOUGHT`, `UI_SOLD`, `UI_NOT_ENOUGH_GOLD`, `UI_NO_ROOM`, `UI_CANNOT_TRADE`,
  `UI_NOTHING_FOR_SALE` and `UI_NOTHING_TO_SELL`. New projects get a `village_shop` and a villager
  who offers it after the first talk.
* An item's `max_hp` modifier raises the cap everywhere (`RpgUtil.max_hp(stats)`: the status menu,
  both HUDs, healing items and heals, full refills, the level-up refill); wearing it does not heal,
  and taking it off pulls the current hp down to the smaller cap (never to 0). A `move_speed`
  modifier scales the player's walk (`RpgMovement.walk_speed()`; it is a factor on the base
  `move_speed`, so the dodge is scaled too). New event `equipment_changed(actor_id, slot)`, which
  the action-RPG HUD listens to; it was emitted before the signal existed, so nobody saw it.
* Sequences (M12): `RpgSequence` (`game/data/sequences/<id>.tres`, or kept inside a map by a
  trigger) holds commands that `RpgSequenceRunner` (created by boot under SceneRouter as
  `SequenceRunner`) plays in fixed physics steps: `move_actor`, `face`, `animate`, `wait`,
  `fade_out` / `fade_in`, `shake`, `camera_pan`, `camera_lock` / `camera_unlock`, `play_sound`,
  `show_dialogue` (a file or lines written into the command), `give_item` / `take_item`,
  `set_flag`, `set_var` / `add_var`, `event` (any dialogue event), `start_battle`, `change_map`,
  and the flow commands `label`, `goto`, `if` / `else`, `call`, `end` and `wait_for` (with
  `wait: false` a move, fade, pan or shake runs in the background while the next commands go on).
  While one runs the player's input, the interact prompt, the pause menu, autosave, overworld
  enemies and action-RPG fighters (no damage either) are held; `RpgSequenceRunner.running()` is
  what they ask. A sequence marked `skippable` is skipped with cancel: the rest plays at once
  (dialogues run their events with the first choice; a battle is still fought). Starting one:
  `RpgTriggerArea` (walk in, or interact; once per game through the flag `<entity_id>.triggered`;
  an optional condition), the dialogue event `run_sequence:<id>` (after the dialogue closes) or
  `RpgSequenceRunner.instance().run(...)`. New events `sequence_requested`, `sequence_started`,
  `sequence_finished`. `RpgActor.scripted_walk`, `hold_animation` and `release_animation`;
  `RpgSceneRouter.fade_alpha` / `set_fade_alpha`; `RpgDialogueBox.fast_forward` and
  `RpgDialogueRunner.fast_forward`.
* Variables (M12): `GameState.variables` (name -> int, `get_var` / `set_var` / `add_var`, saved
  under the optional key `variables`, so `save_version` stays 1), the dialogue events
  `set_var:<name>=<N>` and `add_var:<name>:<N>`, the condition `var:<name><op><N>` (`>=`, `<=`,
  `==`, `!=`, `>`, `<`) and the event `variable_changed`.
* Random encounters (M12, turn-based): `RpgEncounterZone` (a polygon, a shape, or the cells of an
  `Encounters` TileMapLayer; `steps_per_encounter`, default 24; `disabled_flag`),
  `RpgEncounterTable` (`game/data/encounters/<id>.tres`: weighted enemy groups, `can_escape`) and
  `RpgEncounterSteps` (tiles walked, teleports ignored, 6 grace steps after every battle). The
  turn-based mode counts the steps and starts the battles with `GameState.rng`, so a seeded game
  meets the same enemies at the same step. New turn-based projects get a zone over the east half
  of the field map (`game/data/encounters/field_1.tres`).
* Ranged combat (M12, action RPG): `RpgProjectile` (made in code, drawn as an orb or an arrow; the
  team's hitbox layers plus walls; the melee formula with the shooter's attack; spent on its first
  hit, at a wall or at its range; held during a sequence). `RpgItemDefinition.ranged`: a worn
  ranged weapon fires an arrow per attack instead of the swing (the heavy attack's arrow uses the
  heavy damage and knockback); the seeded bow is ranged.
* Enemy kinds (M12, action RPG): `behavior.kind` `melee`, `shooter`, `turret` or `charger`, with the
  components `RpgEnemyShoot` and `RpgEnemyCharge` (a telegraph tint during the windup) and new
  behavior keys (`shoot_range_px`, `keep_away_px`, `projectile_speed`, `projectile_range_px`,
  `shoot_windup_s`, `shoot_cooldown_s`, `charge_range_px`, `charge_speed`, `charge_windup_s`,
  `charge_s`, `charge_recover_s`, `charge_cooldown_s`). New definitions take the kind from words in
  the asset's name; new projects get a charger and a shooter made from the first enemy, used by the
  field map.
* Followers (M12): `RpgFollowers` (boot, under SceneRouter as `Followers`; boot's `followers`
  export) draws the party members behind the player on the map, one tile apart along the path the
  player walked, facing and walking with it. Pictures only: no body, nothing saved. Both archetypes.
  `RpgUtil.world_position` and `RpgUtil.map_tile_px` are new helpers.
* Keys, switches and gates (M12): `RpgGate` (opens for good with `key_item`, flag
  `<entity_id>.unlocked`; open while the dialogue condition `open_when` holds; drawn bars unless it
  has a "Visual" child), `RpgSwitch` (a plate, latching or `hold`, or a lever, `once`; flag
  `<entity_id>.on`) and locked map doors (`RpgDoor.key_item`, `consume_key`, `entity_id`). New keys
  `UI_LOCKED`, `UI_LOCKED_NEED`, `UI_UNLOCKED`; new events `switch_toggled`, `gate_changed`.
* Battle depth (M12, turn-based): `RpgStats.mp` / `max_mp` (saved under optional keys; +2 max MP a
  level for anyone who has some; refilled by a level up, `heal_party_full`, joining and a new game;
  `RpgUtil.max_mp`; the "mp" item effect). `RpgSkillDefinition` (`game/data/skills/<id>.tres`:
  kind physical / magic / heal / status, targets, MP cost, power, element, status and chance,
  cures) and a working `skill` command (the skill list in the item submenu; blocked by silence).
  `RpgActorDefinition` gains `skills` (skill -> level learned), `element_rates`, `status_immune`,
  `attack_element`, `attack_status` and `attack_status_chance`; `RpgItemDefinition` gains the same
  for worn equipment plus `element` and `cures` (the "cure" effect, in battle). `RpgBattleStatus`:
  poison, regen, sleep, silence, blind, haste, slow; they live on the `RpgBattleActor` and end with
  the battle. `RpgBattleMath.hit_chance` (speed, `evade`, blind), `roll_magic`, `roll_heal`,
  `apply_rate`; `RpgBattleEffects` resolves attacks, skills and the end of a round;
  `RpgBattleAi` runs `behavior.turn_based_rules` ({when, use, target, chance, once}) before the
  weights, whose keys may now be skill ids. New targets `TARGET_ALL_ALLIES`; new log entry type
  `miss`; the party panel shows MP and statuses. New turn-based projects get the skills fire, cure,
  sleep and venom, a hero who knows fire, a companion with cure and sleep, an antidote and an
  ether in the shop, and enemies with a weakness, a resistance or a rule. The skill command's label
  key is now `BATTLE_SKILL` (`BATTLE_SKILLS_NONE` stays, as "Skill", for older seeded files).
* Credits (M12): `RpgCredits` (`generated/data/credits.tres`, written on every build from the
  packs' licences, and the user's `game/data/credits_extra.tsv`) and `RpgCreditsMenu`, opened by
  a new *Credits* button on the title screen and in the pause menu (both look the button up with
  `get_node_or_null`, so scenes built before it still work). New keys `UI_CREDITS`,
  `UI_CREDITS_ASSETS`, `UI_CREDITS_ENGINE`, `UI_CREDITS_BY`.
* Eight-direction sprites (M12): a sprite can have the animations `<action>_down_left`,
  `_down_right`, `_up_left` and `_up_right`. `RpgAnimationDriver.play` takes an optional third
  argument, the direction of travel, and plays the diagonal along it when the sprite has one (a
  missing left or right diagonal is the other one mirrored); `RpgActor` passes its velocity and
  remembers it for the idle picture, and followers pass the way their path goes. A facing with no
  animation of its own now shows the direction 45 degrees next to it before it falls back to
  `down`, so a sprite drawn only in the four diagonals works. New: `dir_to_facing8`. `facing`
  stays one of four directions, so hitboxes, interaction and saves are unchanged.
* Input glyphs (M12): `RpgInputGlyphs` (`ui/input_glyphs.gd`) gives the text glyph of an action
  for the device used last: `[E]` on a keyboard, `[A]` / `[Cross]` / `[B]` on an Xbox,
  PlayStation or Nintendo pad (from the pad's name), `[Pad 0]` on a pad of unknown make. It reads
  the InputMap when asked, so remapped keys show at once. `RpgSettings` tracks the device
  (`input_device`, signal `input_device_changed`; a release, stick drift or mouse motion does not
  switch it). The interaction prompt, a key-hint line in the battle interface and on the title
  screen, and the settings remap list use it. No glyph art is bundled; the glyphs are text.
* Languages (M12): *Settings > Language* lists *System* and the locales of
  `generated/i18n` (`RpgStrings.locales()`); `RpgSettings.language` ("" follows the system) is saved
  in `settings.cfg` under `[text]` and applied with `TranslationServer.set_locale`. The settings
  menu redoes the texts it sets in code when the language changes; the title screen and battle
  hints follow `NOTIFICATION_TRANSLATION_CHANGED`. A key a language lacks shows its English text.
* Dialogue tools (M12): `RpgCondition.evaluate_on(expr, state)`, `problems(expr)` and
  `atom_problem(atom)`; `RpgDialogueRunner.execute_event_on(event, state)`, `event_problem(event)`,
  `EVENTS`, and the runner's optional `condition_check` / `event_runner` callables (the editor's test
  player uses a scratch state); `RpgDialogueJson.to_json` / `to_dict` (the import also reads a
  `portrait` path). The game's behaviour is unchanged.
* Lighting (M12): `RpgMapRoot` adds a `CanvasModulate` named `Ambient` (day outdoors,
  `RpgDayNight.INTERIOR` inside: `is_interior`, or a map id starting with "interior"; your own
  colour with `ambient_override`). `RpgLightSource` (`world/light_source.gd`, a `PointLight2D`):
  objects tagged `light` get one from the builder, with the radial texture of the lighting recipe
  (`generated/lighting/light_radial.tres`); a flame flickers, a lamp is steady, and it is switched
  off outside the camera. `RpgDayNight`: the optional time-of-day cycle (`RpgSettings.day_night`,
  *Settings → Day and night*, off by default) tints outdoor maps from the play time (a day per 24
  minutes, from 8 o'clock), so a save looks the same when it is loaded.
* Minimap and world map (M12): the builder's `minimap_recipe` saves one `ImageTexture` per map of
  `game/maps` to `generated/minimaps/<key>.tres` (`RpgMinimapData.key_for`: the project path
  without `res://` and `.tscn`, `/` as `__`), a pixel per cell with the metadata `origin_cell` and `tile_size`.
  `RpgMinimap` (`ui/minimap.gd`), added by Boot on a `CanvasLayer` named `MinimapLayer`, shows the
  area around the player with markers (`RpgMinimapData.markers`: doors, unopened chests, quest
  targets) and is hidden by `RpgSettings.minimap` (*Settings > Minimap*, on by default). A quest
  stage may name an entity id under the optional key `target`; `GameState.quest_targets()` lists
  those of the active quests. The fog: `GameState.fog_mark` / `fog_seen` / `visited_maps`, saved
  under the optional key `map_fog` ({key: {w, h, bits as base64}}; save_version stays 1).
  `RpgWorldMapMenu` (`world_map_menu`, *Pause > Map*) shows the visited maps with unseen cells
  covered. Projects built earlier keep working: the settings and pause menus look up the new
  controls by name and skip them when missing.
* `RpgDialogueLine`, `RpgDialogueChoice` and `RpgDialogueResource` are `@tool` scripts (pure data):
  the editor's dialogue tab reads and edits real instances (with placeholder instances it crashed
  the editor of a project that had dialogue). `RpgStrings.format(key, arg)` formats a translated
  toast with the English text when no translation has the key; the quest, party, door and gate
  toasts use it, so they work in the editor and in tests without the game's translations.

## 0.3.0

* Action-RPG archetype (`archetypes/arpg/`): hitboxes that are live only on attack frames, hurtboxes
  with invulnerability windows, health, knockback and crits; the player's combat state machine
  (idle, move, attack with an input buffer, hurt, dodge, dead); enemies with a component-based AI
  (detection with line of sight, chase, wander, telegraphed attacks, loot pickups); the HUD; the
  generic swing effect for characters without attack animations; optional tile-based navigation.
* Shared code: `RpgActor` gained `move_locked`, `facing_locked` and `animation_locked` (set by an
  archetype's combat code), `RpgAnimationDriver` gained `has_animation` / `play_exact`, the
  inventory menu has an extension point for archetype buttons, and boot takes the archetype's HUD.
## 0.2.0

* Turn-based archetype (`archetypes/turn_based/`): battle commands (attack, defend, item, skill
  placeholder, run), the battle controller and turn manager, the battle scene and interface,
  overworld enemies that start encounters, and the combat mode that returns the result to the map.
* A defeated enemy stays defeated across saves; escaping gives a short grace period; losing sends
  the player back to the newest save, or to the map's default spawn with full health.

## 0.1.0

* First release of the shared RPG runtime: events bus, game state, scene routing, saving,
  stats, items, inventory, dialogue, interaction, settings, audio, UI and translation-ready text.
