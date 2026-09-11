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
- **Raindrop fuzzy dedupe** (PR #7, 2026-09-10). Cross-shop duplicates — the
  same album bookmarked on Bandcamp and also Boomkat, Bleep, Phonica, or
  Rubadub — are found by parsing each shop's page-title shape and matched
  with the same loose-album, agreeing-artist rules `reconcile` already uses
  against beets. A Bandcamp copy is kept when a group has one. The final
  review caught and fixed two real problems before merge: the confirm
  table was truncating the shop URLs a human needs to catch a wrong
  grouping, and three same-artist releases (a two-part release, a remix,
  a reconfiguration) were being wrongly merged by the same bracket-stripping
  that lets format tags like "LP" match across shops.
- **Interactive `dedupe` confirms** (PR #9, 2026-09-10). Raised after PR #7 shipped
  fuzzy matching, which carries more false-positive risk per group than the
  exact-URL case — a single bulk "Delete N duplicates?" made it easy to
  approve well over a hundred deletions on the strength of skimming one
  table. Replaced with a walk that confirms each duplicate group on its own;
  there was no remaining use for the bulk confirm, so it was removed rather
  than kept behind a flag. Stray filing still gets one confirm at the end,
  since strays aren't duplicate groups and don't carry that risk.
- **Separate raindrop-entry links** (PR #11, 2026-09-11). The shop link and
  the raindrop-entry link were sharing one cell — visible text was the shop
  URL, but the href pointed at the Raindrop entry. Split into two hyperlinked
  columns in the confirm panel and the fuzzy-match preview: the shop link
  opens the shop page it names, and a new `raindrop` column carries a short
  `open ↗` link straight to the entry.
- **Raindrop as a reconcile want source** (PR #13, 2026-09-11). Raindrop
  bookmarks (tagged `music`, minus anything `parse_release` can't identify)
  join the Bandcamp wishlist and Spotify "To Listen" as a third want,
  compared against beets and the Bandcamp collection the same way. Live-run
  on the real account: 83 Raindrop bookmarks correctly surfaced as already-
  owned wants.

## Open

### Raindrop

1. **A count-vs-records-read check in `raindrop.py`.** Makes a mid-read page
   skip visible instead of silent. Blocked on the file sitting at 198 of its
   200-line layout cap — something else has to move out first.
2. **50 Raindrop links filed as "music" are Bandcamp Daily articles, not
   releases** (best-of lists, scene reports, album-of-the-day reviews — all
   on `daily.bandcamp.com`, counted live 2026-09-11). `parse_release`
   already refuses that whole domain, so these produce no false identity for
   `reconcile`'s Raindrop source. What's still open is `dedupe`, which has
   no way to tell one of these from a real release and files them as
   ordinary stray music links.
3. **Same-artist reissue/remaster/pre-order titles aren't fuzzy-matched, by
   design.** The bracket-stripping that lets `Album LP` match `Album` across
   shops also strips genuine edition differences, so the guard added after
   PR #7's final review refuses any pair where that stripped text differs —
   which correctly keeps `(Part 1)` away from `(Part 2)`, but also keeps a
   `(Remastered)` or `(Reissue)` copy from matching its plain counterpart.
   Accepted as-is (three known misses on the real account) rather than
   building a list of "noise" words to special-case, matching how
   `reconcile`'s own matching already accepts this exact tension elsewhere.
4. **Some shop links have gone dead (404) since they were saved** — seen on
   Phonica, where a product page's URL scheme changed and the old link no
   longer resolves. `dedupe` has no way to notice today: it never fetches a
   link, only reads the title Raindrop already cached at save time. Idea
   floated: when a dead link surfaces in a group, look the album up on
   Bandcamp and replace it with a fresh Bandcamp bookmark rather than leaving
   the 404 behind. Not scoped — needs a design for detecting "dead" (a fetch
   per link is new I/O this tool has avoided so far) and for the Bandcamp
   lookup (search by parsed artist/album, confidence threshold, what happens
   on no match).

### Reconcile

1. **Make `reconcile`'s report interactive, the way `dedupe`'s per-group
   confirm walk replaced its single bulk prompt.** Today `reconcile` prints
   the whole table at once, and marking a row as a false absence means a
   separate `musictrack dismiss <source>:<ref>` call after the fact —
   two commands and a copy-pasted id instead of one pass. Walking the
   uncertain rows one at a time (the "worth a look" tier at least; the
   absent table plausibly too) and offering a dismiss right there would
   fold review and dismissal into a single interactive pass. Not scoped:
   whether the high-confidence "owned" rows need this at all, what unit
   walks (per-row vs per-tier), and how `--include-dismissed` and
   `--wants`/`--backlog` interact with a walk instead of a static table.

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
