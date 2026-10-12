# 03 — Error Codes

This table is the single source of truth. T1.03 turns it into `rpggen/errors_table.py` (Python) and `godot_templates/builder/lib/error_codes.gd` (GDScript), using `tools/gen_error_codes.py`, which parses this markdown table. `docs/errors.md` is generated from the same table.

Severity: **E** = error (blocks delivery), **W** = warning, **I** = info.

| Code | Sev | Message template | Recommended fix |
|------|-----|------------------|-----------------|
| ENV-001 | E | Godot executable not found at {path}. | Select the Godot 4.7.2 executable (the `_console.exe` build if available). |
| ENV-002 | E | Godot {found} is not supported: rpggen 1.0 builds projects for Godot 4.7. | Press Download Godot 4.7.2, or select a 4.7.x executable. Your other Godot versions are not touched. |
| ENV-003 | W | Godot {found} is not the validated version 4.7.2. | Use 4.7.2 for guaranteed results. |
| ENV-004 | E | Output folder {path} is not writable. | Choose a folder you can write to. |
| ENV-005 | E | Not enough disk space: need {need_mb} MB, have {have_mb} MB. | Free disk space or choose another drive. |
| ENV-006 | W | Output folder is inside a cloud-sync folder ({provider}). | Prefer a local folder; sync can lock files during generation. |
| ENV-007 | W | Some output paths may exceed 260 characters (longest: {length}). | Use a shorter output folder or enable Windows long paths. |
| ENV-008 | E | Output folder is inside the asset pack folder. | Choose an output folder outside the pack. |
| ENV-009 | E | Output folder is not empty and is not an rpggen project. | Choose an empty folder or an existing generated project. |
| ENV-010 | I | {target} export templates for 4.7.2 are not installed; that export check was skipped. | Install export templates from the Godot editor to enable the check. |
| ENV-011 | E | Could not download Godot: {reason}. | Check your connection, or install Godot 4.7.2 from godotengine.org and select it. |
| ENV-012 | I | Could not check for updates: {reason}. | Check your connection, or look at the releases page yourself. |
| ENV-013 | W | Git LFS was chosen for the pack art, but git-lfs is not installed; the art is committed as it is. | Install git-lfs (git-lfs.com) and generate again, or choose another way to handle the pack art. |
| ARCH-001 | E | Archive {path} cannot be opened: {reason}. | Re-download the pack or extract it and select the folder. |
| ARCH-002 | E | Archive is password-protected. | Extract it manually and select the folder. |
| ARCH-003 | E | Unsafe path in archive: {entry}. | The archive is malformed; contact the vendor. |
| ARCH-004 | E | Archive exceeds limits ({reason}). | Extract manually if you trust the archive. |
| ARCH-005 | W | Case-insensitive name collision: {a} vs {b}; kept {kept}. | Rename one file in a copy of the pack if both are needed. |
| ARCH-006 | I | Nested archive {entry} extracted. | — |
| ARCH-007 | W | RAR archives need 7-Zip or UnRAR installed. | Install 7-Zip, or extract manually. |
| ARCH-008 | I | Skipped OS junk file {entry}. | — |
| ARCH-009 | W | {entry} is a link and was skipped. | Put the real file into the pack (or into a copy of it); links are never followed. |
| ASSET-001 | W | Tile size could not be confidently determined for {file} (best {cell} at {score}). | Confirm the grid in the audit. |
| ASSET-002 | W | Image {file} could not be decoded. | Replace or exclude the file. |
| ASSET-003 | W | Grid for {file} does not divide the image evenly; {remainder} px ignored. | Check margin/separation in the grid editor. |
| ASSET-010 | W | No asset with role {role} found; required by {feature}. | Assign one in Mapping, or use a placeholder. |
| ASSET-011 | I | Placeholder used for role {role}. | Replace before shipping. |
| ASSET-014 | W | Multiple candidates for {role}: {candidates}. | Pick one in Mapping. |
| ASSET-020 | W | RPG Maker RTP asset detected: {file}. | RTP assets are licensed for RPG Maker only; replace them. |
| ASSET-021 | I | Pack {pack_id} has no license file. | Check the vendor's license terms. |
| ASSET-022 | I | No NPC asset; the player's sprite stands in for the starter NPC. | Assign an NPC asset in Mapping. |
| ASSET-023 | I | No chest asset; item icon {asset} stands in for the starter chest. | Assign a chest asset in Mapping. |
| ASSET-024 | I | Font {asset} was not used: its pack has no license file. | Add the pack's license file, or choose another font. |
| ASSET-025 | I | No enemy asset; the player's sprite stands in for the starter enemy. | Assign an enemy asset in Mapping. |
| ASSET-026 | I | No music was found in the packs: the game will be silent. | Add a music track to an asset pack, or assign one in Mapping. |
| ASSET-027 | I | No sound effects were found in the packs. | Add sound effects to an asset pack, or assign them in Mapping. |
| ASSET-029 | W | The variant {variant} was left out: {reason}. | Put the source file back into the pack, or remove the variant on the Audit page. |
| ASSET-030 | I | The player {asset} has no {missing} animation: its idle frame is shown in the air. | Add a jump and a fall animation on the Audit page, or use a side-view character. |
| ASSET-031 | I | The packs have no {thing}; a drawn one stands in for it (role {role}). | Add your own to a pack and give it the role on the Audit page. |
| ASSET-032 | I | The vehicle {asset} is one picture, not a sheet of headings: the game turns it. | A sheet with the vehicle in 16 headings looks better. |
| ASSET-033 | W | The LPC character {character} was left out or is incomplete: {reason}. | Put the part back into the pack, or choose the character's parts again on the Audit page. |
| ASSET-028 | W | Pack {pack_id} needs attribution, but no author was found in its license files. | Enter the author on the Audit page (pack information) so that the credits screen names them. |
| ADAPT-001 | W | Adapter {adapter} failed on {file}: {reason}. | Report a bug with a diagnostic bundle. |
| ADAPT-002 | W | Tiled tileset {file} references missing image {image}. | Fix the pack or map the image manually. |
| ADAPT-003 | I | Pack profile {profile_id} matched ({ratio}). | — |
| ADAPT-004 | W | The frame numbers of {sequence} have a gap ({frames}). | Add the missing frames, or rename the files so that the numbers run without a gap. |
| ADAPT-005 | I | {count} animations were found in the numbered frames of {sequence}; their names are not known. | Give them names (walk, attack, ...) in the asset's animations on the Audit page. |
| ADAPT-006 | I | The Aseprite file {file} could not be read ({reason}); the pictures beside it are used without it. | — |
| ADAPT-007 | I | The sprite list {file} does not fit the sheets of the pack ({reason}); the cut pictures are used as they are. | — |
| CAT-001 | E | {file} is not valid JSON: {reason}. | Restore from backup or regenerate. |
| CAT-002 | E | {file} does not match schema: {reason}. | Restore from backup or regenerate. |
| CAT-003 | E | Catalog version {found} is newer than this generator supports. | Update rpggen. |
| CAT-004 | W | Asset {asset} references missing file {file}. | Re-add the file or remove the asset. |
| CAT-005 | E | Duplicate source_id {source_id} in tileset {tileset}. | Report a bug; do not edit source ids by hand. |
| CAT-006 | E | "{slot}" is not a sound slot name. | Name the slot music_<name> or sfx_<name>: lower-case letters, digits and underscores, starting with a letter, at most 31 characters after the prefix. |
| TILE-001 | E | TileSet {tileset} has no sources. | Assign at least one tile sheet to it. |
| TILE-002 | W | Tile region outside texture in {asset} at {coords}. | Fix grid margin/separation. |
| TILE-003 | W | Collision profile for {asset} could not be inferred. | Set a collision profile in the audit. |
| TILE-004 | W | Atlas {asset} changed size; painted tiles may be shifted. | Review the asset (status CONFLICT). |
| TILE-005 | W | Tiles at {coords} in {asset} became empty but are kept. | Remove them in Godot if unused. |
| TILE-006 | W | Terrain layout in {asset} not recognized; terrain skipped. | Paint manually or set terrain in the audit. |
| TILE-007 | I | Collision on {asset} {coords} was edited in Godot and kept. | — |
| TILE-008 | I | Tile animation at {coords} in {asset} is not a horizontal run and was skipped. | Rearrange frames in a copy of the sheet if needed. |
| TILE-009 | W | Layer {layer} of map {map} was skipped: {reason}. | Save the map with zlib, gzip or Zstandard compression, or assign the layer's tile set in the audit. |
| ANIM-001 | W | Animation {anim} of {asset} has no frames. | Fix frames in the animation preview. |
| ANIM-002 | I | {anim} generated by mirroring {source_anim}. | — |
| BUILD-001 | E | Godot import failed (exit {code}). | See the godot_import log. |
| BUILD-002 | E | Recipe {recipe} failed: {reason}. | See the godot_build log. |
| BUILD-003 | E | Godot {phase} timed out after {seconds}s. | Retry; if it repeats, file a bug with diagnostics. |
| BUILD-004 | E | Could not save {file}: Godot error {err}. | Check disk space and permissions. |
| BUILD-005 | E | Unexpected error in phase {phase}: {reason}. | Export a diagnostic bundle and report it. |
| VAL-001 | E | Script failed to parse: {file}. | Fix the script (see log). |
| VAL-002 | E | Resource failed to load: {file}. | See the validate log. |
| VAL-003 | E | Missing dependency {dep} of {file}. | Regenerate, or restore the missing file. |
| VAL-004 | E | Scene failed to instantiate: {file}. | See the validate log. |
| VAL-005 | E | Main scene missing or invalid. | Regenerate. |
| VAL-006 | E | Autoload {name} failed to load. | Regenerate. |
| VAL-007 | E | Input action {action} has no events. | Check generator_config input. |
| VAL-008 | E | Duplicate entity_id {id} in {files}. | Change one id in the Inspector. |
| VAL-009 | W | Empty entity_id on {node} in {file}. | Use the dock's "Fix entity IDs". |
| VAL-010 | E | Map round-trip failed on layer {layer}. | Report a bug with diagnostics. |
| VAL-011 | W | Menu {scene} has focus problems: {reason}. | Fix focus neighbors. |
| VAL-012 | W | Debug placeholder still referenced by {file}. | Assign a real asset before shipping. |
| VAL-013 | E | Runtime error logged: {line}. | See the log. |
| VAL-014 | W | Visual of {file} is not aligned to its origin (bottom at {y}). | Set the origin in the animation/object editor. |
| VAL-015 | W | Entity {node} in {file} is not under a Y-sorted parent. | Move it under YSorted/Entities. |
| VAL-016 | E | Door {node} in {file} targets missing map {target}. | Fix target_map in the Inspector. |
| VAL-017 | E | Door {node} in {file} targets unknown spawn {spawn} in {target}. | Add the spawn point or fix target_spawn. |
| VAL-018 | W | Dialogue {file} line {n} mixes and/or; evaluation is left-to-right. | Split the condition or reorder it. |
| VAL-019 | W | Dialogue {file} line {n} references unknown {kind} {item}. | Create the {kind} (an item, a shop, a quest or an actor under `game/data/`) or fix the id. |
| VAL-020 | E | Sound slot {slot} points at {path}, which does not load. | Assign another sound in Mapping, or restore the file. |
| VAL-021 | I | The smoke test is turned off in the config; the game was not played. | Set validation.smoke_test to true. |
| VAL-022 | I | The export check is turned off in the config; the project was not test-exported. | Set validation.export_check to true. |
| VAL-023 | W | Sequence problem in {file}: {problem}. | Fix the command in the sequence resource (the command list is in the runtime README, "Sequences"). |
| VAL-024 | W | Encounter zone {node} in {file}: {problem}. | Set a table on the zone, or fix the enemy ids in the table. |
| VAL-025 | W | {node} in {file}: {problem}. | Fix the gate, switch or door in the Inspector (key item, condition, entity id). |
| VAL-026 | W | Battle data problem in {file}: {problem}. | Fix the skill, actor, enemy or item resource (README.md, section 11, explains skills, statuses and enemy rules). |
| VAL-027 | W | The map {map} cannot be reached from the starter map through doors. | Add a door pair to it (the dock's validator offers a fix), or ignore this for a map that is meant to be apart. |
| VAL-028 | W | Door {node} in {file} leads nowhere: {what} does not exist. | Regenerate (rpggen mends the maps it made), or use Repair the world on the Results page or Fix in the dock's validator. |
| VAL-029 | W | {stage} cannot be finished as it is planned: {problem}. | Change the stage's entry in rpggen/world_plan.json and game/data/stages.json (fewer bullets, an earlier wave), or delete both files and regenerate to plan the stages again. |
| VAL-030 | W | {stage} cannot be finished by a soldier that does not jump: {problem}. | Turn the option Jump on, or delete rpggen/world_plan.json and game/data/stages.json so that the stages are planned again for the grapple, or put a block to swing from (or a plank to climb) there in the stage's scene. |
| SMOKE-001 | E | Smoke step {step} "{name}" failed: {detail}. | See smoke log and smoke_results.json. |
| SMOKE-002 | E | Smoke test timed out at step {step}. | See smoke log. |
| SMOKE-010 | E | The shoot 'em up could not be played to its credits: smoke step {step} "{name}" failed: {detail}. | See smoke log and smoke_results.json. A wave or a boss of game/data/stages.json that cannot be beaten, or a scene of generated/scenes/shmup/ that was changed, stops the run at this step. |
| SMOKE-011 | E | The run and gun could not be played to its credits: smoke step {step} "{name}" failed: {detail}. | See smoke log and smoke_results.json. A gap, a trap or a boss of a stage that cannot be passed stops the run at this step (see VAL-029 and VAL-030). |
| SMOKE-012 | E | The racing game could not be driven to its credits: smoke step {step} "{name}" failed: {detail}. | See smoke log and smoke_results.json. A track whose checkpoints cannot be driven in their order, or whose road was painted over, stops the run at this step. |
| REGEN-001 | W | User-modified generated file {file} not overwritten; new version at {file}.rpggen-new. | Resolve it with *Resolve conflicts* on the Results page or `rpggen conflicts --target <project>`. |
| REGEN-002 | I | File {file} was deleted by the user and was not recreated. | — |
| REGEN-003 | W | Source {asset} removed from pack; tileset source {source_id} kept. | Confirm removal in the audit. |
| REGEN-004 | E | Staging promotion failed: {reason}. Target restored from backup. | See log. |
| REGEN-005 | E | The Godot editor appears to be open for {path}. | Close the Godot editor before regenerating; open scenes may be overwritten when the editor saves. |
| REGEN-006 | E | Runtime upgrade from {old} to {new} needs confirmation. | The new runtime has breaking changes (see the changelog); confirm the upgrade in the wizard or pass --accept-runtime-upgrade. |
| REGEN-007 | W | The project was generated but the git commit failed: {reason}. | Fix the repository problem (a hook, a lock, a missing identity) and commit by hand. |
| REGEN-008 | I | Your own uncommitted changes were left out of rpggen's commit. | Commit them yourself when you are ready. |
| REGEN-009 | E | There is no .rpggen-new file for {file}: nothing to resolve. | Run `rpggen conflicts --target <project>` to list the files that have one. |
| REGEN-010 | E | {file} is not a text file, so it cannot be merged. | Keep yours or take the new version. |
| REGEN-011 | I | Nothing changed since the last run; this check was not repeated. | Run `rpggen generate --full`, or tick *Run every check again* in the regeneration preview, to repeat every check. |
| GUI-001 | E | Unexpected error: {reason}. | Export a diagnostic bundle and report it. |

## Rules for adding codes

1. Add a row here with the next free number in the area.
2. Run `python tools/gen_error_codes.py`.
3. Commit the regenerated files with the change that uses the code.

Message templates use `{name}` placeholders, which are filled from the `detail` dict. The generator script fails if a placeholder is not a valid identifier.
