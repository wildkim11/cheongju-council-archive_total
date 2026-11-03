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
| Temporal identities | Person/tenure/profile records | Explicit service dates and historical party/district/committee intervals; resolve 675 previously unlinked activities with direct evidence |
| Full relationship evidence | Bill rosters and membership records | 21 held cases, original signature lists, committee/research validity periods |
| Documents | Official attachment links and bounded document queue | Complete downloads, failed/oversized document handling, PDF/HWP/HWPX text extraction and origin links |
| Meeting speech segments | 2,353 canonical Markdown meetings after first automatic update | Speaker/role segmentation, answer blocks, paragraph IDs and person linkage |
| Follow-up and policy progress | Replies in meetings and official bills | Extract existing replies; additionally register official action-result reports, budget decisions and project milestones as sources |
| Public media | Official press/photo metadata sources | Source coverage/deduplication; general media is a separate collection scope, not already complete |

## Processing engines still required

- Verified person × term × date joins, with unresolved/ambiguous rows retained separately.
- Shared activity-role ledger across speeches, questions, bills and official activities; deduplicate source copies without collapsing different events.
- Speech/question/answer/evidence segment ledger; point every result back to meeting ID, paragraph and official URL.
- Versioned policy taxonomy and Q/X/P/M rules; keep evidence states and uncertainty instead of promoting unsupported inference.
- Cross-session follow-up links and evidence-backed policy-progress stages.
- Person × space × policy × time aggregates with scope, period, denominator and missing-data coverage.
- Distribution bundles/text packs and offline-HTML updates after repository-side collection and processing are verified.

`export_minutes_text.py` is a tested producer for URL/hash-preserving compressed meeting text. Automated text extraction of document binaries, full analysis-ledger generation and HTML embedding are not yet connected to the production controller.
