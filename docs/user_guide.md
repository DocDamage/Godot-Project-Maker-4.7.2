# rpggen user guide

This guide takes you from installation to a project you can play. The pictures are produced by
`tools/make_doc_screenshots.py` from the bundled sample pack, so they match the program.

## 1. Install

See the [README](../README.md#install). You need rpggen, **Godot 4.7.2** (standard build) and,
optionally, the Godot **export templates for 4.7.2** (used by the export check). rpggen finds Godot
in the usual places; you can also pick the executable on the first page. Choose the file that ends
in `_console.exe` if you have it.

## 2. First run with the sample pack

1. Start rpggen. It opens on the **welcome view**: *Try the sample*, *Start with my asset pack*
   and *Open an existing project*, the projects you opened lately, and the Godot rpggen found
   (or a **Download Godot 4.7.2** button when there is none, see
   [Privacy and the network](#8-privacy-and-the-network)). Each recent project is a card with a
   picture of its starter map, its archetype, its packs and when it was last generated;
   double-click it to open it, or press **Regenerate** to go straight to the Generate page. A
   card says which pack **changed** on disk since the project was generated.
2. Press **Try the sample**. rpggen fills in the bundled sample pack, a project name and an
   output folder in *Documents*, reads the pack and starts generating with the default options.
   A line at the top of the page says so; **Back** stops the run and returns to the options for
   as long as nothing was written into your folder. (*Choose a sample* on the same card offers a
   second sample, a side-view cave: see [Metroidvania](#3a-metroidvania).)
3. Wait about a minute. The page ticks off what it does, from *Checking your setup* to *Writing
   the report*, with the percentage beside the bar; **Show details** opens the log.
4. On **Results** press **Open in Godot** and then F5. You start on the title screen, begin a new
   game, walk around, talk to the villager, open the chest and enter the house.

On a first start, when there are no recent projects yet, the welcome view shows in three steps
how the wizard works instead.

![The welcome view](images/welcome.png)

![Project page](images/wizard_project.png)

The **Help** menu has the user guide (F1 opens it at the page you are on), the list of error
codes with their fixes, the keyboard shortcuts, *Report a problem…*, *Check for updates…* and
*About rpggen* (version, licenses and the third-party notices). The **View** menu switches
between the dark and the light theme, sets the size of the thumbnails, opens review mode, and
has **Reduce motion** (no fades or sliding menus); **File** lists your recent projects. The
window's title names the project and the page you are on, with the percentage while a
generation runs, so the taskbar tells you how far it is. The steps on the left show which pages
are done (a tick), which need a look (a warning sign, with a count) and which cannot be opened
yet; in a narrow window they shrink to their circles. rpggen follows the display scaling of your system (125 %, 150 %, 200 %):
pictures stay sharp, and everything can be reached and is announced by a screen reader. **View > Language** picks the wizard's language (*Follow the system*, English, or a
language that has a translation; French is the first); it applies the next time rpggen starts.

![About rpggen](images/about_dialog.png)

## 3. Using a pack you bought

**Project page.** Add one or more packs (drag a folder or archive onto the list, or use *Add Zip/7z…* or *Add Folder…*).
Packs stay untouched: rpggen copies what it needs into the project. Pick an **output folder**
that is empty (or an existing rpggen project, see [regeneration](regeneration.md)), the **Godot
executable** and a **project name**. An empty field says in grey what it is for; red text under
a field says what is wrong, and the line above the **Next** button repeats it. The Godot's
version is shown as a chip under its label. Avoid cloud-sync folders (OneDrive, Dropbox): they can
lock files during generation (ENV-006).

Each pack is a card: its name, whether it is a folder or an archive, how many files and how big,
the format rpggen recognised (RPG Maker, LPC, Aseprite, Tiled, LDtk) and whether it found a
licence file. A pack that cannot be read shows the reason on its card; the cross removes it.

![A pack's card on the Project page](images/pack_cards.png)

Rarely, a pack has a password or contains something unsafe (ARCH-002, ARCH-003, ARCH-004); extract
it yourself and add the folder.

**Archetype page.** Choose the kind of game:

* **Turn-based**: encounters on the map start a battle screen with attack, defend, item and run.
  Up to four characters can fight together (the demo villager can bring a companion along).
* **Action RPG**: real-time sword swings with hitboxes, enemies that chase and attack, a HUD.
  Party members follow the player, and the first two help in a fight: they walk to an enemy
  near you and strike with their own attack; at 0 HP they are only down for a few seconds.

* **Metroidvania**: seen from the side. You run, jump and climb through joined rooms, fight in
  real time, and find abilities (a double jump, a dash, …) that open new ways. It has its own
  section: [Metroidvania](#3a-metroidvania).

You can generate another kind later in a new project; the shared systems (saving, dialogue,
inventory, equipment, menus) are the same.

![Archetype page](images/wizard_archetype.png)

**Audit page.** rpggen has guessed what every file is. This is where you check the guesses.

![Audit page](images/wizard_audit.png)

* The grid shows thumbnails with a coloured edge and a small glyph in the corner, so the state
  can be told without colour: ✔ green = confirmed, blue = auto-detected, ? orange = needs
  review, ! red = conflict, ∅ purple = missing from the pack, grey = unused. The chips above
  filter by status; it opens on **Needs attention**. Filters also exist for role, pack and a
  path search. A sound's card shows its waveform and its length; a recolour variant has ⧉ in
  the corner of its picture.
  All of these are one row above the grid: the chips, the two lists, the search box, the
  folder button and, at its end, **Profile**. The page's header has the count of what you have
  reviewed with its bar and the **Review mode** button; the line under the grid says how many
  assets still need attention and names the keys, with **Shortcuts** for the whole list.
* **Group by folder** (the list-shaped button in that row): a header per pack folder with how many of
  its assets are shown and the buttons *Confirm all*, *Select all* and *Make rule…*; click a
  header to fold the folder away.
* **Review mode** (*View → Review mode*, `F7`): one asset at a time, large, with its details
  beside it. `C` confirms and `X` excludes and both move on, `N` and `Shift+N` step, `1`-`9`
  set a role, and `Esc` or `F7` returns to the grid. A counter says how many are left.

  ![Review mode](images/review_mode.png)
* **The tour.** The first time the page opens, a short tour points at the parts of the page one
  after the other (*Skip* or `Esc` closes it). *Help → Show the tour again* brings it back.
* **The queue.** After the first look the page works through what needs attention: `N` and
  `Shift+N` jump to the next and the previous asset that does, and a line under the grid says how
  many are left and when the queue is empty.
* Select an asset to see its details on the right: usage (tiles, sprite, icon, ...), role (what
  the generator uses it for, e.g. GROUND, WALL, PLAYER, ENEMY), tile grid, collision, tile set,
  tags. Change a value and the thumbnail updates; **Confirm** marks an asset as checked,
  **Exclude** leaves it out. Everything is undoable (Ctrl+Z, Ctrl+Y). A sprite with animations
  plays in the panel: choose the animation, play or pause it, and see the frame number, with
  the origin and the collision shape drawn over it.
* **Sounds.** A sound shows its waveform with a play head while it plays. Music also has a
  **Loop** row: where the track jumps back to and from, in milliseconds. Drag the two markers on
  the waveform or type the numbers; **Guess** looks for the longest stretch after which the
  track goes on as before, and **Whole track** takes the points away. In the game music loops
  between these points (a WAV between both; an OGG or MP3 plays to its end and comes back to the
  start point).
* **Select similar** (`Ctrl+Shift+S`, or right-click → *Select similar*): selects the assets
  that look like the selected one, so that a set of look-alike sprites gets its role in one go.
  The same picture shipped twice in different packs is tagged `duplicate_of:<id>`.
* **LPC characters.** A character of the Liberated Pixel Cup collection comes in parts: a body,
  and hair, a head, clothes and a weapon drawn over it. rpggen reads every part and puts a
  character together by itself when a pack leaves no choice (one body, one layer of a kind).
  Where there is a choice, right-click the body (or the character) → **Compose LPC
  character…**: pick one layer of each part, or none, see the character as it stands, and
  give it a name. The character is an asset of its own, one sheet with every animation its
  body has; the parts stay unused by themselves, each with the reason on its card. *Remove
  character* takes one away again and frees its body. A layer that has no picture for an
  animation (a hat without a *run*) is not drawn in it.
* **Variants.** Right-click a sprite → **Make variant…** to get a second enemy from the one a
  pack ships: turn the hue (with saturation and brightness), or change single colours in the
  palette table (click a colour in the source picture to find its row, double-click the row to
  choose what it becomes), give it a name, and for an enemy set how its HP, attack, XP and gold
  compare with the original. The variant is an asset of its own, rendered again from its source
  whenever you generate, and an enemy variant gets its own file in `game/data/enemies/`; it is
  not placed on the demo maps. *Remove variant* takes it away again. If the source leaves the
  pack the variant is left out with ASSET-029 until it is back.

  ![Making a variant](images/variant_dialog.png)
* **Keys:** `C` confirm, `X` exclude, `N` / `Shift+N` next / previous asset that needs
  attention, `1`-`9` quick roles, `Ctrl` + mouse wheel zooms the grid (or use *View → Thumbnail
  size*). *Help → Keyboard shortcuts* lists them all; `Alt+N` and `Alt+B` are Next and Back.
* **Bulk actions:** select many assets (Ctrl/Shift-click) and use the panel at the bottom: every
  combo reads "— unchanged —" until you pick something.
* **Rules:** right-click an asset → *Make rule for this folder…* so that everything in a folder
  (a glob such as `characters/**`) gets the same role or tags, now and after pack updates. The
  *Rules* tab lists them; drag to reorder.
* **Grid editor** (*Edit grid…*): cell size, margin and separation with a live readout
  (`12 × 4, 47 non-empty, remainder 0 px`) and the five best candidates. ASSET-003 appears here
  when the sheet does not divide evenly.
* **Animations** (*Animations…*): a direction-grouped list of animations with playback, click the
  sheet to pick frames, mirror left from right, reverse, ping-pong, origin and baseline, and
  *active frames* (the hit frames) for the action RPG. An animation saved as one numbered image
  per frame (`hero_walk_down_01.png`, `hero/walk/0001.png`, `Walk (3).png`) is read as one
  animation when its name has an action word such as walk, attack or cast; a missing number in
  the row gives ADAPT-004 and the frames that exist are used. Characters drawn in eight directions
  (`walk_down_left`, `walk_ne`) use the diagonal pictures while they move diagonally.
* **Object cutter** (*Cut objects…*): draw rectangles around a house or tree in a sheet, set its
  footprint (where it blocks), door and origin. Detected objects appear blue, yours green.
* **Terrain tab:** autotile proposals for RPG Maker A2 sheets and 47-tile blob sheets. A blob
  sheet is 12 tiles by 4 (192 x 64 for 16 px tiles) in the order of Godot's *3x3 minimal*
  template, which is how most packs ship one, or with the tiles in the order of their
  neighbour masks. It is recognised in a folder or under a name that says *tileset*,
  *autotile* or *terrain*; accept the proposal and the tiles join by themselves when you
  paint. A fence or wall sheet of the same shape is not a blob terrain and stays plain tiles.
* **Packs tab:** the licence, author and URL rpggen read from each pack's licence files, and
  whether the licence asks for credit. Correct anything that is wrong: the game's *Credits*
  screen (title screen and pause menu) lists every pack with these values. A pack that needs
  credit but names no author gets ASSET-028 until you enter one.
* **Profile menu:** export your audit as a profile, import one, or find one online
  ([profiles](profiles.md)).
* **Learning from your fixes.** When you change the role, usage or collision of a few files that
  share a folder or name word, rpggen remembers it and proposes the same for new packs. Such an
  asset stays *Auto-detected* (to be reviewed) and its *Why* line says *learned from your earlier
  fixes (n times)*. A rule is used after two fixes and when you do not keep correcting it; **Edit
  → Learned rules…** manages them.
* **Contact sheet:** *Profile → Export contact sheet…* (or *File → Export contact sheet…*)
  prints the assets on A4 or Letter pages, as a PDF or one PNG per page, for review away from
  the computer: each asset's picture (optionally with its tile or frame grid), file name, role,
  status, confidence and tile or frame size. It takes the assets the grid shows now (your
  filters) or all of them.

**Mapping page.** A checklist of what the starter map and the systems need: ground, wall, player,
NPC, enemy, chest, building, UI and so on. Each row shows the chosen asset. Its list offers the
best candidates that could plausibly fill the role; **More…** opens all of them as a gallery of
thumbnails, grouped by pack with the best candidate first and a search box. The three small
buttons at the end of a row open that gallery, show the chosen asset on the Audit page (*Back*
returns) and clear the row, which goes back to the automatic choice; each says what it does
when the mouse rests on it. The header counts the roles that are filled and has **Undo**; a
required role without an asset has a warning edge. If a required role has no asset you can continue with a
**placeholder** (a labelled debug picture, ASSET-010) and fix it later.

**Sound.** Under the roles, the *Sound* section lists **sound slots**: the map, battle and title
music, the menu cursor, confirm and cancel sounds, and the sounds of a hit, an attack, a
pick-up, a chest, a door, a footstep, saving and a level-up. rpggen fills each slot from the
audio of your packs by file name; *Edit…* shows a row per slot with **Choose…** (a list of the
audio files, with ▶ to listen and the length of each), **▶** and **Clear**. A cleared slot is
silent. A pack without audio simply gives a silent game. **Add slot…** makes a slot of your own
(`sfx_<name>` or `music_<name>`): play it with the dialogue event `play_sound:<slot>`, the
`play_sound` step of a cutscene or `SceneRouter.audio.play(&"sfx_<name>")`. A slot named
`sfx_step_<surface>` is the footstep on ground of that kind (grass, stone, wood, water, sand):
rpggen reads the surface from a ground sheet's folder and file names and fills these slots
from files such as `step_grass.wav`.

![Mapping page](images/wizard_mapping.png)

**Options page.** Features (dialogue, combat, saving, demo content, editor tools, debug tools),
resolution and window mode, the **layers** of the map (Ground is always there; add Decoration,
Collision, anything), and under *Advanced* the random seed, key/gamepad bindings and the option to
**initialize a git repository** and commit.

* **Presets.** *Save as preset…* keeps the options for your next project; *Manage…* renames or
  deletes them. A preset only fills the options, never the packs or the folder, and *Reset to
  defaults* (beside the presets, in the page's header) returns to the factory values. Three presets come with rpggen and cannot be deleted:
  **Everything**, **Minimal** (tile sets, collision, animations, saving and dialogue) and
  **Just the tilesets**.
* **Options that need each other.** A feature that needs another one is greyed out while that
  one is off, with a line saying what it needs (the demo content needs tile sets, dialogue,
  combat and saving; enemy pathfinding needs combat). Switching the needed one back on
  restores what you had chosen.
* **Starter map.** The *Starter map* box sets the size in tiles (24 to 96, with the names Small,
  Medium and Large), the ground set, how many buildings, villagers, enemies, chests,
  decorations and ground patches. The picture beside it is the real plan, drawn from your assets:
  *Reroll* picks a new seed (under *Advanced*). With the default settings the map is the one earlier versions made. A project that
  already has a starter map keeps it; the box then says so and the preview is switched off.
  Every house on the map has its own interior (`interior_1`, `interior_2`, ...), and leaving it
  brings you back to the door of that house.
* **A world of several areas.** *Make a world of several areas* in the same box turns the
  project into several connected maps. The table has a row per area: a name, a **biome**
  (village, field, forest, cave or shore), a size, and how many enemies and chests; *Add*,
  *Remove*, *Up* and *Down* edit it and *Undo* (Ctrl+Z) takes a change back. The village is the
  starter map. rpggen lays the areas on a grid around it, joins neighbours with doors, fills a
  forest with trees and a shore with water, and puts one **key** in a chest somewhere you can
  reach before the gate that closes the first cave. A biome your packs cannot fill becomes the
  one before it in that list, and the report says so. The picture under the table shows the
  world as one tile per area with a dot for every door; click an area to see what stands in it,
  and *Rearrange this area* gives that area another arrangement. Once the project has been
  generated the world is fixed: the table says so, and the only change it still takes is a new
  row, joined to the area you pick. See [regeneration](regeneration.md#the-world-of-areas-and-its-repair).

  ![The areas of a world](images/areas_table.png)

* **Imported maps.** A pack that ships Tiled (`.tmx`, `.tmj`) or LDtk (`.ldtk`) maps lists them in
  the *Imported maps* box, each with a checkbox. A checked map is built into
  `game/maps/imported/<pack>/` (nothing is built unless you check it). The *Starter map* list under
  it can make one of them the starter map: the layout options above are then skipped, and that map
  has none of the demo's villager, chest or enemy (put your own in Godot). Tile layers go into the
  map layer of the same name (see *Map layers*) or become a layer of their own; flipped tiles keep
  their flips; the solid values of an LDtk IntGrid layer block the player (*Solid values…* chooses them; a value named wall, solid or collision starts solid); objects on layers named
  `spawn`, `door` or `sign` become spawn points, doors (properties `target_map`, `target_spawn`)
  and markers with a `text`. Layers saved with zlib, gzip or Zstandard compression are read.
  Like the other maps these are yours: regenerating never rewrites them.
* **Export targets.** Each checked platform gets an export preset in `export_presets.cfg`, so
  *Project → Export…* in Godot is ready to use: **Windows** (on by default, one `.exe` with the
  game inside), **Web** (`export/web/index.html`; thread support is off, so the build runs on
  itch.io without special server headers), **Linux** (`.x86_64`) and **macOS** (a `.zip` with an
  ad-hoc signature: no Apple developer ID and no notarization, so players must right-click →
  *Open* the first time; set your own bundle identifier in place of `com.example.<name>` before
  you publish). The export check test-exports each checked platform whose export templates are
  installed and notes the others (ENV-010). Checking a platform later adds its preset when you
  regenerate; presets already in the file, and your changes to them, are never touched.
* **Version control.** With *initialize a git repository* on, each generation is committed.
  Most pack licences forbid sharing the art, so a second choice says what happens to
  `assets/packs/`: *Commit the pack art with the project* (the default, a safe private copy),
  *Leave the pack art out of git* (it goes in `.gitignore`; use this before you push to a public
  host) or *Use Git LFS for the pack art*. See [regeneration](regeneration.md#git).

![Options page](images/wizard_options.png)

![The starter map preview](images/map_preview.png)

**Generate and Results.** Generation runs on a copy (`.rpggen_staging`) and only a validated,
smoke-tested result replaces your folder, so a failure never leaves a half project behind.

![Generate page](images/wizard_generate.png)

![Results page](images/wizard_results.png)

* The page leads with a picture of the starter map that was generated (click it to open the
  file) and a *What next* list: press F5, paint on the map, drag objects from the dock, edit the
  items, read the project's `README.md`. While it runs the page shows each phase with its time
  and, from the second generation on, how long the rest will take (from how long the phases
  took before on this computer); the taskbar button shows the progress, and a notification
  tells you when it is done if the window is in the background.
* **Open in Godot / Open folder / View report** (`GENERATION_REPORT.md` explains what was
  generated, what to review and the packs' licenses).
* **Restore previous** undoes the last regeneration.
* **Repair the world…** appears beside a warning about a door that leads nowhere or a map that
  cannot be reached. It shows what it would add before it writes, and saves the maps first.
  The maps rpggen made itself are mended without asking
  ([regeneration.md](regeneration.md#the-world-of-areas-and-its-repair)).
* **Notes (n)** lists what is worth knowing but did not stop the run, starting with the **checks
  that did not run** (for example the export check without export templates, or a check you turned
  off), each with the reason. `GENERATION_REPORT.md` has the same list under *Checks not run*.
* **Resolve conflicts…** appears when generated files you changed have a new version beside them
  (`.rpggen-new`): keep yours, take the new one or merge the two, file by file
  ([regeneration.md](regeneration.md#resolving-conflicts)).

  ![The conflict resolver](images/conflict_resolver.png)
* Under the picture the counts (assets, TileSets, scenes, animation sets, warnings, errors)
  are tiles; a regeneration that found nothing changed says so here and on the Generate page,
  where the checks it did not repeat have a dash ([regeneration.md](regeneration.md)).
* **After a failure** the page says which step failed and shows what to do about it: the
  problem with its fix, and under it what Godot itself reported (*Godot said: …*, with the file
  and the line when Godot named them) and the last 30 lines of that step's log (**Show more**
  for the rest). The buttons under the problem act on it: **Open the log**, **Show this asset
  in the audit** when the file belongs to one of your assets, and **Open failed folder**;
  **Export diagnostic bundle** packs everything for a bug report.

  ![The Results page after a failed run](images/results_failed.png)

## 3a. Metroidvania

The third kind of game is seen **from the side**: you run and jump through rooms that are joined
into one world, and some ways are closed until you have found the ability that opens them.

**Trying it.** On the welcome view, **Choose a sample** on the *Try the sample* card lists two
samples: the *Top-down village* (what a click on the card itself gives) and the *Side-view cave*. The cave
is a small pack made for this kind of game (cave tiles, planks, ladders and spikes, a hero with
run, jump, fall, climb, dash and attack animations, a crawler and a bat, a guardian, a hermit,
two ability orbs, three background layers and sounds). Choosing it fills in the pack, chooses
**Metroidvania** and starts generating; **Back** returns to the options while nothing was
written yet.

![The two samples](images/welcome_samples.png)

**Choosing it for your own pack.** On the Archetype page pick the **Metroidvania** card. Under
the cards rpggen says what it saw in your pack: *This pack looks side-view* (platform tiles,
ladders, spikes, backgrounds in layers, a character that faces left and right), or that *your
characters have walk-down animations*: the card can still be chosen, but a top-down character
will look odd running sideways. A player without a `jump` or `fall` animation shows its idle
frame in the air; the page says so, and the report lists it (ASSET-030).

**What the roles are used for.** The Mapping page lists the roles this kind of game uses:

| Role | Used for |
|------|----------|
| Player * | the hero, seen from the side |
| Ground * | the floors and walls of every room |
| Background | the pictures behind a room; several scroll at different speeds (parallax) |
| Decoration | scenery in the rooms |
| Enemy | the creatures in the rooms |
| Boss | the guardian |
| Item | pickups and chests |
| NPC | the characters you talk to |
| UI, Portrait | menus and dialogue |

Only the two with a star are required. What your pack lacks is drawn by rpggen: a pack without
one-way platforms, ladders, spikes or breakable blocks gets plain ones in its tile size, and
without an enemy or a guardian the first ability lies in its room as a pickup instead. On the
Audit page a tile's **collision** can be *One-way* (a plank you can jump up through) or
*Ladder*, and the tags `hazard` and `breakable` mark spikes and blocks. The Sound section has
four more slots: **Jump**, **Land**, **Dash** and **Ability**, filled by file name like the
others.

**The world options.** On the Options page the *Starter map* box is the **Starter world**:

* **Rooms** (5 to 12) and the **room width** and **height** in tiles. A room is at least one
  screen large.
* **Abilities**, in the order they are found: *Double jump*, *Dash*, *Wall jump*, *High jump*
  and *Break blocks*. The first one is guarded by the guardian; each of the others lies in a
  room of its own. Every ability needs a room, so the number of rooms can never be lower than
  the abilities plus three; the box raises it for you.
* **Enemies** per room and **pickups** (potions and coins) in the whole world.
* The picture is the plan, seen from the side: one box per room where it lies, the exits
  between them, a letter where an ability is needed (**J** double jump, **D** dash, **W** wall
  jump, **H** high jump, **B** break blocks) and marks for the start, the save station, the
  guardian and the end. *Reroll* under *Advanced* gives another world.
* **Added rooms.** A row with a name and the room it lies beside makes one more room. This is
  also how a world that exists grows: once the project has been generated, the other options
  are fixed (the box says so) and a new row is the one change the world still takes.

There is no pathfinding in rooms, so *Navigation* is not offered, and the layer list shows the
layers every room has (Background, Ground, Platforms, Hazards, Decoration, Foreground).

![The starter world](images/world_preview.png)

**Playing.**

| Action | Keyboard | Gamepad |
|--------|----------|---------|
| Run | A / D, Left / Right | D-pad, left stick |
| Jump | Space, Z | A (cross) |
| Drop through a platform | Down, then jump | D-pad down, then A |
| Climb a ladder | Up / Down | D-pad, left stick |
| Attack | J, X, left mouse button | X (square) |
| Dash (once you have it) | Shift, C | right stick button |
| Talk, read, use | E, Up | Y (triangle) |

* A jump is as high as you hold the button. You can still jump for a moment after walking off
  an edge.
* **Abilities** are found as orbs, or given by the guardian. A toast says what the new ability
  does and which key uses it; the HUD shows the abilities of the world and lights the ones you
  have. A ledge that was too high, a gap that was too wide or a wall of cracked blocks is then
  a way on.
* **Rooms** change as you walk through an exit: no fade, the camera slides over. The exits of
  the guardian's room are closed while it lives.
* **Save stations.** You save only at a save station (a bench in the first room): interact with
  it to rest, which restores your health and brings ordinary enemies back, and to choose a slot.
  The game also saves by itself on every room change. At 0 HP you return to the last station
  you used, with everything you had.
* **The map.** The minimap shows the rooms you have been in, with a mark for a station and for
  an ability that still lies in a room; *Pause → Map* shows the whole world you have seen.
* The game ends with the hermit in the last room, who has the last word and the credits.

**Editing rooms in Godot.** Every room is a scene in `game/maps/rooms/`. Paint on its layers
with the TileMap editor, drag enemies, pickups, chests, signs and save stations from the **RPG
Project Tools** dock under `Entities` (an object dropped in a room lands on the floor below the
mouse), and move the exits on its edges. A room that exists is never built again, so what you
change is kept when you regenerate. The project's `README.md` has the details: the parts of a
room, abilities and gates, enemies by tag, and the guardian.

**Adding a room.** Either add a row under *Added rooms* in the wizard and generate again (the
new room is built and the room beside it gets its exit), or duplicate a room scene in Godot,
give it a new **Map Id** and set the **Target Room** and **Target Exit** of the exits on both
sides. The validator reports an exit that leads nowhere (VAL-028) and can fix it; see
[regeneration](regeneration.md#rooms-and-the-stored-plan).

## 4. In Godot

The game's *Settings* have a **Language** choice: *System* and every language of the project's
`game/i18n/strings.tsv` (add a column with a locale code to translate the game; the project's
README explains how).

**Light.** Each map has an ambient light: daylight outdoors, dimmer indoors. Objects whose name
says they give light (torch, lamp, lantern, candle, campfire) get the `light` tag in the audit,
and their scenes a light, a flickering one for a flame. You can add or remove the tag on any
object. *Settings → Day and night* (off by default) lets the outdoor light follow a day of 24
minutes of play.

**Minimap and world map.** A small map in the top-right corner shows the area around the player:
a dot for the player, marks for doors, chests not yet opened and what the current quest stage
points at, and darkness over the cells not seen yet. *Settings → Minimap* turns it off. *Pause →
Map* shows every map visited so far, the unseen parts covered; what has been seen is kept in the
save. A game with a world of several areas lists **World** first: every area where it lies,
the ones you have been to lit, with the doors between them. The pictures are made by the build from each map's tiles, so a map you repaint gets a new
one on the next regeneration.

**What the game can do, and where to change it.** The project's `README.md` has a section for
each part you are likely to edit: dialogue (and the dock's Dialogue tab), items, **equipment and
shops**, **quests** and the journal, cutscenes, keys, switches and gates, languages, credits,
sound, light, the minimap, your own build steps, and the combat of your archetype (turn-based:
the **party**, **random encounters**, skills, MP, elements and statuses, enemy tactics; action
RPG: enemy kinds such as shooters, turrets and chargers, bows, and the heavy attack).

Key prompts follow the player's device: `[E]` on the keyboard, the pad's own button name
(`[A]`, `[Cross]`, `[B]`) once a controller is used, and a remapped key at once.

The project has a `README.md` with the controls and where things are: the sound slots and how to
change them, the heavy attack of the action game, autosave and the game-over screen, and how the
maps (the starter map, a house interior per house, and the field or the areas of your world) are
connected. Your own work goes in
`game/`; rpggen never overwrites it. The **RPG Project Tools** dock lists every object, building and
character from your packs: drag one into the map (it lands on the right layer, snapped, Y-sorted),
edit an asset's role or collision in the inspector and *Rebuild*, validate the content (duplicate
entity ids, broken doors, missing sprites) and remove the demo content when you start your game.
Its **Dialogue** tab edits the conversations in `game/data/dialogue/` line by line: speaker,
portrait (from your PORTRAIT assets), text with a preview of its formatting, the condition, the
events, the choices and where the line goes next, with undo (Ctrl+Z). A condition or an event
the game would not understand is marked at once, and **Test** plays the conversation against a
pretend game state whose flags and items you tick, without touching your saves. Dialogue can be
exported to and imported from JSON. An event that names a shop, a quest or a character that does
not exist is marked too, and the validator reports it (VAL-019).

The **Quests** tab edits the quests in `game/data/quests/`: the list of stages, and for each its
id, title, description, the condition that finishes it (checked as you type), the stage it leads
to, the entity the minimap points at (pick it from the map that is open) and its rewards. A
picture beside the form shows the stages and how they follow each other, and **Test** tells you
which stage the quest reaches with the flags, items and gold you set. The **Cutscenes** tab edits
the sequences in `game/data/sequences/` step by step: move, face, say, wait, camera, flag, give,
play sound and fade each have a form (every other command can be edited as JSON), a step that
names a character the open map does not have is marked, and **Test** plays the cutscene in the
game when you have started it from the editor. Both tabs undo with Ctrl+Z and export and import
JSON.

![The Quests tab](images/quests_tab.png)

On the dock's **Validate** tab, **Fix** and **Fix all** mend doors that lead nowhere and maps that
cannot be reached (they add the missing spawn point or door; Ctrl+Z takes it back).

**Shops.** In a shop, left and right choose how many to buy or sell (up to what you can pay for,
carry or own), and **Sell all** sells everything the shop buys after a second press.

Your own build steps go in `game/builder_recipes/`: GDScript files that run after rpggen's
steps on every build ([custom recipes](recipes.md)).

## 5. Regenerating

Change options, fix the audit, or add a new release of a pack, then run rpggen on the same output
folder. Your maps, scenes and everything under `game/` are kept. Read [regeneration](regeneration.md).

Before anything is written, rpggen lists what the run will change: the files it updates, the
generated files you changed (their new version is written beside them as `.rpggen-new`), the
files it no longer makes, the files you deleted (they stay deleted) and where the backup goes.
**Cancel** leaves the project exactly as it was. *Edit → Show changes before regenerating* turns
the list off.

![The changes a regeneration will make](images/regeneration_preview.png)

## 6. Troubleshooting

Every message has a code; [errors.md](errors.md) lists all of them with the fix. The common ones:

| Code | Meaning | What to do |
|------|---------|------------|
| ENV-001 / ENV-002 | Godot not found or not 4.7.x | Select the Godot 4.7.2 executable on the project page. |
| ENV-003 | A different 4.7.x build than the validated 4.7.2 | Works, but use 4.7.2 for guaranteed results. |
| ENV-005 | Not enough disk space | Free space or pick another drive (3× the pack size is needed). |
| ENV-006 | Output in a cloud-sync folder | Pick a local folder. |
| ENV-007 | Paths may exceed 260 characters | Use a shorter output folder or enable Windows long paths. |
| ENV-009 | The output folder is not empty | Pick an empty folder or an existing rpggen project. |
| ENV-010 | Export templates missing | Info only: install them from Godot (Editor → Manage Export Templates) to enable the export check for that platform. |
| ASSET-010 | A required role has no asset | Assign one on the Mapping page or use a placeholder. |
| ASSET-001 / ASSET-003 | Tile size uncertain / grid does not divide | Fix the grid in the audit. |
| REGEN-005 | The Godot editor has the project open | Close it, press Retry. |
| REGEN-006 | A new major runtime version | Confirm the upgrade (`--accept-runtime-upgrade` on the CLI). |
| BUILD-00x / VAL-0xx / SMOKE-00x | A recipe, validation or smoke step failed | View the logs, export a diagnostic bundle. |
| GUI-001 | An unexpected error in rpggen | Export a diagnostic bundle and report it. |

The **Help → Error codes…** dialog looks a code up and shows what to do. Light theme:

![The audit page in the light theme](images/wizard_audit_light.png)

![The error dialog](images/crash_dialog.png)

## 7. Diagnostic bundles

If something goes wrong that you cannot fix, send a diagnostic bundle with your bug report:

* In the wizard: **Export diagnostic bundle** on the Results page or in the error dialog.
* On the command line: `rpggen-cli diagnose --target <project or .rpggen_failed folder>`.

The zip has your configuration and catalog, the ownership ledger, build results, the logs (with
your user name and home folder replaced by `<user>` and `<home>`, each cut to its last 5 MB), a
manifest of every asset (id, path, hash, size) and system information. **It never contains images
or audio.** Open it before you send it if you like.

## 7a. Running rpggen from a script

Everything the wizard does for a finished config is also a command (`rpggen-cli`, see the README).
Four options are meant for scripts and build servers:

* `--dry-run` (on `generate`) checks the packs, the output folder and the requirements and plans
  the starter map without writing anything or starting Godot. Use it to find out, before a long
  run, that a role has no asset or that the folder belongs to something else.
* `--confirm` (on `generate`) prints what a regeneration is about to change (files to update,
  your changed files that get a `.rpggen-new` copy, deletions) and asks y/N on a terminal. Without
  a terminal the answer is no and the run is cancelled (exit code 4). In the wizard the same list
  is shown in a dialog before a regeneration writes anything (Edit > Show changes before
  regenerating, on by default).
* `--json` prints one JSON document on stdout; the readable lines go to stderr.
* `--tile-size N` (on `generate --pack`) sets the base tile size, 8 to 256 px. Without it rpggen
  uses the size most of the pack's tile sheets have; a config file carries its own.
* `conflicts --target <project>` lists the files that have a `.rpggen-new` version; add a file and
  `--keep-mine`, `--take-new` or `--merge` to resolve it, as the wizard's *Resolve conflicts…*
  does.
* The **exit code** says why a command stopped: 0 OK, 1 generation failed, 2 usage error,
  3 environment or input (Godot or a pack not found, an unusable folder, a required role with no
  asset), 4 cancelled with Ctrl+C (nothing is delivered), 70 internal error (send a diagnostic
  bundle).

## 8. Privacy and the network

rpggen does not phone home. It goes online in exactly three cases, and only after you click:

1. **Find profile online** (Audit page, Profile menu): downloads the community profile index
   and the profile you pick from this project's `registry/` folder on GitHub.
2. **Download Godot** (Project page, or the welcome view): downloads the official Godot 4.7.2
   from github.com/godotengine/godot/releases after you confirm the source, size and
   destination, verifies its SHA-512 checksum and keeps it in rpggen's own folder. Your other
   Godot versions are not touched.
3. **Help > Check for updates**: asks GitHub for the latest release of this project and offers
   to open its download page in your browser. rpggen never downloads or installs an update.

There is no start-up check, no background timer and no setting that enables one.

**Learned rules stay on your computer.** When you fix the role, usage or collision of assets in
the audit, rpggen keeps what it learned (*"files in a folder named `trees` are decorations"*) in
`learned_rules.json` in its data folder (see below), to suggest the same for your next packs. The
file holds folder and file-name words, the values you chose and how often; it is never uploaded
and never put in a project. **Edit → Learned rules…** lists the rules, turns them off, deletes
them or makes them folder rules of the open project; deleting the file forgets everything.

## 9. Where rpggen keeps its files

rpggen keeps what it needs in three folders, so that a disk-cleanup tool (which empties folders
called "cache") cannot take your work with it. **Edit → Storage…** shows how big each part is and
clears it.

![The Storage dialog](images/storage_dialog.png)

| Folder | What is in it | Windows | Linux | macOS |
|--------|---------------|---------|-------|-------|
| Settings | `settings.json`: window, theme, recent projects, option presets | `%LOCALAPPDATA%\rpggen\config` | `~/.config/rpggen` | `~/Library/Application Support/rpggen` |
| Your data | drafts of audits you have not generated yet, installed pack profiles, the rules learned from your fixes (`learned_rules.json`), the Godot rpggen downloaded, the logs | `%LOCALAPPDATA%\rpggen\data` | `~/.local/share/rpggen` | `~/Library/Application Support/rpggen` |
| Cache | extracted archives, analysis results, file lists, thumbnails, GIF and frame strips, terrain sheets | `%LOCALAPPDATA%\rpggen\cache` | `~/.cache/rpggen` | `~/Library/Caches/rpggen` |

(On Linux the `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `XDG_CACHE_HOME` variables are honoured.)

* **The cache can always be made again**, so it is kept small: extracted packs beyond the limit
  in **Storage…** (10 GB by default) are removed, the least recently used first and never the one
  you are working with; analysis results, file lists and thumbnails together stay under 1 GB.
* **Your data is only deleted by you.** Clearing it in **Storage…** first lists what you lose. A
  half-downloaded Godot that was not resumed for a week is the only thing removed by itself.
* A version before 1.0 kept everything in one folder; the first start moves the settings, drafts,
  profiles, Godot and logs to their new places and never overwrites what is already there.
* Your **generated projects** are never in these folders: they are where you chose to put them.
