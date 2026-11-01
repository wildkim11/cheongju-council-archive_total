# Historical member collection

Historical member collection is implemented with one adapter per council scope.

## Why adapters are separate

The official site exposes historical rosters through different page families:
- integrated council: combined historical-member page
- pre-integration Cheongju city: term-specific pages
- pre-integration Cheongwon county: separate source structure, to be activated only after verification

A single parser would risk silently mixing same-numbered terms.

## Identity policy

Historical roster rows are source facts.

Temporary archive person IDs are scope-aware. Cross-term or cross-scope identity merges must not be performed from name alone. A later identity-resolution step may connect records only when official evidence supports the match.

## Affiliation policy

Historical party, district and committee attributes are not inferred from current profiles. They are collected from period-specific official sources where available.
