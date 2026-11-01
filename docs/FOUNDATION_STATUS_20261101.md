# Foundation status — 2026-11-01

This document records verified collector behavior for the archive foundation branch.

## Branch policy

- Development branch: `feature/archive-foundation`
- `main` is not yet the archive production branch.
- Scheduled collection remains disabled.
- Live source probes are manual-only except when temporarily enabled for a single controlled verification.
- The existing repository `wildkim11/cheongju-council-minutes` is independent and must not be modified by this project.

## Verified official meeting inventory

Integrated council generation-root terms available:

- term 1
- term 2
- term 3
- term 4

Live inventory verification on macOS runner:

| term | official rows |
|---:|---:|
| 1 | 663 |
| 2 | 771 |
| 3 | 855 |
| 4 | 50 |
| **total** | **2,339** |

Publication state:
- published: **2,333**
- provisional: **6**

The archive retains provisional records and will preserve them as `superseded` when an official replacement is identified.

The official term/generation inventory is authoritative for term assignment.
The official year inventory is a coverage cross-check. A year-only row is not assigned a term by date inference.

## Verified current members

Live no-portrait verification:

- current members: **44**
- official portrait source URLs: **44**
- party rows: **44**
- district rows: **44**
- committee membership rows from the current member list: **53**

Current member identity uses official `f_code`.
The current roster also exposes `mcode`, retained as roster metadata.

## Verified integrated historical rosters

Terms 1-3 official historical search:
- roster rows: **123**
- tenure rows: **123**
- district rows: **122**
- historical `mcode` rows: **123**
- historical `f_code` rows: **0**

Historical `mcode` is scoped by `daesu` and is not treated as a cross-term stable person identifier.
Same-name historical rows are not automatically merged.

## Verified pre-integration Cheongju City rosters

| term | roster rows |
|---:|---:|
| 4 | 36 |
| 5 | 42 |
| 6 | 28 |
| 7 | 28 |
| 8 | 26 |
| 9 | 27 |
| **total** | **187** |

All 187 rows expose an official represented-area label on the static roster page.

## Verified pre-integration Cheongwon County rosters

| term | roster rows |
|---:|---:|
| 1 | 15 |
| 2 | 14 |
| 3 | 14 |
| 4 | 14 |
| 5 | 12 |
| 6 | 11 |
| **total** | **80** |

The static roster pages do not expose represented-area labels in the member list.

## Portrait policy

One official profile/roster portrait per source person record is eligible for mirroring.

Stored provenance:
- source URL
- local path
- checked timestamp
- SHA-256

Other large attachments are link-only by default.

## Network/runtime finding

The official minutes server timed out from `ubuntu-latest` during live verification.
The existing proven collector and successful new archive probes use `macos-14` for official-source network collection.

Unit-test CI may remain on Ubuntu because it does not contact the official source.

## Next foundation gates

1. current standing/special/other committee roster collector
2. historical committee roster and effective-period strategy
3. research-group roster collector
4. bill/resolution source collectors and full proposer rosters
5. source-candidate identity resolution layer
6. archive-to-analyzer export
7. only then initial full body/portrait population and scheduled incremental collection
