# Changelog

All notable changes to the rpggen application. The generated game's runtime has its own
changelog in `godot_templates/addons/rpg_runtime/CHANGELOG.md`.

## 1.1.0 (in progress, on the branch `m13`)

* Tiled map layers saved with **Zstandard** compression are imported (TILE-009 is now only for a
  compression rpggen does not know).

* The validator and the Dialogue tab check the **shop, quest and party member ids** a dialogue
  names (`open_shop:`, `quest_start:`, `quest_stage:`, `quest_complete:`, `join_party:`); a typo
  is marked on its line while you type.

* **Shops**: left / right on a row sets how many to buy or sell (the row shows the total), and
  the Sell tab has **Sell all**. A shop can list the item categories it buys.

* **Audit review mode** (View → Review mode, `F7`, or the button beside the progress line): one
  asset at a time with a large preview and the same panel and keys; `Esc` returns to the grid.

* **Audit: Group by folder** (on the filter bar, remembered): a header per folder with its counts
  and **Confirm all**, **Select all** and **Make rule…**; click a header to fold its folder.

* **Audit: live preview**: the picture shows an object's footprint and origin and the frames
  where an attack hits; a sprite with animations has a small transport (animation, Play, frame)
  that plays it in the preview, in the panel or large in review mode.

* **Audit: Select similar** (right-click, `Ctrl+Shift+S`): selects the assets that look like the
  selected one, so one bulk edit covers them. A file that repeats another one says so in its
  *Why* line.

* **Mapping**: *More…* opens a gallery of the candidates (thumbnails grouped by pack, best first,
  with search), and each row has **Show in audit**, which opens the Audit page on that asset;
  *Back* returns to the row.

* **Options**: three built-in presets (**Everything**, **Minimal**, **Just the tilesets**) head
  the preset list; *Navigation* needs *Combat* and the demo scene needs *Tilesets*, and a box
  whose requirement is off says what it needs.

* **Generate**: from the second run on, the running phase and the top line say about how long
  is left, from how long the last ten runs took on this computer (and `taking longer than
  usual` instead of counting below zero). The CLI prints the usual time after each phase line.

* **Welcome view**: recent projects are cards with the picture of the starter map, the kind of
  game, the date of the last generation and the packs. A pack that changed since gives the card
  a line and **Regenerate**; a folder that is gone offers *Remove from the list*.

* **A tour of the Audit page** the first time you open it: five short callouts (the cards, the
  queue, the detail panel, the keys, profiles). *Skip* or `Esc` closes it for good;
  *Help → Show the tour again* brings it back.

* **Display scaling**: thumbnails, previews and the archetype drawings are made for the screen's
  scaling, so pixel art stays sharp at 150 % and 200 %. **Screen readers** get a name for every
  card of the audit grid. **View → Reduce motion**. On Windows the taskbar button shows the
  progress of a generation (the dock icon on macOS counts the steps left).

* **One interior per house**: every house of the starter map leads to its own `interior_<n>`,
  as wide as the house, and leaving it returns to that house's door. A project from 1.0 gets
  the interiors its map is missing; its map is not changed (the project's README says how to
  point a house at its interior).

* **Followers in the action RPG**: `join_party:` works there too. Party members walk behind the
  player, and the first two help in a fight: they walk to an enemy within three tiles of the
  player and swing every 1.2 s with their own attack, stay within six tiles, and are only
  "down" for five seconds at 0 HP. The HUD shows their HP bars, and the demo villager offers
  the companion in both archetypes.

* **Custom sound slots**: **Add slot…** in Mapping → Sound makes a slot of your own
  (`sfx_<name>` or `music_<name>`), played by `play_sound:<slot>` in a dialogue, the
  `play_sound` step of a cutscene or `SceneRouter.audio.play`. `sfx_step_<surface>` is the
  footstep on ground tagged `surface:<name>` (read from folder and file names: grass, stone,
  wood, sand, water, snow), filled from files like `step_grass.wav`. A bad slot name in a
  config file is `CAT-006`.

* **Waveforms and loop points**: an audio card shows the waveform of the decoded file (WAV, OGG
  Vorbis, FLAC, MP3, through libsndfile) and the detail panel shows it large with a play head.
  Music gets a **Loop** row: start and end in milliseconds, draggable markers, **Guess** and
  **Whole track**. Music now loops in the game, between the chosen points (a WAV between both;
  OGG and MP3 play to their end and come back to the start point). New dependency:
  `soundfile`.

* **Recolour variants**: right-click a sprite on the Audit page → **Make variant…** to get a
  second slime from the one a pack ships: a hue wheel with saturation and brightness, or a
  palette table with an eyedropper, a name, and for an enemy the HP, attack, XP and gold
  multipliers. The variant is an asset of its own (⧉ in the grid), rendered again from its
  source on every generation, and an enemy variant gets its own definition in
  `game/data/enemies/`. Nothing is placed on the demo maps. A variant whose source left the
  pack is `ASSET-029`.

* **Quests and Cutscenes tabs** in the Godot dock. Quests: a stage list with a form (id, title,
  description, condition with the inline checker, where it leads, the target entity with a
  picker from the open map, rewards), a read-only graph of the stages, and a test against a
  pretend game state. Cutscenes: a step list with a form per kind of step (move, face, say,
  wait, camera, flag, give, play sound, fade), the actors checked against the open map, and
  **Test**, which plays the cutscene in the game when one runs from the editor. Both export
  and import JSON, and every change is one undo step. A quest stage may now name its `next`
  stage and have `rewards` of its own.

* **A world of connected maps**: *Options → Starter map → Make a world of several areas* is a
  table of areas (name, biome, size, enemies, chests; village, field, forest, cave, shore).
  rpggen lays them on a grid around the village, joins neighbours with door pairs, places
  chests, enemies and decorations, and puts one key in an area before the gate that closes the
  first cave. The preview shows the world as one tile per area. The plan is stored in
  `rpggen/world_plan.json` and reused: once an area's map exists, a new seed or table changes
  nothing; a new row adds an area. The validator warns about a map the starter map cannot
  reach (`VAL-027`) and a door of the world that leads nowhere (`VAL-028`). The game's world
  map starts with an overview of the areas.

* **World repair**: rpggen mends the maps it made; yours it mends when you ask. After a
  generation a door that leads nowhere or a map that cannot be reached is mended in the area
  maps nobody changed (a missing spawn point, a door back, a door pair), after a backup, so
  **Restore previous** takes it back; the report lists it under *World repairs*. A map you
  changed is only offered the repair: **Repair the world…** on the Results page (with a
  preview), `rpggen-cli repair-world --target X [--dry-run]`, and **Fix** / **Fix all** in the
  dock's Validate tab (Ctrl+Z undoes). *Options → Advanced → Repair generated maps after a
  build* and `--no-repair-world` turn the automatic part off.

## 1.0.0

The first release. It turns a 2D RPG asset pack into a Godot 4.7.2 project (tile sets with
collision and terrain, animated characters, a starter map with a house and a second area, dialogue,
inventory, saving, menus, and a turn-based or action-RPG combat system), checks the result by
loading and playing it headless, and regenerates it later without touching your work.

### The wizard

* A **welcome view**: try the sample, start with your own pack, or open an existing project;
  recent projects; the Godot that was found, or a **Download Godot** button that fetches the
  official 4.7.2 after you confirm the source, size and destination and verifies its checksum.
* A menu bar (File, Edit, View, Help): recent projects, undo and redo, a dark and a light theme,
  the thumbnail size, the user guide at the page you are on (F1), an error-code lookup, the
  keyboard shortcuts, *Report a problem…*, *Check for updates…* (only when you click) and *About*.
* **Project page**: the output folder is checked as you type, with a plain explanation of what
  is wrong; Next stays enabled and shows the missing fields instead of leaving you stuck.
* **Archetype page**: two large cards with a drawn preview of each game, what is generated and
  the controls.
* **Audit page**: a queue of the assets that need attention (`N` / `Shift+N`), a corner glyph on
  every thumbnail so status is not colour-only, bulk actions, folder rules, the grid editor,
  the animation editor, the object cutter, terrain proposals, and profiles.
* **Mapping page**: roles and, new, **sound slots** (map, battle and title music; menu, hit,
  attack, pick-up, chest, door, footstep, save and level-up sounds) filled from the audio of your
  packs by file name, with a preview and the length of every file.
* **Options page**: presets, and the starter map's size, counts and seed with a **live preview**
  of the real plan drawn from your assets.
* **Generate and Results pages**: each phase with its time and an estimate of the time left,
  cancel, a desktop notification when the window is in the background, and a results page that
  leads with a picture of the generated starter map and a *What next* list.
* **Resolve conflicts**: generated files you changed and rpggen remade (`.rpggen-new`) side by
  side with the version rpggen last wrote; keep yours, take the new one or merge them line by
  line, each backed up first (also `rpggen conflicts`).
* **Project page** pack cards (licence, size, what was found); **Archetype cards** drawn with
  your pack's own art; a **sidebar** with each step's status and jumps forward to any step that
  is ready; the Mapping page's candidates inline; an Options **summary panel**; the map preview's
  legend.
* **Audit**: the detail panel opens as wide as its form needs (it no longer scrolls sideways at
  the default window size), audio and font cards with playback, role badges, a filter bar that fits, a **change
  history**, frame sequences (one numbered image per frame) read as animations, eight-direction
  characters, **learned rules** (rpggen remembers your fixes and proposes them for the next pack;
  *Edit → Learned rules…*), and a printable **contact sheet** (PDF or PNG).
* **Options**: **imported Tiled and LDtk maps** (any of them can be the starter map), **export
  targets** (Windows, Web, Linux, macOS), and what git does with the purchased **pack art**
  (commit, leave out, Git LFS).
* **Before a regeneration** the changes are listed for you to confirm; **Results** has *Play*,
  *Open starter map*, warnings grouped with **one-click fixes**, and the checks that were
  skipped, with the reason.
* The wizard **follows the system theme**, fits laptop screens, and can be shown in **French**
  (*View → Language*; more languages can be added).
* **Storage** (*Edit → Storage…*): settings, your data and a size-limited cache in the system's
  usual folders.
* Tooltips and accessible names on every control, `Alt+N` / `Alt+B`, a tab order, and status
  colours that keep a 3:1 contrast on both themes.

### The generated game

* **Equipment** (weapon, armor, accessory, with a preview of the stat change), **shops**, a
  **quest journal**, **party members** who fight together and walk behind you (turn-based), and a
  **credits** screen built from the packs' licences.
* **Random-encounter zones** and deeper turn-based battles: **skills, MP, elements, statuses**,
  hit and evade, and enemy tactics.
* Action RPG: **bows and projectiles**, and **shooter, turret and charger** enemies.
* **Cutscenes** (an event sequencer started from trigger areas or dialogue), **keys, switches and
  gates**, locked doors.
* **Lighting** (ambient day and interior light, torches and lamps, an optional day/night cycle),
  a **minimap** and a **world map** with fog of war.
* **Save and load screens**, safe save rotation, key prompts that follow the device (keyboard,
  Xbox, PlayStation, Nintendo), and an in-game **language** setting.
* In the Godot editor: a **Dialogue** tab to write and test conversations, and **your own build
  steps** (`game/builder_recipes/`), which rpggen runs on every build.
* Music and sound effects wired to the slots; autosave (slot 0); a game-over screen with
  continue, try again and quit; the action-RPG heavy attack with screen shake and hit-stop; a
  second outdoor map behind the east wall; chests that show their open picture; a key prompt over
  what you can interact with.

### Under the hood

* A **scriptable CLI**: `--json`, documented exit codes, `--dry-run`, `--confirm`, `--tile-size`,
  and `conflicts`; unknown arguments are an error.
* Faster and safer analysis: each pack is hashed once, images are analysed in parallel with real
  progress and a Cancel that cancels, folder inventories are cached, archives are extracted with
  one size budget and no links; the base tile size is read from the packs.
* Generation shows Godot's live output and build progress; a failed run keeps a lean folder;
  logs live in one place, rotated, with run ids; unexpected errors get a report.
* A Godot download with a pinned checksum, resume and retry; git commits only the files rpggen
  wrote; the editor-open check matches exact project paths.
* The template project's GDScript is strict (typed), and a test that logs a script error fails.

* The targeted Godot version lives in one file (`rpggen/godot_target.py`); `tools/bump_godot.py`
  moves the app, the workflows and the texts to a new release.
* A deterministic starter-map planner shared by the preview (Python) and the builder (GDScript),
  checked against one fixture.
* Diagnostic bundles, export presets for Windows, Web, Linux and macOS with a test export per
  target, the community profile registry client,
  and packaging for Windows (installer and portable zip), Linux (AppImage and tar.gz) and macOS
  (an unsigned `.app`), each smoke-tested frozen, with one `SHA256SUMS.txt`.
