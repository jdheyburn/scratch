# musiclib

Takes a vinyl rip from Audacity export to a verified beets import.

You record a record in Audacity and export numbered tracks (`1.flac`, `2.flac`, …) into
`~/Music/vinyl/<slug>/`. `musiclib` handles everything from there: identifying the release,
fetching artwork, tagging, transferring to the music server, and cleaning up once beets
confirms the album landed.

## Requirements

- `uv`
- ssh access to the music server (`dee`), which runs beets
- A Discogs token at `~/.config/beets/discogs_token.json` — the one beets already uses

## Install

```sh
uv tool install --from . musiclib     # puts `musiclib` on PATH
uv run musiclib vinyl sync            # or run it straight from the checkout
```

## Workflow

**1. Record and split, in Audacity.** One project per side, exported as numbered tracks into
a directory named however you like:

```text
~/Music/vinyl/wax/
  1.flac  2.flac        the tracks, numbered in play order
  a.aup3  b.aup3        one project per side
```

The slug is a note to yourself — it never leaves this machine.

**2. Capture and transfer.**

```sh
musiclib vinyl sync
```

It finds every album waiting and asks two questions each:

```text
wax
  Discogs release for wax (id, url, or 'skip'): https://www.discogs.com/release/30257615-Wax-No-90009
  -> Wax - No. 90009  [discogs 30257615]
    2024 / Wax / WAX 90009
    2 tracks, sides=2
    Correct release? [y/n]: y
  Cover image url (or 'skip'): https://f4.bcbits.com/img/a3990828446_16.jpg
    cover 2000x2000
```

Paste the id or the URL, whichever you have. Answer for every album first — nothing is
written until you've been through them all. Then you get one table and one decision:

```text
┏━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ album ┃ tracks ┃ destination                ┃ notes ┃
┡━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ wax   │      2 │ Wax - No. 90009 (30257615) │ ok    │
└───────┴────────┴────────────────────────────┴───────┘

Tag and transfer 1 album(s)? [y/n]:
```

**3. Confirm the matches.** After transferring, it drops you at the beets prompt with your
release proposed first. Confirm as usual, or skip an album to deal with later — anything you
skip is offered again next run.

**4. Archive, once you're happy.**

```sh
musiclib vinyl done
```

Verifies each album against the library and archives only what passed. Nothing is deleted,
and skipped albums are left alone.

**5. Reclaim the space, weeks later.** The Audacity projects stay in `~/Music/vinyl/done/` in
case you want to re-split. `sync` tells you when they're past the window; `musiclib vinyl gc`
removes them.

Plex picks the albums up on its own — no scan needed.

## Commands

```text
musiclib vinyl sync [SLUG...]      capture, check, tag, transfer, hand off to beets
musiclib vinyl done [SLUG...]      verify against beets, then archive both sides
musiclib vinyl gc                  delete archived albums past the retention window
musiclib vinyl reconcile           archive pending dirs already in the library
```

### sync

Auto-detects every directory under `~/Music/vinyl` holding FLACs that isn't already
imported. Positional slugs narrow it.

It runs in two passes. The first prompts for a Discogs release and a cover URL for each
album, resolves them, and runs every check — nothing is written or transferred. You get one
summary table and one confirmation. The second pass tags, transfers, and drops you at the
beets prompt.

Capture is resumable: it only prompts for albums missing an `album.yaml`, so an interrupted
run loses nothing.

| Flag | Effect |
| --- | --- |
| `--root` | Where your rips live. Default `~/Music/vinyl` |
| `--recapture` | Re-prompt for release and cover, discarding what was captured |
| `--refresh` | Re-fetch release and artwork from a hand-edited `album.yaml` |
| `--import-all` | Import everything in `pending/`, not just this run |
| `--dry-run` | Show what would happen, change nothing |

**Hard stops** exclude an album and report it; the rest of the run continues.

- The Discogs release doesn't resolve (or wasn't given)
- FLAC count doesn't equal the release's track count
- No cover, or a cover under 500px — beets' own `minwidth` would reject it

**Warnings** don't block: a cover under 1000px, or an `.aup3` count that disagrees with the
release's side count. The side check skips itself when Discogs uses numeric rather than
`A1`/`B1` positions.

### done

Requires three things before touching anything:

1. The album is in the library
2. Its item count equals the FLAC count transferred
3. Every library file exists on disk

Then dee's `pending/vinyl/<dest>` moves to `/mnt/nfs/media/vinyl-archive/`, and the local
directory moves to `~/Music/vinyl/done/` with its `.aup3` files intact. Nothing is deleted.

If you picked a different pressing at the beets prompt than the one you captured, the
applied id won't match. `done` then searches the library by artist and album, and when
exactly one album matches with the right track count it shows you what it found and asks.
Two matches is treated as ambiguous and refuses.

### gc

Deletes albums from `done/` once they're past the retention window (21 days, `--days` to
change), on confirmation. `sync` reminds you at startup when anything is eligible. This is
the only command that deletes.

### reconcile

Works entirely from the server: reads `discogs_id` from each pending directory's
`album.yaml`, asks beets, and archives what's already imported. Directories without an
`album.yaml` are listed, never guessed at.

## Files

Two per album, kept separate so a machine write can't clobber a hand edit.

**`~/Music/vinyl/<slug>/album.yaml`** — yours. Written at capture, hand-editable, and
transferred to the server as permanent provenance. Comments survive rewrites.

```yaml
# Wax - No. 90009 (2024, Wax · WAX 90009)
discogs_id: 30257615
discogs_url: https://www.discogs.com/release/30257615
cover_url: https://f4.bcbits.com/img/a3990828446_0.jpg

# cached snapshot — drives the pre-flight checks and the destination name.
# edit discogs_id or cover_url above, then run:
#   musiclib vinyl sync --refresh
release:
  artist: Wax
  album: No. 90009
  year: 2024
  label: Wax
  catalogue: WAX 90009
  format: Vinyl
  tracks: 2
  sides: 2
  side_tracks: {A: 1, B: 1}
```

**`~/Music/vinyl/.state/<slug>.yaml`** — bookkeeping. Never leaves the Mac and is safe to
delete: every field is re-derivable, and the library is always the authority on whether an
album imported.

## How it works

**Tags.** Written locally with mutagen before transfer, so rsync sees final bytes and stays
incremental. Tagging afterwards would make every re-run resend the whole album.

| Tag | Source |
| --- | --- |
| `TRACKNUMBER` | Parsed numerically from the filename, so nothing depends on sort order |
| `MUSICBRAINZ_ALBUMID` | The Discogs release id — beets stores Discogs ids in this field itself |
| `ALBUM`, `ALBUMARTIST` | The release snapshot |
| `DATE`, `CATALOGNUMBER`, `MEDIA`, `LABEL` | The release snapshot |

No per-track titles: a mis-split would make them wrong, and beets applies the real ones on
import anyway.

The last four matter more than they look. Repressings share artist, album, track count and
often catalogue number, so without them a reissue outranks the release you asked for —
measured 7th of 10 candidates for one record. Adding the year alone moved it to 1st.

**Destination naming.** Directories on the server are named from the resolved release —
`Wax - No. 90009 (30257615)` — so two different records can never collide, however you name
them locally. Path separators are replaced to match beets' own convention. An album captured
without an id lands as `<slug> (no-id)`.

**Transfer.** rsync over ssh, with `RemoteCommand=none` set inline so it doesn't depend on
an ssh alias. No compression (FLAC is already compressed). Only FLACs, `cover.jpg` and
`album.yaml` are sent — Audacity projects stay local.

**Artwork.** Fetched from the URL you give, normalised to real JPEG (sources hand back PNG
and WEBP as often as JPEG), and measured. Bandcamp URLs are upgraded to the original upload
— `_16` is 700px, `_0` is full size. Image hosts get a browser user-agent because shop CDNs
reject anything else; the Discogs API gets a descriptive one because Discogs asks for it.

## Development

```sh
uv run --group dev pytest -q      # tests
uv run --group dev ruff check .   # lint
uv run --group dev ruff format .  # format
uv run --group dev ty check       # types
```

All three run on commit via [prek](https://github.com/j178/prek), configured in
`prek.toml`. The repo root is a prek workspace, so these hooks run from this directory
rather than from the repo root — which is what lets `ty` resolve dependencies from this
`pyproject.toml`. After cloning, `prek install` writes the git hook.

Tests use a real 9.5 KB FLAC fixture rather than mocks, and the tagging tests read back with
`mediafile` — beets' own tag layer — so field names are verified against what consumes them.
Network transports are injected; nothing in the suite reaches the internet.

### Layout

```text
src/musiclib/
  cli.py         the Typer app; registers each command
  commands/      one module per command — sync, done, gc, reconcile
  capture.py     the interactive part: prompt, resolve, write album.yaml
  discogs.py     release ids in, Release out
  cover.py       artwork: where it comes from, how big it has to be
  preflight.py   what's checkable before a byte moves
  tags.py        what gets written into the FLACs
  albumfile.py   album.yaml — yours to hand-edit
  state.py       .state/ bookkeeping and the retention window
  library.py     asking beets what it actually holds
  remote.py      rsync and ssh command lines
  net.py         the only module that touches the network
```

Command modules are plain functions registered in `cli.py` rather than decorated in place, so
each imports on its own and nothing imports the CLI. `tests/test_layout.py` holds that shape:
one file per command, no import cycles, no module over 200 lines.
