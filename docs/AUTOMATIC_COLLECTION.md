# Automatic collection on GitHub macOS

The production task is repository collection/processing, not HTML development.

`automatic-collection.yml` runs the original collectors on macOS. A thin copy
on `main` supplies the scheduled entry point; it checks out
`feature/archive-foundation` for the actual collector code and source archive.
The daily 06:00 Asia/Seoul schedule runs all source families: minutes, bills,
activities, people, committee/research groups, public media/photo metadata and
document attachments. An hourly Ubuntu gate reads GitHub retry state only;
healthy sources do not start macOS or official-site requests. Due failures have
a maximum of three extra attempts per family per Korean calendar day. It does not infer
political scores or promote identity candidates.

Each run copies the archive to a disposable candidate, collects there, rebuilds
all analyzer JSONL exports, runs archive/hash QA, and only then installs the
candidate with the existing crash-recoverable transaction journal. Git commits
use a fast-forward push. Concurrent code-only changes can be rebased after the
full tests and archive QA pass again; concurrent source changes stop publication
rather than merging independently collected snapshots. The original live `run_sync` hard lock is retained.

The state in `reports/automatic/collection_state.json` records each source
family, attempts, errors, last success and next retry. Failure preserves the
old source archive; operational failure state is still committed. Missing
board items are retained, missing meetings must have recorded supersession,
and existing repaired bill rosters are held in a review queue when the current
official display differs. New records and recent/rotating details are checked.
Unchanged published minutes receive rotating body checks, not a false claim of
full body revalidation on every run.

Successful HTML source responses are retained as gzip-compressed, content
addressed UTF-8 decoded text with URL and SHA-256. They are not advertised as
HTTP wire bytes. Meeting bodies retain original official URLs and Markdown
hashes. Attachment downloads have a 20-document per-run budget and 8 MiB
per-file cap, official-host HTTPS checks and binary signature validation.
Oversize/unrecognized documents stay failed/pending in the queue; they are not
counted as downloaded. Photo images are still metadata only. Research/committee
source parsing failures remain visible and block that candidate.

For a manual family run:

```
python scripts/automated_collection.py --family minutes
```

Run all tests before changing the scheduled code:

```
python -m unittest discover -s tests
```

A workflow success is evidence for the selected family only. All-family
operational completion requires successful recorded collection for all seven
families. Meeting/text export into a downloadable HTML is a separate downstream
consumer and does not replace collection. This change does not publish HTML.

The immutable initial-term shards remain historical regression fixtures. Tests
for the old 2,339-record capture must not use the growing current index.

`export_minutes_text.py` is a downstream command-line producer for reproducible
plain-text gzip packs with official URLs and original/content hashes. The local
full-corpus trial verified 2,339 bodies: 217,884,901 UTF-8 text bytes and
58,516,198 compressed bytes. It is not an HTML build, and these large packs are
not committed by this change. The canonical Markdown sources already remain in
Git. Text-pack delivery can be added after collection operation is stable.

Initial activation uses `bootstrap`: run all source families that lack a
successful checkpoint within 24 hours. Each family is committed independently.
An individual source failure is recorded and does not prevent later families
from being attempted. Normal daily operations run the full source cycle; failed-only retries are separate.
A manual `all` performs a complete cycle without the bootstrap freshness skip.

Verified source candidates now also generate and validate speech/paragraph ranges
and source activity-role records before transaction publication. A separate
`process-archived-records.yml` job processes existing GitHub originals without
official-site access. It uses Ubuntu for offline computation; live collection
remains macOS. Derived records do not assert question/answer or policy scores.

## Recovery when macOS never starts (2026-11-04)

The source controller cannot record a failure when its macOS job ends before
its first step. Hourly gates therefore also inspect recent GitHub workflow/job
metadata. A completed failed workflow with a cancelled/failed/timed-out `collect`
job and **zero steps** is eligible for startup recovery within 24 hours of its
last update. This identifies a job that did not start; it does not establish
whether capacity, account limits or another infrastructure condition caused it.
Manual workflow cancellation and jobs with any started step are not classified
by this recovery rule.

The gate persists `reports/automatic/runner_recovery.json` **before** requesting
macOS. It reserves at most three startup retries per Korean calendar day, with
1/2/4-hour backoff after reservations. Failed allocations therefore consume the
budget even though no collector ran. Families with a saved success since the
failed workflow began are excluded. Controller-recorded source failures remain
under their existing backoff and daily budget. Replayed startup reservations
also skip families subsequently checkpointed or handed to source retry.

`main` runs a lightweight gate when this workflow file changes. Configuration
pushes never request a full cycle by themselves: collection starts only if the
bounded startup-failure recovery rule authorizes it. Normal daily collection
remains 06:00 Asia/Seoul. Hourly healthy checks make zero official-site requests.
Only GitHub Actions macOS performs official collection; the gate reads/writes
GitHub operational metadata and never contacts council hosts. The existing
shared concurrency group serializes gate reservation and snapshot publication.

Reservations and successful gates are **not** successful source checkpoints.
Operational coverage still requires each family's actual successful collection,
validation, publication and persisted `last_success_at`. This patch does not
claim successful collection of previously unverified families. A start failure
after any job step, a missing scheduled run, or a failure older than 24 hours
requires separate diagnosis; this recovery rule does not silently guess.

## Written-question link regression check (2026-11-04)

The recovered macOS activities cycle collected all 16 written-question records.
An independent HTMLParser-based audit matched both current-record question and
answer download links against the 16 preserved official detail responses, with
hash/size checks. Fourteen previously wrong answer record numbers changed; all
16 pairs now match. This confirms link provenance, not attachment binary contents.

`scripts/audit_written_question_links.py` consumes the latest durable activities
response manifest rather than the rotating latest-response pointer. Repeated
capture entries for the same URL/content are one proof, not independent sources.
Wrong question IDs, answer/question type mix-ups, duplicate query values,
external hosts, missing/ambiguous anchors, changed response hashes and unsafe
paths are held. macOS candidate validation rejects a HOLD report; offline
processing runs the same audit in strict mode. The source rows, dates and member
identity are not rewritten by this audit.
