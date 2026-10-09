# Pack profiles

A **profile** is a small file (`<id>.rpgprofile.json`) that stores your audit decisions for one
asset pack: roles, tile grids, collision, animations, objects such as houses and trees, folder
rules and tile set definitions. Anyone who owns the same pack and installs the profile gets those
decisions automatically. A profile contains **no images**, only file names, hashes and decisions.

## Using a profile

* **Installed profiles** live in the cache folder (`%LOCALAPPDATA%\rpggen\cache\profiles`). When you
  add a pack, rpggen compares its files with each profile's *fingerprint* (the 20 largest images
  and their hashes). If at least `min_match` of them match (default 80%), the profile is applied:
  matching assets are `CONFIRMED`, so the audit starts nearly empty.
* **Your own edits always win** over a profile: re-analysis builds on your current catalog.
* **Import** a file: audit page → *Profile → Import profile…*.
* **Find online:** audit page → *Profile → Find profile online…*. This is the only time rpggen
  contacts the community registry, and only because you clicked. It downloads `index.json`, lists
  entries whose fingerprint overlaps at least 50% with your packs, and installs the one you pick
  after validating it.

## Making a profile

1. Audit the pack until the project looks right.
2. *Profile → Export pack profile…*, choose the pack, give it a title and your name, and keep the
   license **CC0-1.0** (required for the registry).
3. Share the file, or contribute it to the registry (below).

Audio files and fonts are covered too: a profile can give a music or sound file its role
(`AUDIO_MUSIC`, `AUDIO_SFX`) and tags, which decide which sound slot it fills by default. The
bundled sample pack's profile does this for its `music/` and `sfx/` files.

Only assets you changed or confirmed are written. Re-running your own export is deterministic.

## Format

See `rpggen/schema/profile.schema.json` (mirrors `docs/spec/02_SCHEMAS.md`). In short:
`profile_version`, `profile_id` (lowercase letters, digits, underscores), `title`, `fingerprint`
(`required_files`: path → sha256, `min_match`), `assets` (pack-relative path → facets),
`objects`, `folder_rules`, `tilesets`, `author`, `license`.

Profiles are **data only**. rpggen validates every profile against the schema before using it and
never executes anything from one; a file that does not validate is rejected whole.

## Learned rules, profiles and folder rules

Three ways to tell rpggen what a pack's files are, from the most general to the most exact:

* **Learned rules** (T12.59) are rpggen's memory of your fixes across all packs: a folder or file
  name word and the role, usage or collision you gave such files. They only *propose* (the asset
  stays *Auto-detected*, at most 85% sure) and they are yours alone: `learned_rules.json` in the
  data folder, never in a profile, a project or the registry.
* **Folder rules** belong to one project: a glob on one pack and the facets it sets. *Edit →
  Learned rules… → Add to folder rules* turns learned rules into folder rules of the open
  project (a word becomes `**/*word*/**` or `**/*word*`, which can also match a longer word).
* **Profiles** describe one pack exactly and can be shared; a profile's decisions win over learned
  rules.

## The community registry

The registry is the `registry/` folder of the project repository: `profiles/<profile_id>.rpgprofile.json`
files, an `index.json` that CI regenerates, a schema validator and `CONTRIBUTING.md`. **Find
profile online** downloads it from `main` on GitHub, in the background, and only after you click.
Set `RPGGEN_REGISTRY_BASE` (https only) to use a fork or a test server. The client
(`rpggen/core/profile_registry.py`) additionally requires:

* the license `CC0-1.0`,
* `profile_id` equal to the file name,
* a response smaller than 8 MB over HTTPS.

To contribute, follow `registry/CONTRIBUTING.md`: export the profile, add it under `registry/profiles/` and
open a pull request; CI validates it.
