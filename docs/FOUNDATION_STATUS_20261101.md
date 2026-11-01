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

## Verified current committee rosters

Live official-page verification:

- committee pages: **10**
- roster membership rows: **81**
- unresolved current-member names: **0**

Current homepage shortcut scope:
- 7 standing committees
- 2 special committees
- 1 personnel-hearing committee

The collector reads only the homepage `section.mCmt` current-committee shortcut block, not historical/side-menu committee links.

Roster roles are taken from the official committee-page `span.name` values:
- 위원장
- 부위원장
- 위원

Committee display whitespace is normalized only for type classification. Source labels are retained.

## Verified current research groups

Live official active-table verification for 2026:

- research groups: **5**
- membership rows: **65**
- representative rows: **5**
- unresolved current-member names: **0**

Current active table:
- 청주시 강호축 미래전략 연구회 — 22
- 도서관을 사랑하는 의원 모임 — 13
- 미래 정책 연구 포럼 — 7
- 청주공항 비상을 바라는 모임 — 12
- 청주시의회 문화·예술 연구회 — 11

The official HTML retains an older roster draft inside an HTML comment. It is ignored by the current-state collector. The commented draft remains a potential historical clue only and is not treated as current source truth.

## Historical committee strategy

Historical committee membership must come from dated official composition/recomposition records, not from backfilling current committee pages.

Initial verified source families include:
- standing-committee original composition records
- standing-committee latter-half recomposition records
- budget special committee composition records
- ethics special committee composition records
- later replacement / recomposition records where published

Effective dates are stored only when explicitly supported. Roster changes and substitutions must create new effective-period records instead of rewriting earlier source states.

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

1. historical committee source registry and effective-period roster collector
2. historical research-group source registry / roster collector
3. bill/resolution source collectors and full proposer rosters
4. source-candidate identity resolution layer
5. archive-to-analyzer export
6. only then initial full body/portrait population and scheduled incremental collection


## Verified official bill detail parsing

One-time live verification on the official bill-detail source succeeded on macOS runner.

Verified sample:
- internal number: `3492`
- bill number: `133`
- bill type: `결의안`
- proposal date: `2026-10-08`
- representative proposer: `최동식`
- co-proposers parsed: **51**
- full proposer roster parsed: **52**

The bill collector now supports:
- integrated council terms 1-4 list discovery
- official detail-page parsing
- bill number / type / proposal date / session / committee
- representative proposer(s)
- full co-proposer roster
- list processing result/date preservation
- institutional proposer labels excluded from person-name extraction

Bill proposer identity linkage is term-scoped:
- exact unique same-term member match -> `resolved_exact_term`
- multiple same-term candidates -> `ambiguous_same_term`
- no same-term candidate -> `unresolved`

No global name-only promotion is allowed.

## Historical research-group source discovery

A non-promoting discovery layer now scans:
- official annual research-group composition notices
- official annual research-activity report pages

Promotion to a research-group membership relation requires a full official participant roster.
Group-name-only notices remain source metadata only.
Large report attachments remain link-only by default.

## Identity candidate layer

The archive now emits a non-promoting identity candidate ledger.

Candidate evidence families:
- matching official `f_code`
- same normalized name across source records

Same-name matches are weak evidence and are never merged automatically.

## Analyzer export

The archive now exports source facts under `exports/analyzer/` as JSONL.

Current export families include:
- people
- tenures
- party memberships
- district memberships
- represented areas
- committee states and memberships
- research groups and memberships
- bills
- bill proposer memberships
- meetings
- identity candidates

The export explicitly excludes downstream analytical judgments such as Q codes, EVENT clusters, P1-P7 stages, rankings, scores, probabilities and predictions.


## Historical-state identity correction

Initial stage-A population exposed an important temporal identity case.

The official 2026-07-03 term-4 standing-committee composition includes 최영중 in 행정안전위원회. The member resigned on 2026-07-16, so the present-day active-member roster no longer contains that name.

Correction:
- historical committee states are resolved against the official roster for that council term;
- the current active roster is only a corroborating source for still-active term-4 members;
- a departed/resigned member is retained in earlier historical states when supported by the dated official source;
- current roster absence must not erase prior official membership.

This rule also applies to future resignations, deaths, replacements, by-elections and other mid-term roster changes.

Stage-A population is being retried after this correction.
