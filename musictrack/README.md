# musictrack

Keeps the places new music is tracked in agreement with each other.

New records arrive by record store newsletter and Bandcamp email, get
bookmarked in Raindrop, and end up bought on vinyl, wishlisted on Bandcamp, or
added to Spotify. Four places hold overlapping state. This tool reconciles
them, starting with Raindrop.

## Requirements

- `uv`
- A Raindrop personal test token at `~/.config/raindrop/token`

## Install

```sh
uv tool install --from . musictrack   # puts `musictrack` on PATH
uv run musictrack raindrop dedupe     # or run it straight from the checkout
```

## The token

Create an app at [the app management console](https://app.raindrop.io/settings/integrations),
open it, and copy its **Test token**. There is no OAuth flow: the tool only
ever reads one account, its own.

```sh
mkdir -p ~/.config/raindrop
read -s t && printf %s "$t" > ~/.config/raindrop/token
chmod 600 ~/.config/raindrop/token
```

## Commands

```text
musictrack raindrop dedupe [--dry-run]   remove duplicate music bookmarks, file the strays
```

### dedupe

Reads every bookmark in the account, works out the whole plan, and shows it as
one table before writing anything.

```text
2021 raindrops read
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ action                 ┃ count ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ duplicate groups       │   100 │
│ raindrops to delete    │   102 │
│ survivors gaining tags │     1 │
│ survivors to file      │    48 │
│ stray links to file    │   620 │
└────────────────────────┴───────┘

Delete 102 duplicate(s)? [y/N]:
```

Deduping and filing are confirmed separately, so you can take one and decline
the other. `--dry-run` prints the table and stops.

**What counts as a music link.** Anything tagged `music`, or filed in the
`music` collection. Roughly half the music bookmarks are tagged but sitting in
Unsorted, so neither test catches them all on its own.

The read is wider than that. Every bookmark in the account is paged, because a
music link stranded in Unsorted cannot be found by asking for the `music`
collection. Everything read is then filtered through the rule above, so nothing
outside the music set is ever written: no tag change, no move, no delete.

**What counts as the same link.** URLs are compared after being normalised:
`https`, lowercase host, no `www.`, no trailing slash, no fragment, tracking
params dropped, remaining params sorted. Only the last of those rules currently
finds anything — bleep.com sends the same release with and without a `_kx`
param — but the rest cost nothing.

**Which copy survives.** The oldest. Then its tags absorb any real tag its
duplicates carried, and if it was in Unsorted it moves to `music`. A survivor
already filed in some other collection is left where it is.

Date tags — `12/07/2026`, `June 25 2024` — record when a batch was saved, so
they are never copied from one bookmark onto another.

**Deletes go to Trash**, not permanent removal, so a run you regret is
recoverable in the Raindrop UI.

## Development

```sh
uv run --group dev pytest -q      # tests
uv run --group dev ruff check .   # lint
uv run --group dev ruff format .  # format
uv run --group dev ty check       # types
```

All three run on commit via [prek](https://github.com/j178/prek), configured in
`prek.toml`. The repo root is a prek workspace, so these hooks run from this
directory rather than from the repo root.

Decision logic — `identity.py`, `tags.py`, `plan.py` — is pure functions over
frozen dataclasses, so the interesting cases are parametrized tests rather than
mocks. `raindrop.py` takes an injected transport; nothing in the suite reaches
the network. `tests/fixtures/raindrops.json` is a trimmed snapshot of the real
account, and `test_dedupe.py` asserts the plan it produces, so a rule change
that moves the numbers has to be deliberate.

### Layout

```text
src/musictrack/
  cli.py         the Typer app; registers each command
  commands/      one module per command
  config.py      where the token lives
  models.py      one bookmark, as much of it as this tool needs
  identity.py    what makes two bookmarks the same bookmark
  tags.py        which tags mean something, and what a survivor inherits
  plan.py        what the tool intends to do, before it does any of it
  raindrop.py    the only module that talks to Raindrop
  errors.py      every way this tool gives up, in one place
  console.py     the one console every command prints through
```
