# Automatic collection on GitHub macOS

The production task is repository collection/processing, not HTML development.

`automatic-collection.yml` runs the original collectors on macOS. A thin copy
on `main` supplies the scheduled entry point; it checks out
`feature/archive-foundation` for the actual collector code and source archive.
The schedule rotates minutes, bills, activities, people, committee/research
groups, public media/photo metadata and document attachments. It does not infer
political scores or promote identity candidates.

Each run copies the archive to a disposable candidate, collects there, rebuilds
all analyzer JSONL exports, runs archive/hash QA, and only then installs the
candidate with the existing crash-recoverable transaction journal. Git commits
use an ordinary fast-forward push; concurrent branch changes fail rather than
being overwritten. The original live `run_sync` hard lock is retained.

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
