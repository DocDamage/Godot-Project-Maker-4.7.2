# rpggen

rpggen turns a 2D RPG asset pack (a folder, `.zip`, `.7z` or `.rar` you already own) into a
ready-to-edit **Godot 4.7.2** project: TileSets with collision and terrain, animated characters,
a starter map with buildings you can walk into, or a whole world of connected areas with a
locked cave and its key (or your own Tiled and LDtk maps), dialogue, inventory, equipment, shops,
quests, cutscenes, saving, menus, lighting, a minimap and a combat system. It makes six kinds
of game: a **turn-based RPG** with a party, an **action RPG** with followers who help, a
side-view **metroidvania** of joined rooms, abilities that open new ways, a guardian and save
stations, and three arcade games with stages, lives, bosses and high scores: a **shoot 'em up**
(scrolling up or to the right), a **run and gun** with an optional grapple arm, and a **racing
game** with rivals, pickups and a championship. What a pack lacks for the kind you choose is
drawn for it, so every pack makes a game. It checks the result by loading and playing it headless before it gives it to you,
and it can regenerate the project later without touching your work.

It is a desktop application for **Windows**, **Linux** and **macOS**, with a dark and a light
theme. *Try the sample* on its first screen makes a playable project in two clicks.

![The audit page](docs/images/wizard_audit.png)

## Install

Download the file for your system from the
[Releases](https://github.com/DocDamage/Godot-Project-Maker-4.7.2/releases) page, together with
`SHA256SUMS.txt`, and compare the file's SHA-256 with its line there before you run it.

| System | File | Check the download |
|--------|------|--------------------|
| Windows 10/11 (x64) | `rpggen-<version>-setup.exe`, or the portable `rpggen-<version>-portable.zip` | PowerShell: `Get-FileHash .\rpggen-1.2.0-setup.exe -Algorithm SHA256` |
| Linux (x86_64, glibc 2.35 or newer: Ubuntu 22.04, Debian 12, Fedora 36 and later) | `rpggen-<version>-x86_64.AppImage`, or `rpggen-<version>-linux-x86_64.tar.gz` | `sha256sum -c SHA256SUMS.txt --ignore-missing` |
| macOS 13 or newer (Apple silicon) | `rpggen-<version>-macos-arm64.zip` | `shasum -a 256 -c SHA256SUMS.txt --ignore-missing` |

* **Windows:** run the installer. It installs for the current user only and needs no
  administrator rights.
* **Linux:** `chmod +x rpggen-*.AppImage` and run it; `./rpggen-<version>-x86_64.AppImage cli
  --help` runs the command-line version. Or unpack the tar.gz and run `rpggen/rpggen` (or
  `rpggen/rpggen-cli`). Qt needs the `libxcb-cursor0` package (`sudo apt install libxcb-cursor0`
  on Ubuntu and Debian); without FUSE, start the AppImage with `APPIMAGE_EXTRACT_AND_RUN=1`.
* **macOS:** unzip and move `rpggen.app` to *Applications*. The command-line version is
  `rpggen.app/Contents/MacOS/rpggen-cli`.

Then install **Godot 4.7.2** from <https://godotengine.org/> (the standard build, not .NET), or let
rpggen download it, and, to enable the export check, its export templates (Editor → Manage Export
Templates). rpggen looks for Godot on `PATH`, in `%LOCALAPPDATA%\Programs` (Windows),
`~/.local/bin` (Linux) and `/Applications` or `~/Applications` (macOS).

### "Windows protected your PC"

Until the project's code-signing application is accepted (see [docs/release.md](docs/release.md)),
the installer and the executables are **not signed**, and Windows SmartScreen may stop them:

1. Click **More info**.
2. Click **Run anyway**.

Only do this for files whose SHA-256 matches `SHA256SUMS.txt` on the official Releases page. Signed
releases do not show this screen.

### "rpggen cannot be opened" (macOS)

The macOS app is **not signed with an Apple developer ID and not notarized** yet, so Gatekeeper
stops it the first time. After checking the SHA-256:

1. In Finder, **Control-click** (or right-click) `rpggen.app` and choose **Open**.
2. Click **Open** in the dialog. macOS remembers the choice.

On macOS 15 and later the dialog has no *Open* button: try to open the app once, then go to
**System Settings → Privacy & Security** and click **Open Anyway** next to the message about
rpggen.

## First run

Start rpggen and press **Try the sample** on the welcome view. It fills in a bundled CC0 sample
pack and an output folder under *Documents*, and walks you to the last page; press **Generate**
and open the result in Godot. No Godot yet? The welcome view finds one, or downloads the official
4.7.2 after you confirm (rpggen never goes online without a click). [docs/user_guide.md](docs/user_guide.md) explains each page and how to use a pack
you bought.

## Documentation

| Document | For |
|----------|-----|
| [docs/user_guide.md](docs/user_guide.md) | Installing, the wizard page by page, troubleshooting, diagnostic bundles |
| [docs/regeneration.md](docs/regeneration.md) | Updating packs and regenerating safely |
| [docs/profiles.md](docs/profiles.md) | Sharing your audit work as a profile; the community registry |
| [docs/recipes.md](docs/recipes.md) | Your own build steps (custom recipes) in a generated project |
| [docs/adapters.md](docs/adapters.md) | Adding support for a new pack format |
| [docs/errors.md](docs/errors.md) | Every error code, with its fix |
| [docs/architecture.md](docs/architecture.md) | How it works |
| [docs/release.md](docs/release.md) | Building, signing and publishing a release |
| [docs/coverage.md](docs/coverage.md) | How well it handles real packs |
| [CHANGELOG.md](CHANGELOG.md) | What each release contains |
| [docs/status.md](docs/status.md) | What is finished, and what is left before 1.0.0 is tagged |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Developing rpggen |

## Command line

```bat
rpggen-cli generate --pack "C:\Packs\forest" --target "D:\Games\forest" --godot "C:\Godot\Godot_v4.7.2-stable_win64_console.exe"
rpggen-cli analyze  "C:\Packs\forest"
rpggen-cli restore  --target "D:\Games\forest"
rpggen-cli conflicts --target "D:\Games\forest"
rpggen-cli diagnose --target "D:\Games\forest"
```

`rpggen.exe` with no arguments opens the wizard; `rpggen-cli.exe` is the console build for scripts.
Mistyped options are an error (exit code 2), never a guess.

### For scripts: `--json`, exit codes and `--dry-run`

**`--json`** (on `generate`, `analyze`, `restore` and `diagnose`) prints one JSON document on
stdout. Everything meant for a person (progress, the issue list) goes to stderr, so
`rpggen-cli generate ... --json > result.json` leaves a file that parses and a console that still
shows what is going on. The documents are described in `docs/spec/02_SCHEMAS.md` (section 11) and
checked against `rpggen/schema/cli.schema.json`. For `generate` the document holds `ok`, `target`,
`failed_phase`, `failed_staging`, `skipped`, `timings` and `issues` (`code`, `severity`,
`message`, `fix`, `file`):

```powershell
$result = rpggen-cli generate --pack "C:\Packs\forest" --target "D:\Games\forest" --json 2> progress.txt | Out-String | ConvertFrom-Json
if (-not $result.ok) { $result.issues | Where-Object severity -eq error | Format-Table code, message }
```

**Exit codes** are the same for every command:

| Code | Meaning |
|-----:|---------|
| 0 | OK |
| 1 | Generation failed (`BUILD`, `VAL`, `SMOKE`, `REGEN` or `TILE` errors); the work folder was kept as `.rpggen_failed` |
| 2 | Usage error: a missing or unknown argument, an unknown preset |
| 3 | Environment or input: Godot or a pack could not be found or opened, the output folder is not usable, a required role has no asset (`ENV`, `ARCH`, `CAT`, `ASSET`, `ADAPT`) |
| 4 | Cancelled with Ctrl+C. The work folder is discarded and nothing is delivered; a second Ctrl+C quits at once |
| 70 | Internal error (`BUILD-005`). Run `rpggen-cli diagnose` and report it |

**`--dry-run`** (on `generate`) does everything that needs no Godot: it checks the config, the
packs and the output folder, analyses the packs, makes the requirement check and plans the
starter map, then prints what it found (roles, tile size, map size and what stands on the map).
It creates no work folder, starts no Godot and leaves the output folder as it is, so it also
shows what a regeneration would run into. The exit code is the one a real run would give
for what it found.

```bat
rpggen-cli generate --pack "C:\Packs\forest" --target "D:\Games\forest" --dry-run --placeholder PLAYER
```

## Privacy

rpggen never uploads anything. It goes online in exactly three cases, each behind a click:
**Find profile online** (downloads the community profile index and the profile you pick),
**Download Godot** (fetches the official Godot 4.7.2 from github.com/godotengine/godot/releases)
and Help > **Check for updates** (reads the latest release of this project and opens its page; it
never downloads or installs an update). There is no automatic check. A diagnostic bundle is a zip you create and send yourself; it contains no art.

## Development

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md). The build manual the project was written from is in
`docs/spec/` (start with `00_START_HERE.md`).

## License

MIT, see [LICENSE](LICENSE). Third-party components and their licenses are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Asset packs keep their own licenses; the report
that rpggen writes into every project lists them.
