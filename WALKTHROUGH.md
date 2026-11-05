# Walkthrough

This is the text version of the walkthrough (the README allows text instead of a recording).

## What the exercise is about

A scanner checks computer assets and writes down findings. It helps me to think of it as a
guard checking rooms in a building and writing down every broken thing he sees. The scan ran
twice: once in the "before" snapshot and once in the "after" snapshot.

The trap is this: when a finding is missing from the after list, that does not always mean it
was fixed. Maybe the second scan could not fully check that asset. The input tells us how well
each asset was checked the second time, in `after.coverage`:

- `complete`: the asset was fully checked again. A missing finding is really fixed, so resolved.
- `partial`: only part of the asset was checked. We cannot be sure, so unknown.
- `failed`: the scan of that asset crashed. We know nothing, so unknown.
- no entry at all: we know nothing, so unknown.

So my program puts every finding into one of five buckets: new, changed, unchanged, resolved,
unknown. It only says "resolved" when it has proof. That idea, not claiming more than the data
shows, is the main thing I learned from this exercise.

## How my program works

You run it like this:

```sh
python3 app.py --input inputs/primary.json --tenant north
```

Inside `app.py` the work happens in four steps:

1. `_validate_payload` checks the shape of the file (tenant, before.findings, after.findings,
   after.coverage) and that the selected tenant matches the input tenant. If not, exit 2.
2. `_load_findings` cleans each snapshot: it trims every string field, lowercases the severity,
   and checks that all five fields are nonempty strings and the severity is a known one. Findings
   from other tenants are just counted in `excluded_foreign_rows` and their values never show up
   anywhere. Two findings with the same identity (tenant, asset_id, rule_id, location) in the same
   snapshot are a duplicate, so the run fails with exit 2.
3. `_classify` applies the five bucket rules to every finding key, in sorted order, so repeated
   runs give the same output.
4. `_build_report` and `main` print one JSON document with entries, counts, excluded_foreign_rows
   and a readable report. The report is built from the same entries and counts, so they can never
   contradict each other. On any bad input the program prints one `error: ...` line to stderr and
   exits with code 2, never a traceback.

## One edge case in detail

My favorite case from inputs/primary.json is two findings that both disappear from the after
list, but get different answers:

- the key (north, api, tls, /) is gone, and api has coverage complete, so it is resolved
- the key (north, portal, debug, /debug) is gone, but portal only has coverage partial, so it
  is unknown

Same situation, two honest answers, and the only difference is coverage. The same file also
shows that a change in the evidence text alone (portal/leak goes from "old leak" to "fresh leak")
keeps the finding unchanged, because only the severity decides that.

One refinement I made while testing: duplicate detection has to run after trimming. If one row
has location " /login " with spaces and another has "/login", trimming makes them the same key,
so this must fail with exit 2 instead of silently merging. The test
`test_whenDuplicateKeyAppearsOnlyAfterTrimming_fails` locks that behavior in.

## Evidence of execution

All commands were run from the candidate folder.

The test suite, 20 tests, all passing:

```sh
$ python -m unittest discover -s tests -p "*_test.py" -v
...
Ran 20 tests in 3.9s
OK
```

The primary fixture gives exactly the counts the README asks for (exit code 0):

```sh
$ python app.py --input inputs/primary.json --tenant north
"counts": { "new": 1, "changed": 1, "unchanged": 1, "resolved": 1, "unknown": 1 },
"excluded_foreign_rows": 2
```

The secondary fixture works too: one unknown, zero resolved, because after.coverage is empty:

```sh
$ python app.py --input inputs/secondary.json --tenant north
"counts": { "new": 0, "changed": 0, "unchanged": 0, "resolved": 0, "unknown": 1 }
```

Broken inputs fail cleanly. Exit code 2, a readable one line error, nothing on stdout:

```sh
$ python app.py --input inputs/malformed-input.txt
error: Expecting ',' delimiter: line 2 column 1 (char 34)

$ python app.py --input broken.json
error: before.findings[0]: severity 'urgent' must be one of: critical, high, medium, low, info
```

## Known limits

- The tool is a standard library only CLI. No framework, no database, on purpose.
- Coverage status is matched exactly after trimming. Only severity is lowercased, because that
  is what the contract says.
- A finding row without a readable tenant cannot be scoped to any tenant, so I treat it as an
  invalid selected-tenant row (exit 2). This assumption is written down in the README.
