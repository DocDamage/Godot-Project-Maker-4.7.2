# Changelog

All notable changes to the rpggen application. The generated game's runtime has its own
changelog in `godot_templates/addons/rpg_runtime/CHANGELOG.md`.

## 1.5.0 (in work)

* **A farm and life sim**, the seventh kind of game (not yet offered by the wizard): a farmer
  with tools, a hotbar and energy; soil that is tilled and watered and crops that grow by the
  night and the season; a farm of its own with a house, a plot, a pond or a well, a shipping
  bin and, if you want them, a coop and a barn; a village with a shop that keeps hours and
  people who keep schedules and can be befriended; animals, fishing, foraging, weather and
  seasons. On the command line: `--archetype farm`.
* **Detection for farming packs**: growth strips (a crop's stages in a row), the roles *Crop*,
  *Farm animal* and *Tool*, seasonal variants of a sheet as one card, fence sheets and drawn
  2 x 2 corner sheets as terrains, and a farmer's tool strips kept apart from the villagers.

## 1.4.0 (in work)

Three more kinds of game, and what real packs needed to be read. Nothing changes for a project
of the three older kinds: a 1.0 to 1.3 project regenerates without a prompt (but see the two
fixes in the runtime's changelog: its minimap and two of its screens are now where they were
meant to be).

* **Shoot 'em up.** A ship over a scrolling background, vertical or horizontal: waves in
  formations, four kinds of enemy, power-ups and weapons in three levels, bombs, a boss at the
  end of every stage. The stages are planned from the seed and shown as a wave chart on the
  Options page.
* **Run and gun.** A soldier seen from the side who runs, jumps, aims in eight directions and
  throws grenades; four weapons on carriers, five kinds of enemy, three kinds of boss, stages
  planned in chunks that are checked to be passable. With the **grapple arm** the soldier
  swings and hoists; the preset *Bionic* switches jumping off and plans every stage for the arm.
* **Racing.** A car seen from above against up to five rivals who drive on the same physics:
  tracks planned as closed loops with checkpoints, surfaces (road, dirt, grass, oil, boost
  arrows), pickups (boost, missile, bomb, shield, parts that stay), laps, a results screen and
  a championship table, a map of the track; relative or absolute steering.
* **The arcade framework** the three share: stages in order, lives, a score with a multiplier,
  a *Continue?* screen, the ten best runs on the title screen, a save between stages.
* **Every pack makes a game.** What a pack lacks for the kind is drawn in its tile size (a
  bullet, an explosion, a capsule, a ship, a car in sixteen headings, a road, a hook) and
  reported as a note (ASSET-031).
* **The wizard**: six cards on the Archetype page (two rows of three, or one column in a narrow
  window), a hint that names the kind a pack looks made for, each kind's options with a picture
  of its plan, the presets *Arcade classic*, *Bionic* and *Sunday drive*, and three more
  samples under *Choose a sample*: *Star lane*, *Jungle line* and *Dirt cup*.
* **Rotation sheets**: a picture of one object turned step by step (8 to 32 headings, as
  top-down car packs ship them) is recognized and used as a vehicle.
* **The command line** takes `--archetype shmup`, `run_and_gun` and `racing`, and a dry run
  says what would be planned.
* **What real packs needed.** Numbered frames without an action word are split into animations
  at blank frames (ADAPT-005) and can be named in *Animations…*; binary `.aseprite` files give
  the names and ranges of the animations; `_32x32_4frames` and `_9split` in a name are read;
  a pack that ships its art for several engines is read from Godot's folder and the copies are
  set aside; `__MACOSX`, previews, links and guide pictures are left out; names with number
  prefixes, ampersands, emoji and small typos are read; sheets named only by a number take
  their words from their folder; RPG Maker's sheet names are read wherever they lie; the list
  a sprite cutter left in a pack gives its sheets their objects (ADAPT-007); colour variants a
  pack ships as files are grouped; the 47-tile terrain sheet in the order packs ship it
  (Godot's 3x3 minimal template) is a terrain.
* **A bundle of packs.** An archive that holds many packs (a folder each, or a zip each) opens
  *Choose packs*: tick the ones to add, search them, and see what the choice comes to. Each
  becomes a pack of its own, only those are unpacked, and *Choose packs…* on the bundle's row
  changes the choice later. On the command line: `--pack <archive> --pack-folder <name>`.
* **Aseprite files without an export** are drawn from the file itself and their tags are the
  animations (layers, opacity, indexed colour; blend modes other than *normal* are drawn as
  normal and the asset is marked for review).
* **Colour variants a pack ships** are one card in the audit, with a *Variants* row to see and
  select them, and are offered together on the Mapping page.
* **The pack card** says what a pack looks like: a shooter pack, a racing pack, art for several
  engines. The grid editor shows a rotation sheet's views in a ring.
* **LPC characters**: the universal sheet is read whole (cast, thrust, shoot, and the
  generator's climb, idle, jump, sit, emote, run and the other rows, where they are drawn), and
  the LPC collection's files are read: a picture per animation, or a folder per animation with
  a picture per colour, are read as the parts of a character: its body, and the hair, clothes
  and weapons that are drawn over it. An LPC project made with an earlier version gets the
  added animations when it is regenerated.
* **LPC characters put together**: a pack with one body and one layer of each kind gets its
  character by itself; with *Compose LPC character…* on the Audit page you choose the layers
  of a body, see the result and name it. The character is one sheet with every animation of
  its body, and can be the player.
* **Four more roles** in the audit and on the Mapping page: *Vehicle*, *Explosion*,
  *Power-up* and *Hazard*. A car's rotation sheet is a vehicle; in a shooter or racing pack
  asteroids, oil and tyres are hazards and capsules and boosts are power-ups.

## 1.3.0

The look, the feel and the ease of use of the wizard. Nothing was taken away and nothing moved
out of reach: every control, menu entry and shortcut of 1.2 is there. The generated game is
unchanged (the runtime's changelog has no entry), and a project made with 1.0, 1.1 or 1.2
regenerates without a prompt.

* **A designed look, in both themes.** One set of colours, sizes and radii for the whole
  program; every button, field, list, tab, scroll bar and menu is drawn to it. Buttons say how
  much they matter (one main action per view, quiet ones beside it, red for what deletes),
  there are icons, groups are cards, and a keyboard user sees a clear focus ring. Pages fade in
  (not with *Reduce motion*).
* **The steps on the left** show what is done, what needs a look and what is not open yet, and
  shrink to their circles in a narrow window. Every page starts the same way: its name, what it
  is for, its own controls and help.
* **Welcome**: three cards of one height, *Choose a sample* on the sample card, how the wizard
  works while there are no recent projects, and the Godot that was found (or *Download*) in one
  line at the bottom.
* **Project**: a small drop zone that holds the Add buttons; hints inside the fields.
  **Audit**: one filter row with *Profile* at its end (it was three rows, and *Profile* was cut
  off in the default window), the review count in the header, a footer with the keys.
  **Mapping**: compact rows with icon buttons. **Options**: two columns in a wide window,
  *Reset to defaults* beside the presets. **Generate**: a checklist of plain-language steps and
  the percentage. **Results**: a banner, the counts as tiles.
* **Try the sample in two clicks**: the welcome card goes all the way to the Generate page and
  starts; *Back* returns to the options while nothing was written.
* **Failures that say what to do**: the Results page shows what Godot reported, with the file
  and line, the end of the failed step's log, and buttons that open the log, show the asset in
  the audit or open the failed folder.
* **A regeneration that changed nothing takes seconds**: when the packs, the audit, the options,
  rpggen and Godot are what they were and no file of the project was touched since the last
  run (a generated one, or one of your own under `game/`), the import, the build and the
  checks are not repeated (REGEN-011). `--full` on the command line, or *Run every
  check again on every regeneration* in the preview of changes, runs them all.
* The window's title names the project, the page and the progress.
* Fixed: colour codes of the terminal showed as `[0m` and the like in the Generate log.
* Fixed: a project that uses a placeholder for a missing role, or the generated side-view tiles
  of a metroidvania, got a *file is missing* warning (CAT-004) for it on every regeneration,
  and a second copy of the placeholder in its catalog each time.
* Fixed: `Alt+N` stopped working once the Next button read *Generate*.
* For contributors: pictures of every page are compared on each change
  (`python -m rpggen.dev update-ui-goldens`), and CONTRIBUTING has a *Look and feel* section.

## 1.2.0

A third kind of game: the **metroidvania**. A project made with 1.0 or 1.1 regenerates with 1.2
without a prompt: the config and save versions are the same, every new key is optional, maps and
everything under `game/` are never rewritten, and the TileSets of top-down projects are what
they were. The real-time combat scripts of the action RPG moved to a shared folder; the old
paths keep working until 2.0 (see the runtime's changelog).

* **Metroidvania** (the third card on the Archetype page): a side-view hero that runs, jumps
  with a variable height, drops through one-way platforms, climbs ladders and attacks; a world of
  joined **rooms** that change without a fade; **abilities** (double jump, dash, wall jump, high
  jump, break blocks) that open ledges, gaps, shafts and walls; a **guardian** that gives the
  first one; patrolling, flying and shooting enemies; **save stations**, a room map and a HUD of
  health pips and abilities; a hermit in the last room who ends the game.

* **Side-view detection**: platform, ladder, spike and breakable tiles, parallax background
  layers and left/right characters are recognised from folder and file words. A pack that looks
  side-view says so on its card and suggests the Metroidvania card; a top-down pack can still
  be used, with a note. New collision values for tiles: *One-way* and *Ladder*. A player without
  a jump or fall animation shows its idle frame in the air (ASSET-030, a note).

* **Starter world** (Options, for a metroidvania): rooms, room size, abilities, enemies and
  pickups, with a side-view picture of the plan. The plan is planned in advance so that every
  room can be reached and every ability is found before the way that needs it, stored in the
  project, and never planned again; *Added rooms* grows a world that exists, and the world
  repair gives the neighbour its exit. An exit that leads nowhere is VAL-028, as for doors.

* **A second sample**: *Try the sample* is a split button, *Top-down village* (as before) or
  *Side-view cave*, a small CC0 pack made for the metroidvania.

* What a pack lacks is drawn: plain one-way platforms, ladders, spikes and breakable blocks in
  the pack's tile size, an orb for an ability, a bench for the save station.

* Mapping: the roles of the archetype (Background, Decoration and Boss among them), and four
  more sound slots for it (Jump, Land, Dash, Ability).

* The Archetype page fits three cards in the minimum window: the flow of a card wraps, and the
  controls line is shown when the card is wide enough for it.

* `rpggen generate --archetype metroidvania`; a dry run describes the world ("6 rooms, 2
  abilities, a guardian"); the report's World section names the rooms.

* The integration tests run as one CI job per archetype.

* Fixed: the JSON result of a run that mended a metroidvania's exit did not fit its schema.

## 1.1.0

Polish for the wizard, seven improvements and three additions to the generated game. A project
made with 1.0 regenerates with 1.1 without a prompt: the config and save versions are the same,
every new key is optional, no generated script moved, and maps and everything under `game/` are
never rewritten. Music now loops (in 1.0 a track played once), and the dependency `soundfile`
(libsndfile) is new.

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

* Documentation for all of the above: the user guide (with pictures of review mode, the variant
  dialog, the areas table and the dock's Quests tab), the regeneration guide (the stored world
  plan and the repair rule), the project's README and the runtime's README and changelog.
  The version is 1.1.0.

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
