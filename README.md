# Tesla Music Tools

A command-line tool that cleans up and standardizes metadata in a local music library before you copy it onto a USB drive for your Tesla — so duplicate artist spellings, messy "featuring" credits, and nested folder structures don't follow you into the car.

Every change is previewed before it happens: nothing is written to your files until you explicitly ask for it, and every real change is backed up first so it can be undone.

## What it does

- **Scans** your library (MP3 and M4A) and reports how many songs you have, broken down by artist and file format
- **Detects duplicate artist spellings** (`Chris Brown` vs `chris brown`, `Jay-Z & Kanye West` vs `JAY Z & Kanye West`) with a confidence score and reason for each proposed merge
- **Cleans up "featuring" credits** — splits `Chris Brown Featuring T-Pain & Nelly` into a clean `Chris Brown` artist tag and a `(feat. T-Pain & Nelly)` suffix on the title
- **Flattens nested folders** — copies every song out of its `Artist/Album/` subfolders into one flat folder, keeping original filenames, so it's easy to browse from a USB drive
- **Backs up before every real change**, and can **restore** any previous backup session
- Everything defaults to a **dry run** — nothing is modified unless you pass `--apply`

## Setup

Requires Python 3.9+.

```
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs the tool itself (as `tesla-music-tools`) along with its dependency (`mutagen`). If you'd rather not install it and just run it in place, `pip install -r requirements.txt` and use `python src/main.py` instead — every example below works either way, just swap the command name.

For running tests, also install the dev dependencies:

```
pip install -r requirements-dev.txt
```

## Usage

By default the tool looks for your music in `data/input/`. Run everything from the repository root.

**Preview what would change (safe — nothing is written):**
```
tesla-music-tools
```

**Apply the previewed changes for real:**
```
tesla-music-tools --apply
```

**Point at a different library instead of `data/input/`:**
```
tesla-music-tools --library "/path/to/your/music"
```

**Expand the file-format summary to list every song:**
```
tesla-music-tools --show-files
```

**Flatten your library into one folder** (copies into `data/output/flattened/`, original library untouched):
```
tesla-music-tools --flatten          # preview
tesla-music-tools --flatten --apply  # actually copy
```

**Undo a previous `--apply` run:**
```
tesla-music-tools --list-backups           # see available backup sessions
tesla-music-tools --restore                # preview restoring the most recent one
tesla-music-tools --restore --apply        # actually restore it
tesla-music-tools --restore 20260806_132555 --apply   # restore a specific session
```

## How it stays safe

- **Dry run by default.** Every command that modifies files only previews its changes unless you add `--apply`.
- **Automatic backups.** Every real change backs up the original file first, mirroring its full original path under `data/backups/<timestamp>/`, before any tag is written.
- **Restorable.** `--restore` copies a backup session's files back to their original locations, so an `--apply` run can always be undone.
- **Review reports.** Every apply run writes `data/output/change_plan.json` (machine-readable) and `data/output/change_report.txt` (human-readable) describing exactly what changed and why.

## Project structure

```
src/tesla_music/
  scanner.py            find audio files in the library
  metadata.py            read tags from a file
  models.py               the Song data model
  analyzer.py            aggregate artist + format stats
  normalizer.py         detect duplicate artist spellings
  confidence.py          score how likely two artist names are the same
  recommendations.py     turn duplicate groups into merge recommendations
  feat_normalizer.py     detect and split "featuring" credits
  planner.py             turn recommendations into a flat list of file changes
  backup.py               back up a file before changing it
  writer.py               write tags to MP3/M4A files
  apply.py                 apply a change plan (dry-run or real)
  restore.py               restore files from a backup session
  flattener.py            copy a nested library into one flat folder
  reporter.py             build the human-readable review report
```

## Running tests

```
pytest
```

## Status

Core CLI is functional and tested. See `ROADMAP.md` for what's next (packaging, a desktop/web UI).
