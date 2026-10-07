# rpggen

rpggen turns a 2D RPG asset pack (a folder, `.zip`, `.7z` or `.rar` you already own) into a
ready-to-edit **Godot 4.7.2** project: TileSets with collision and terrain, animated characters,
a starter map with a building you can walk into, dialogue, inventory, saving, menus and a combat
system (turn-based or action-RPG). It checks the result by loading and playing it headless before
it gives it to you, and it can regenerate the project later without touching your work.

It is a Windows desktop application. The code also runs on Linux and macOS for development and CI,
but only Windows builds are packaged for 1.0.

![The audit page](docs/images/wizard_audit.png)

## Install

1. Download `rpggen-<version>-setup.exe` (or the portable `rpggen-<version>-portable.zip`) from the
   [Releases](https://github.com/rpggen/rpggen/releases) page, together with `SHA256SUMS.txt`.
2. Check the download (PowerShell):
   `Get-FileHash .\rpggen-1.0.0-setup.exe -Algorithm SHA256` and compare it with the line in
   `SHA256SUMS.txt`.
3. Run the installer. It installs for the current user only and needs no administrator rights.
4. Install **Godot 4.7.2** from <https://godotengine.org/> (the standard build, not .NET) and, to
   enable the export check, its export templates (Editor → Manage Export Templates).

### "Windows protected your PC"

Until the project's code-signing application is accepted (see [docs/release.md](docs/release.md)),
the installer and the executables are **not signed**, and Windows SmartScreen may stop them:

1. Click **More info**.
2. Click **Run anyway**.

Only do this for files whose SHA-256 matches `SHA256SUMS.txt` on the official Releases page. Signed
releases do not show this screen.

## First run

Start rpggen and press **Try with sample pack**. It fills in a bundled CC0 sample pack and an
output folder under *Documents*, and walks you to the last page; press **Generate** and open the
result in Godot. [docs/user_guide.md](docs/user_guide.md) explains each page and how to use a pack
you bought.

## Documentation

| Document | For |
|----------|-----|
| [docs/user_guide.md](docs/user_guide.md) | Installing, the wizard page by page, troubleshooting, diagnostic bundles |
| [docs/regeneration.md](docs/regeneration.md) | Updating packs and regenerating safely |
| [docs/profiles.md](docs/profiles.md) | Sharing your audit work as a profile; the community registry |
| [docs/adapters.md](docs/adapters.md) | Adding support for a new pack format |
| [docs/errors.md](docs/errors.md) | Every error code, with its fix |
| [docs/architecture.md](docs/architecture.md) | How it works |
| [docs/release.md](docs/release.md) | Building, signing and publishing a release |
| [docs/coverage.md](docs/coverage.md) | How well it handles real packs |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Developing rpggen |

## Command line

```bat
rpggen-cli generate --pack "C:\Packs\forest" --target "D:\Games\forest" --godot "C:\Godot\Godot_v4.7.2-stable_win64_console.exe"
rpggen-cli analyze  "C:\Packs\forest"
rpggen-cli restore  --target "D:\Games\forest"
rpggen-cli diagnose --target "D:\Games\forest"
```

`rpggen.exe` with no arguments opens the wizard; `rpggen-cli.exe` is the console build for scripts.

## Privacy

rpggen never uploads anything. The only network access is two buttons you click yourself: **Find
profile online** (downloads the community profile index and the profile you pick) and, later,
update checks. A diagnostic bundle is a zip you create and send yourself; it contains no art.

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
`Implementation Plan and Specs/` (start with `00_START_HERE.md`); `docs/spec/` is its copy.

## License

MIT, see [LICENSE](LICENSE). Third-party components and their licenses are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Asset packs keep their own licenses; the report
that rpggen writes into every project lists them.
