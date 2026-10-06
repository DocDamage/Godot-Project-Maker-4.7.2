# rpggen

Windows desktop tool that turns 2D RPG asset packs into ready-to-edit Godot 4.7.2 projects.

The build manual lives in `Implementation Plan and Specs/`. Start with `00_START_HERE.md`.

## Development

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```
