# Error codes

<!-- GENERATED from docs/spec/03_ERROR_CODES.md by tools/gen_error_codes.py -->

## Environment (ENV)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| ENV-001 | error | Godot executable not found at {path}. | Select the Godot 4.7.2 executable (the `_console.exe` build if available). |
| ENV-002 | error | Godot {found} is not supported: rpggen 1.0 builds projects for Godot 4.7. | Press Download Godot 4.7.2, or select a 4.7.x executable. Your other Godot versions are not touched. |
| ENV-003 | warning | Godot {found} is not the validated version 4.7.2. | Use 4.7.2 for guaranteed results. |
| ENV-004 | error | Output folder {path} is not writable. | Choose a folder you can write to. |
| ENV-005 | error | Not enough disk space: need {need_mb} MB, have {have_mb} MB. | Free disk space or choose another drive. |
| ENV-006 | warning | Output folder is inside a cloud-sync folder ({provider}). | Prefer a local folder; sync can lock files during generation. |
| ENV-007 | warning | Some output paths may exceed 260 characters (longest: {length}). | Use a shorter output folder or enable Windows long paths. |
| ENV-008 | error | Output folder is inside the asset pack folder. | Choose an output folder outside the pack. |
| ENV-009 | error | Output folder is not empty and is not an rpggen project. | Choose an empty folder or an existing generated project. |
| ENV-010 | info | {target} export templates for 4.7.2 are not installed; that export check was skipped. | Install export templates from the Godot editor to enable the check. |
| ENV-011 | error | Could not download Godot: {reason}. | Check your connection, or install Godot 4.7.2 from godotengine.org and select it. |
| ENV-012 | info | Could not check for updates: {reason}. | Check your connection, or look at the releases page yourself. |
| ENV-013 | warning | Git LFS was chosen for the pack art, but git-lfs is not installed; the art is committed as it is. | Install git-lfs (git-lfs.com) and generate again, or choose another way to handle the pack art. |

## Archives (ARCH)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| ARCH-001 | error | Archive {path} cannot be opened: {reason}. | Re-download the pack or extract it and select the folder. |
| ARCH-002 | error | Archive is password-protected. | Extract it manually and select the folder. |
| ARCH-003 | error | Unsafe path in archive: {entry}. | The archive is malformed; contact the vendor. |
| ARCH-004 | error | Archive exceeds limits ({reason}). | Extract manually if you trust the archive. |
| ARCH-005 | warning | Case-insensitive name collision: {a} vs {b}; kept {kept}. | Rename one file in a copy of the pack if both are needed. |
| ARCH-006 | info | Nested archive {entry} extracted. | — |
| ARCH-007 | warning | RAR archives need 7-Zip or UnRAR installed. | Install 7-Zip, or extract manually. |
| ARCH-008 | info | Skipped OS junk file {entry}. | — |
| ARCH-009 | warning | {entry} is a link and was skipped. | Put the real file into the pack (or into a copy of it); links are never followed. |

## Assets (ASSET)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| ASSET-001 | warning | Tile size could not be confidently determined for {file} (best {cell} at {score}). | Confirm the grid in the audit. |
| ASSET-002 | warning | Image {file} could not be decoded. | Replace or exclude the file. |
| ASSET-003 | warning | Grid for {file} does not divide the image evenly; {remainder} px ignored. | Check margin/separation in the grid editor. |
| ASSET-010 | warning | No asset with role {role} found; required by {feature}. | Assign one in Mapping, or use a placeholder. |
| ASSET-011 | info | Placeholder used for role {role}. | Replace before shipping. |
| ASSET-014 | warning | Multiple candidates for {role}: {candidates}. | Pick one in Mapping. |
| ASSET-020 | warning | RPG Maker RTP asset detected: {file}. | RTP assets are licensed for RPG Maker only; replace them. |
| ASSET-021 | info | Pack {pack_id} has no license file. | Check the vendor's license terms. |
| ASSET-022 | info | No NPC asset; the player's sprite stands in for the starter NPC. | Assign an NPC asset in Mapping. |
| ASSET-023 | info | No chest asset; item icon {asset} stands in for the starter chest. | Assign a chest asset in Mapping. |
| ASSET-024 | info | Font {asset} was not used: its pack has no license file. | Add the pack's license file, or choose another font. |
| ASSET-025 | info | No enemy asset; the player's sprite stands in for the starter enemy. | Assign an enemy asset in Mapping. |
| ASSET-026 | info | No music was found in the packs: the game will be silent. | Add a music track to an asset pack, or assign one in Mapping. |
| ASSET-027 | info | No sound effects were found in the packs. | Add sound effects to an asset pack, or assign them in Mapping. |
| ASSET-029 | warning | The variant {variant} was left out: {reason}. | Put the source file back into the pack, or remove the variant on the Audit page. |
| ASSET-030 | info | The player {asset} has no {missing} animation: its idle frame is shown in the air. | Add a jump and a fall animation on the Audit page, or use a side-view character. |
| ASSET-028 | warning | Pack {pack_id} needs attribution, but no author was found in its license files. | Enter the author on the Audit page (pack information) so that the credits screen names them. |

## Adapters (ADAPT)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| ADAPT-001 | warning | Adapter {adapter} failed on {file}: {reason}. | Report a bug with a diagnostic bundle. |
| ADAPT-002 | warning | Tiled tileset {file} references missing image {image}. | Fix the pack or map the image manually. |
| ADAPT-003 | info | Pack profile {profile_id} matched ({ratio}). | — |
| ADAPT-004 | warning | The frame numbers of {sequence} have a gap ({frames}). | Add the missing frames, or rename the files so that the numbers run without a gap. |

## Catalog (CAT)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| CAT-001 | error | {file} is not valid JSON: {reason}. | Restore from backup or regenerate. |
| CAT-002 | error | {file} does not match schema: {reason}. | Restore from backup or regenerate. |
| CAT-003 | error | Catalog version {found} is newer than this generator supports. | Update rpggen. |
| CAT-004 | warning | Asset {asset} references missing file {file}. | Re-add the file or remove the asset. |
| CAT-005 | error | Duplicate source_id {source_id} in tileset {tileset}. | Report a bug; do not edit source ids by hand. |
| CAT-006 | error | "{slot}" is not a sound slot name. | Name the slot music_<name> or sfx_<name>: lower-case letters, digits and underscores, starting with a letter, at most 31 characters after the prefix. |

## Tiles (TILE)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| TILE-001 | error | TileSet {tileset} has no sources. | Assign at least one tile sheet to it. |
| TILE-002 | warning | Tile region outside texture in {asset} at {coords}. | Fix grid margin/separation. |
| TILE-003 | warning | Collision profile for {asset} could not be inferred. | Set a collision profile in the audit. |
| TILE-004 | warning | Atlas {asset} changed size; painted tiles may be shifted. | Review the asset (status CONFLICT). |
| TILE-005 | warning | Tiles at {coords} in {asset} became empty but are kept. | Remove them in Godot if unused. |
| TILE-006 | warning | Terrain layout in {asset} not recognized; terrain skipped. | Paint manually or set terrain in the audit. |
| TILE-007 | info | Collision on {asset} {coords} was edited in Godot and kept. | — |
| TILE-008 | info | Tile animation at {coords} in {asset} is not a horizontal run and was skipped. | Rearrange frames in a copy of the sheet if needed. |
| TILE-009 | warning | Layer {layer} of map {map} was skipped: {reason}. | Save the map with zlib, gzip or Zstandard compression, or assign the layer's tile set in the audit. |

## Animation (ANIM)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| ANIM-001 | warning | Animation {anim} of {asset} has no frames. | Fix frames in the animation preview. |
| ANIM-002 | info | {anim} generated by mirroring {source_anim}. | — |

## Build (BUILD)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| BUILD-001 | error | Godot import failed (exit {code}). | See the godot_import log. |
| BUILD-002 | error | Recipe {recipe} failed: {reason}. | See the godot_build log. |
| BUILD-003 | error | Godot {phase} timed out after {seconds}s. | Retry; if it repeats, file a bug with diagnostics. |
| BUILD-004 | error | Could not save {file}: Godot error {err}. | Check disk space and permissions. |
| BUILD-005 | error | Unexpected error in phase {phase}: {reason}. | Export a diagnostic bundle and report it. |

## Validation (VAL)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| VAL-001 | error | Script failed to parse: {file}. | Fix the script (see log). |
| VAL-002 | error | Resource failed to load: {file}. | See the validate log. |
| VAL-003 | error | Missing dependency {dep} of {file}. | Regenerate, or restore the missing file. |
| VAL-004 | error | Scene failed to instantiate: {file}. | See the validate log. |
| VAL-005 | error | Main scene missing or invalid. | Regenerate. |
| VAL-006 | error | Autoload {name} failed to load. | Regenerate. |
| VAL-007 | error | Input action {action} has no events. | Check generator_config input. |
| VAL-008 | error | Duplicate entity_id {id} in {files}. | Change one id in the Inspector. |
| VAL-009 | warning | Empty entity_id on {node} in {file}. | Use the dock's "Fix entity IDs". |
| VAL-010 | error | Map round-trip failed on layer {layer}. | Report a bug with diagnostics. |
| VAL-011 | warning | Menu {scene} has focus problems: {reason}. | Fix focus neighbors. |
| VAL-012 | warning | Debug placeholder still referenced by {file}. | Assign a real asset before shipping. |
| VAL-013 | error | Runtime error logged: {line}. | See the log. |
| VAL-014 | warning | Visual of {file} is not aligned to its origin (bottom at {y}). | Set the origin in the animation/object editor. |
| VAL-015 | warning | Entity {node} in {file} is not under a Y-sorted parent. | Move it under YSorted/Entities. |
| VAL-016 | error | Door {node} in {file} targets missing map {target}. | Fix target_map in the Inspector. |
| VAL-017 | error | Door {node} in {file} targets unknown spawn {spawn} in {target}. | Add the spawn point or fix target_spawn. |
| VAL-018 | warning | Dialogue {file} line {n} mixes and/or; evaluation is left-to-right. | Split the condition or reorder it. |
| VAL-019 | warning | Dialogue {file} line {n} references unknown {kind} {item}. | Create the {kind} (an item, a shop, a quest or an actor under `game/data/`) or fix the id. |
| VAL-020 | error | Sound slot {slot} points at {path}, which does not load. | Assign another sound in Mapping, or restore the file. |
| VAL-021 | info | The smoke test is turned off in the config; the game was not played. | Set validation.smoke_test to true. |
| VAL-022 | info | The export check is turned off in the config; the project was not test-exported. | Set validation.export_check to true. |
| VAL-023 | warning | Sequence problem in {file}: {problem}. | Fix the command in the sequence resource (the command list is in the runtime README, "Sequences"). |
| VAL-024 | warning | Encounter zone {node} in {file}: {problem}. | Set a table on the zone, or fix the enemy ids in the table. |
| VAL-025 | warning | {node} in {file}: {problem}. | Fix the gate, switch or door in the Inspector (key item, condition, entity id). |
| VAL-026 | warning | Battle data problem in {file}: {problem}. | Fix the skill, actor, enemy or item resource (README.md, section 11, explains skills, statuses and enemy rules). |
| VAL-027 | warning | The map {map} cannot be reached from the starter map through doors. | Add a door pair to it (the dock's validator offers a fix), or ignore this for a map that is meant to be apart. |
| VAL-028 | warning | Door {node} in {file} leads nowhere: {what} does not exist. | Regenerate (rpggen mends the maps it made), or use Repair the world on the Results page or Fix in the dock's validator. |

## Smoke test (SMOKE)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| SMOKE-001 | error | Smoke step {step} "{name}" failed: {detail}. | See smoke log and smoke_results.json. |
| SMOKE-002 | error | Smoke test timed out at step {step}. | See smoke log. |

## Regeneration (REGEN)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| REGEN-001 | warning | User-modified generated file {file} not overwritten; new version at {file}.rpggen-new. | Resolve it with *Resolve conflicts* on the Results page or `rpggen conflicts --target <project>`. |
| REGEN-002 | info | File {file} was deleted by the user and was not recreated. | — |
| REGEN-003 | warning | Source {asset} removed from pack; tileset source {source_id} kept. | Confirm removal in the audit. |
| REGEN-004 | error | Staging promotion failed: {reason}. Target restored from backup. | See log. |
| REGEN-005 | error | The Godot editor appears to be open for {path}. | Close the Godot editor before regenerating; open scenes may be overwritten when the editor saves. |
| REGEN-006 | error | Runtime upgrade from {old} to {new} needs confirmation. | The new runtime has breaking changes (see the changelog); confirm the upgrade in the wizard or pass --accept-runtime-upgrade. |
| REGEN-007 | warning | The project was generated but the git commit failed: {reason}. | Fix the repository problem (a hook, a lock, a missing identity) and commit by hand. |
| REGEN-008 | info | Your own uncommitted changes were left out of rpggen's commit. | Commit them yourself when you are ready. |
| REGEN-009 | error | There is no .rpggen-new file for {file}: nothing to resolve. | Run `rpggen conflicts --target <project>` to list the files that have one. |
| REGEN-010 | error | {file} is not a text file, so it cannot be merged. | Keep yours or take the new version. |

## GUI (GUI)

| Code | Severity | Message | Recommended fix |
|------|----------|---------|-----------------|
| GUI-001 | error | Unexpected error: {reason}. | Export a diagnostic bundle and report it. |
