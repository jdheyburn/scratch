# Backlog

Deliberately deferred work, and small findings parked rather than fixed.
Recorded here so the decision is visible rather than lost. Each item names
where it came from — a spec's Deferred section, or a review finding — so the
reasoning can be checked rather than taken on faith.

## Shipped

- **Raindrop dedupe** (PR #2, 2026-09-03). Exact-URL dedupe and filing into
  the `music` collection.
- **reconcile + dismiss** (PR #3, 2026-09-07). Compares the Bandcamp
  wishlist, Bandcamp collection, Spotify "To Listen", and the beets library.
- **Source cache** (PR #4, 2026-09-08). `reconcile` answers from a local
  copy by default; `--refresh` forces a refetch.
- **Empty-title match bug** (PR #5, 2026-09-09). A title with no ASCII
  equivalent folded to the same key as a genuinely blank library title,
  producing false "worth a look" matches. Fixed by refusing to match on an
  empty folded key.
- **Raindrop fuzzy dedupe** (2026-09-10). Cross-shop duplicates — the same
  album bookmarked on Bandcamp and also Boomkat, Bleep, Phonica, or Rubadub —
  are found by parsing each shop's page-title shape and matched with the
  same loose-album, agreeing-artist rules `reconcile` already uses against
  beets. A Bandcamp copy is kept when a group has one.

## Open

### Raindrop

1. **A count-vs-records-read check in `raindrop.py`.** Makes a mid-read page
   skip visible instead of silent. Blocked on the file sitting at 198 of its
   200-line layout cap — something else has to move out first.
2. **~20 Raindrop links filed as "music" are articles, not releases**
   (Bandcamp Daily pieces, best-of lists). The tool can't currently tell an
   album from an article about albums.
3. **Feed raindrop-derived (artist, album) identity into `reconcile` as a
   source.** This dedupe work gives structured identity for Raindrop
   bookmarks, but nothing feeds it into the beets/Bandcamp/Spotify comparison
   yet.

### Matching

1. **Bundle titles are reported as owned on a partial match.** A title like
   `Fragments + Distancing`, where one half is in the library and the other
   isn't, is currently counted owned on the strength of the first half alone
   — a false positive risk in the "owned" bucket, which is otherwise close to
   fully trustworthy.
2. **Title-only fallback widening, measured but not applied.** Also checking
   the track indexes and the variant titles (not just the candidate's own
   album title) would move 90 rows from absent to possible: 48 on the
   Bandcamp wishlist, 42 on Spotify. Not applied because nobody has evaluated
   the behaviour change on its own.
3. **Title-only generic-word noise.** Live review of the "worth a look"
   rows (2026-09-09) found the `title-only` tier — which drops the artist
   check entirely — produces false matches whenever a candidate's title is a
   single common word or bare number (`Faith`, `Fire`, `1`, `Forever`,
   `Birds`, `Untitled`...). A length or word-count heuristic might cut this
   without losing real matches, but a quick check shows it wouldn't cleanly
   separate short real titles (`RÁS`, `Plush V`) from short noise (`X`,
   `Faith`) — needs measuring against the fixture set before it's applied,
   same as item 2.

### Cache

1. **A `musictrack cache` command** to inspect or clear the cache.
   `--refresh` and deleting the database file cover both today.
2. **Cache the Bandcamp summary counts** to detect drift without a full
   refetch — "your wishlist has grown by 3 since this cache." One cheap
   request against a source whose count is already read, but an unmeasured
   behaviour change.

### Smaller

1. `AlbumRef.source` doesn't round-trip cleanly through the cache.
2. `Gathered.fetched` is written but never read.
3. `describe_age(None)` and `is_stale(None)` disagree on how they treat
   "never fetched."
4. The gathering spinner shows one message for all sources rather than
   per-source progress.
5. One command-level test name overstates what it actually asserts
   (`test_reconcile.py`).

## Deliberately out of scope

Not backlog — decided against, recorded so it isn't re-proposed without a
reason to revisit:

- **Writes to any source.** Bandcamp has no published write API; Spotify and
  the beets library are left alone. The only permitted write is the SQLite
  database `reconcile`/`dismiss`/the cache use for their own state.
- **Spotify saved albums.** A saved album means the opposite of a want.
