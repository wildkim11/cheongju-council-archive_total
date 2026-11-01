# Historical identity resolution

## Principle

Historical static member pages may provide a name, district label and portrait but no durable member code.

The archive must not silently merge people solely because their names match.

## Initial state

Rows without an official stable identifier are created with:
- `identity_status = candidate_unmerged`
- scope + term + name + source portrait fingerprint based candidate ID

This intentionally allows the same real person to exist as multiple source candidates across terms.

## Later resolution

A separate evidence-backed resolver may merge candidates only when supported by reliable combinations such as:
- official stable profile/member code
- exact official biography connecting terms
- matching official portrait plus corroborating district/career evidence
- explicit historical roster references

Every merge must preserve aliases/source candidate IDs and source evidence.

## Why

This prevents:
- same-name different people from being conflated
- present-day attributes from being backfilled historically
- inferred party/district history from becoming source fact
