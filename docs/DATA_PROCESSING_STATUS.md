# Data collection and processing status

## Execution policy

- Daily complete source cycle: 06:00 Asia/Seoul (GitHub scheduling may be delayed).
- Hourly Ubuntu gate reads only the GitHub collection state. It does not contact council sites or allocate a macOS collector for healthy sources.
- Only due failed families/documents are retried; maximum 3 extra attempts per family per Korean calendar day. Backoff starts at one hour and increases after repeated failures.
- Failed attachment retries select failed documents only; successful and new pending documents wait for the normal cycle. Daily collection still discovers new material.
- There is no automatic official-site collection on code push. Manual runs remain available.

## Implemented automatic processing

1. Existing official-site collectors preserve source records/meeting text and URLs.
2. The controller stores response provenance, versions, retries and checkpoints.
3. Bill-proposer roles are linked within the recorded term; institution-type name anomalies remain quarantined.
4. The existing exporter generates 24 normalized JSONL fact views and a row-count/SHA-256 manifest.
5. The staged snapshot passes schema/original-body/hash/export checks before transactional installation and Git publication.

These are fact extraction and integrity operations. They do not mean that all policy analysis engines are implemented.

## Further data and joins needed

| Need | Available starting point | Remaining work |
|---|---|---|
| Temporal identities | Person/tenure/profile records | Explicit service dates and historical party/district/committee intervals; resolve the remaining 645 activities; 30 gained exact full-body evidence links |
| Full relationship evidence | Bill rosters and membership records | 21 held cases, original signature lists, committee/research validity periods |
| Documents | Official attachment links and bounded document queue | Complete downloads, failed/oversized document handling, PDF/HWP/HWPX text extraction and origin links |
| Meeting speech segments | 2,353 canonical Markdown meetings after first automatic update | Basic speaker/role/paragraph segmentation implemented; answer/function classification and remaining identity review still required |
| Follow-up and policy progress | Replies in meetings and official bills | Extract existing replies; additionally register official action-result reports, budget decisions and project milestones as sources |
| Public media | Official press/photo metadata sources | Source coverage/deduplication; general media is a separate collection scope, not already complete |
| Detailed election results (user-approved plan, 2026-11-05) | NEC searches for 44 current-profile names; partial source-corroborated election links | Official district-wide candidate/results ledger, votes/share/rank/seats/margins and statistics; term/election/by-election and boundary versions; user-defined multi-sort, filters and comparisons. See ELECTION_RESULTS_PLAN_20261105.md. Planning only; detailed collection/UI not complete. |

## Processing progress and remaining engines

- Implemented evidence-level identity links: explicit tenure dates, source meeting term/role/roster links and exact full-body cross-source links; unresolved cases remain separate.
- Implemented shared source activity-role ledger for official speeches/questions and safe bill proposer roles. Distinct-event deduplication is still required.
- Implemented source speech/document/paragraph ranges, original URLs and hashes. Question/answer/function labels remain unclassified.
- Versioned policy taxonomy and Q/X/P/M rules; keep evidence states and uncertainty instead of promoting unsupported inference.
- Cross-session follow-up links and evidence-backed policy-progress stages.
- Person × space × policy × time aggregates with scope, period, denominator and missing-data coverage.
- Distribution bundles/text packs and offline-HTML updates after repository-side collection and processing are verified.

`export_minutes_text.py` is a tested producer for URL/hash-preserving compressed meeting text. Speech segmentation and the shared source activity-role ledger now run before collection publication and in a separate no-official-HTTP GitHub job. Binary-document text extraction, higher-level analysis and HTML embedding remain incomplete. See MEETING_PROCESSING.md.

## User-approved pledge plan — 2026-11-05

Register public-source discovery and original election pledge collection by member/term/election; provenance-preserving extraction, search, user-defined sorting/filtering and comparisons; joins to election results and legislative/budget/execution evidence. Separate original pledges, self-reported fulfillment and verified facts; missing evidence is not non-fulfillment. Full collection and fulfillment evaluation/UI remain unimplemented. See `PLEDGE_COLLECTION_PLAN_20261105.md`.

## Preserved NEC election observations — 2026-11-05

Offline ledger: 83 target events, 67 displayed vote/share observations, 16 absent; 30 linked events across the existing 19 corroborated profiles (26 winner displays, 4 candidacies without confirmed result). Review evidence for the remaining 25 profiles is preserved without promotion. Literal detail-menu contracts retained; live transport and full district result completeness remain unverified. No ranks/margins or exact seniority calculated. See `NEC_ELECTION_LEDGER_20261105.md`.

## Early-voting and count-unit sample originals — 2026-11-05

Captured six selection pages and three observed read-only report POSTs on macOS. Offline table ledger verifies 13 Sangdang early-voting facilities, four Cheongju-na candidates, and 19 counting-unit rows with ward/district arithmetic conservation. Official correction-row abstentions -49 preserved in that field only. Whole-city coverage, official seats/winners, member identities and physical polling-place vote links are not promoted. See `EARLY_VOTING_SOURCES_PLAN_20261105.md`.

## 2026 Cheongju four-committee election snapshot — 2026-11-05

Official district selectors reconcile to 14 observed districts. Snapshot includes 43 early-voting facilities across four committees, 64 regional candidates, 12 count reports/156 count rows with arithmetic conservation, and two explicit report-body uncontested statements. Actual new requests32/reused4/errors0. Source-backed regional table coverage is distinct from proportional/historical/seat/winner/seniority completeness. See `NEC_CITY_ELECTION_20261105.md`.
