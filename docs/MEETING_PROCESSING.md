# Evidence-preserving meeting processing

This repository now produces source-coordinate speech segments and a shared
activity-role ledger from preserved originals. Official website collection stays
on macOS. Offline processing can run independently on GitHub Ubuntu; it makes
zero requests to council websites. The normal daily collection controller also
processes and verifies its candidate before transactional publication.

## Inputs and outputs

Inputs: canonical meeting index and original Markdown; SHA-256-verified analyzer
exports for people, tenures, bills, the member-only proposer view, five-minute
speeches, city questions and written questions.

Outputs under `exports/processing/`:
- `manifest.json`: input fingerprints, processing code hash, coverage and limits.
- `meeting_segments_catalog.json`: one entry for each canonical meeting.
- `segments/*.json.gz`: per-meeting role/paragraph ranges with official URL and
  original source hash. Source text is referenced, not duplicated in each turn.
- `activity_roles.jsonl.gz`: source items and person roles across official
  speeches/questions and safe member-proposed bills.

Each source segment has exact character offsets into the UTF-8-decoded archived
Markdown, exclusive end offsets, inclusive 1-based line ranges, paragraph IDs
and paragraph hashes. Preambles, attendance lists, documentary notices and
unparsed circle markers are retained as separate ranges. The entire original
body is covered without silently attributing an attendance list to the preceding
speaker.

## Identity evidence levels

1. `resolved_explicit_tenure`: an exact name has a unique explicitly dated
   same-council tenure that covers the source date. Exact interval verification
   is separate from inferred term limits.
2. `resolved_source_meeting_term`: an explicit council-speaker role/name in a
   hash-verified official meeting matches exactly one person in the official
   roster of the same council and term. The meeting's term/date are source
   metadata. This identifies the speaker within that term; it does not verify
   the person's full tenure interval or merge identities across terms.
3. Other same-name or ambiguous cases remain candidates. Executive/staff and
   external-role labels are not mapped to an identically named council member.
4. Activities lacking a recorded term can additionally link when the complete
   visible activity body (at least 80 normalized characters) is an exact
   whitespace-normalized substring of one source speech on the same date by
   the same named speaker. Multiple matches or conflicting dated identities
   are not arbitrarily resolved. No fuzzy title/keyword matching is used.
5. Bill identities retain the preexisting safe exact-term proposer link and its
   separate `term_only_not_exact_dates` temporal qualification. Institutional
   name anomalies are excluded from the safe source view.

## Validation and caching

`verify_processing.py` checks original and derived hashes, corpus coverage,
character/line ranges, paragraph hashes, role fields against original headers,
activity source row references and every exact full-body cross-source link.
The per-meeting signature includes original hash, parser code hash and relevant
identity fields. Unchanged shards are reused; corrupt caches are rebuilt only
from verified originals. Checked-at timestamp changes do not by themselves
change identity semantics.

Run locally or in GitHub:

```
python scripts/process_meeting_segments.py
python scripts/verify_processing.py --out reports/processing-qa-latest.json
```

## Measured current snapshot

Local full-corpus verification: 2,353 meetings; 664,179 total ranges;
647,816 speech ranges; 872,589 paragraphs; 12,084 activity-role rows.
The role ledger includes 11,377 proposer-person rows, not 11,377 distinct bills.
Thirty previously unresolved official activities link through exact full-body
source evidence; 645 activity identities remain unresolved. There are 2,334
unparsed source markers, preserved for review rather than discarded.

These are source record/range counts. Speeches are explicitly
`speech_function=unclassified`, not automatically substantive questions,
answers, collaborations, achievements or policy-progress stages.
Cross-source event deduplication, Q/X/P/M policy analysis and follow-up
judgments remain incomplete. Full historical party/district/committee intervals,
held original signature evidence and uncollected document text are still needed.
