# AI use note

As the README allows and encourages, I used an AI assistant (OpenCode with the GLM model) while
working on this exercise. I used it to generate practice exercises so I could test my
understanding of the classification rules before and while coding, to help implement the feature,
and to draft parts of these documents. This note describes one concrete output I accepted and how
I checked it.

## One accepted output and how I checked it

To practice before coding, I asked the assistant for exercises, and one of them was to classify
the findings of `inputs/primary.json` into the five buckets. My accepted example is the
assistant's trace of that fixture:

- (north, api, tls, /) is resolved, because the key exists only in before and api has coverage
  complete
- (north, portal, debug, /debug) is unknown, because the key exists only in before and portal
  has coverage partial
- (north, api, auth, /login) is changed (high to critical), (north, api, headers, /) is new,
  (north, portal, leak, /export) is unchanged (same severity, evidence text changed)
- the two south rows are excluded, so excluded_foreign_rows is 2

I did not accept it blindly. I checked it three ways:

1. Against the README, which states the primary counts must be new 1, changed 1, unchanged 1,
   resolved 1, unknown 1, with 2 foreign rows excluded. The trace matches.
2. Against my own program after implementation: the run produced exactly those counts.
3. Against the test suite: `testPrimary_classifiesAllFiveBucketsWithExpectedCounts` checks every
   entry by key, and `test_whenCoverageFailed_isUnknownNotResolved` confirms that only exactly
   complete coverage allows the resolved classification.

## What I corrected or rejected

During the same practice session I classified an evidence-only change as "changed" in my first
attempt. The practice discussion pointed back to the contract wording ("otherwise unchanged, even
when evidence text changes"): identity is the four-part key and only severity decides between
changed and unchanged. I verified this against the README and locked it in with the test
`test_whenOnlyEvidenceChanged_isUnchanged`.

## How I worked with AI overall

I used the assistant to generate practice exercises (classification scenarios and trace checks),
which I solved myself before and during implementation. The code was written with AI assistance,
but the logic was mine: I decided the approach (validate the input, scope to the selected tenant,
normalize and deduplicate the rows, classify with the five buckets, build the report from the same
data as the entries and counts), and the assistant helped me turn that plan into the Python
functions in app.py step by step. I reviewed every function, ran the tests myself, and every
behavior in the submission is backed by an executed test in tests/app_test.py. I take
responsibility for the submitted work.
