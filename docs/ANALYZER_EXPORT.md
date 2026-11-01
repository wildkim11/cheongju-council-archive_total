# Analyzer export

The archive exports source facts to `exports/analyzer/` as JSONL datasets.

The export is intentionally not the analytics engine.

Included source-fact families:
- people and tenure records
- temporal affiliation/membership ledgers
- committee states and memberships
- research groups and memberships
- bills and proposer memberships
- meetings
- identity-resolution candidates

Not included:
- Q classifications
- EVENT clusters
- P1-P7 progression
- policy-interest/style judgments
- rankings, scores, probabilities, or predictions

Identity candidates remain non-promoting until reviewed by a separate evidence-backed resolution process.
