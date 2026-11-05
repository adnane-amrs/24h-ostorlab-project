# Run guide

You need Python 3.10 or newer and nothing else. All commands run from the `candidate/` folder.
On Windows use `python` instead of `python3`.

## Normal runs (exit code 0, JSON on stdout)

The primary fixture, with the acceptance numbers from the README:

```sh
python3 app.py --input inputs/primary.json --tenant north
```

Expected counts: new 1, changed 1, unchanged 1, resolved 1, unknown 1, and
`excluded_foreign_rows` 2. Some entries to look for in the output:

- key (north, api, auth, /login) is `changed`: severity goes high to critical
- key (north, api, tls, /) is `resolved`: it is gone from after and api has coverage complete
- key (north, portal, debug, /debug) is `unknown`: it is gone from after but portal coverage
  is only partial
- key (north, portal, leak, /export) is `unchanged`: same severity, only the evidence text changed
- key (north, api, headers, /) is `new`: it exists only in the after snapshot

The secondary fixture proves the feature is reusable with an empty after snapshot:

```sh
python3 app.py --input inputs/secondary.json --tenant north
```

Expected: exactly one entry, `unknown`, for key (north, api, auth, /login), zero resolved,
because `after.coverage` is empty.

## The tests

```sh
python3 -m unittest discover -s tests -p "*_test.py" -v
```

Expected result: `Ran 20 tests ... OK`. The suite covers: the counts of both supplied fixtures,
tenant isolation (foreign rows counted, values never exported), duplicate keys, unknown severity,
blank fields, bad or repeated coverage, missing sections, tenant mismatch, empty snapshots,
trimming and lowercasing, evidence-only changes, and identical output on repeated runs.

## Error runs (exit code 2, readable error on stderr, nothing on stdout)

Broken JSON file (deliberately truncated by the exercise):

```sh
python3 app.py --input inputs/malformed-input.txt
```

Expected: `error: Expecting ',' delimiter: ...`

File that does not exist:

```sh
python3 app.py --input inputs/does-not-exist.json
```

Expected: `error: [Errno 2] No such file or directory: ...`

Selected tenant does not match the tenant in the file:

```sh
python3 app.py --input inputs/primary.json --tenant south
```

Expected: `error: selected tenant 'south' does not match input tenant 'north'`

Valid JSON but invalid data (a finding with severity "urgent"):

```sh
python3 app.py --input broken.json
```

Expected: `error: before.findings[0]: severity 'urgent' must be one of: critical, high, medium, low, info`
(This uses a small local file I created for the manual check; it is not part of the submission.)
