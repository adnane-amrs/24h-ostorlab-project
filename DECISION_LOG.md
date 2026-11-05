# Decision and work log

## Priorities: what I did first and what I deferred

My first priority was understanding the classification rules before writing any code. The
five buckets and the coverage rule are the heart of this exercise, and if I got those wrong
nothing else would matter. Then I built the core in this order: input validation, snapshot
loading and cleaning, classification, output and report. I wrote tests next to each part
instead of saving them for the end.

I deliberately deferred the stretch ideas (extra CLI options, fancier output) because the
scoring says a clear, tested core earns full marks, and my time was limited. The feature
stays a standard library CLI, no framework or database, because the README says that is
out of scope.

## One obstacle and how I responded

My biggest obstacle was conceptual, not technical. At first I thought "a finding is missing
from the after list" simply means "resolved". The coverage field breaks that logic: if the
second scan only partly checked the asset, the finding may still be there and we just did
not see it.

My response was to slow down and work the concept by hand before coding. I made small
examples, traced every finding into its bucket on paper, and only started implementing once
I could predict the expected counts for inputs/primary.json from memory. After that, writing
`_classify` felt almost mechanical, because the hard part was already understood.

## One validation that caused a refinement

While testing duplicates I realized that duplicate detection must run after normalization.
Example: one row with location " /login " (with spaces) and another with "/login", same asset
and rule. After trimming they are the same identity, so this must fail with exit 2 instead of
silently merging two rows. I added the test `test_whenDuplicateKeyAppearsOnlyAfterTrimming_fails`
to lock that in.

A second check that refined my thinking: portal/leak in primary.json keeps severity high in
both snapshots while the evidence text changes from "old leak" to "fresh leak". My first mental
draft treated any text change as a change. The contract says severity decides, so the correct
answer is unchanged, and `test_whenOnlyEvidenceChanged_isUnchanged` now proves it.

## Known limits and next step

- Coverage status is matched exactly after trimming; only severity is lowercased, because the
  contract mentions lowercasing only for severity.
- A finding row whose tenant cannot be read (missing, blank, or not a string) cannot be scoped
  to any tenant, so I treat it as an invalid selected-tenant row and fail with exit 2. This is
  my documented assumption, not a silent rule change.
- The report is plain text by design; there is no HTML or GUI output.

Next step if I had more time: I would add more combined cases to the test suite, for example
failed coverage together with foreign rows in both snapshots, and I would test tenant scoping
with a second tenant present in both snapshots at once. I kept the scope small on purpose to
protect the core.

## References I used as evidence

- inputs/primary.json: the five north keys (api/auth//login changed, api/headers// new,
  api/tls// resolved, portal/debug//debug unknown, portal/leak//export unchanged) and the two
  south rows counted in excluded_foreign_rows.
- inputs/secondary.json: one before-only key (north, api, auth, /login) with empty coverage,
  so one unknown and zero resolved.
- tests/app_test.py: 20 tests, all passing.
