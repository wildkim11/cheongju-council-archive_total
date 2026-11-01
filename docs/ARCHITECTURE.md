# Archive architecture

## Source-of-truth rule

The archive stores source facts and provenance. Analytical classifications belong downstream.

## Council scopes

Every historical record must carry both:
- `council_scope`
- `term`

Initial council scopes:
- `cheongju_integrated`
- `cheongju_old_city`
- `cheongwon_old_county`

This prevents same-numbered historical terms from being conflated.

## Layers

```text
official sources
  -> raw source capture / source metadata
  -> normalized archive records
  -> indexes and coverage reports
  -> exports/analyzer
  -> downstream analyzer
```

## Meeting version policy

Meeting publication state is explicit:
- `provisional`: temporary minutes
- `published`: official/current minutes
- `superseded`: older version replaced by a newer official record

A provisional record is not deleted solely because a published record replaces it. The relationship is retained through `superseded_by` / `supersedes` where determinable.

Downstream analysis should prefer the current published version by default while preserving older versions for audit.

## Attachments

Large attachment binaries are not mirrored by default.

Store:
- title
- media/extension when known
- official URL
- official source identifier when available
- first_seen_at
- last_checked_at

## Member portraits

One official profile portrait per person may be mirrored for representative display. Preserve:
- source URL
- checked_at
- file hash
- local path

## Historical attributes

Party, district, committee, office and research/special-committee membership are temporal facts. They must be modeled with effective start/end dates or the narrowest supported period. Current affiliations must never be backfilled into older periods.
