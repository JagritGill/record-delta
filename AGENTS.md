# Working in Record Delta

Offline reconciliation of sorted JSONL exports, reporting IDs and changed paths.
Read [README](README.md) for contracts and [architecture](docs/architecture.md)
for streaming, decimal, and publication tradeoffs. Preserve [MIT](LICENSE) and
[dependency/provenance notes](THIRD_PARTY_NOTICES.md).

## Map and invariants

| Location | Responsibility |
| --- | --- |
| `record_delta/reader.py` | Bounded JSONL reads, exact numeric parsing, schema/order validation |
| `record_delta/diff.py` | Structural changes and JSON Pointer escaping |
| `record_delta/merge.py` | Sorted merge join with one lookahead per input |
| `record_delta/report.py`, `record_delta/__main__.py` | Formatting, report spool, publication and CLI exits |
| `tests/test_core.py`, `tests/test_cli.py` | Merge/diff/reader tests and I/O behavior |
| `scripts/` | Release scan and isolated Python-decimal fallback tests |

- Inputs have strictly ascending unique string IDs in Unicode code-point order.
  Do not silently sort/normalize inputs or load both complete exports in memory.
  Drain both streams so late invalid/unmatched records cannot escape validation.
- Decode all JSON numbers as exact Decimal values. Preserve boolean/number
  distinction, exponent bounds, and long coefficients on both decimal backends.
  Avoid float conversion or whole-coefficient integer-string conversion.
- Reject duplicate object keys, unpaired surrogates, invalid UTF-8/BOM, excess
  nesting, and oversized physical lines, including their line endings.
- Arrays compare by index. Container replacement emits one changed path;
  added/removed subtrees emit one path. Escape `~` and `/` in JSON Pointers.
  Output is not JSON Patch and cannot reconstruct omitted field values.
- Fully validate both inputs before releasing the spooled report. Use a sibling
  temporary file and no-replace hard link for file publication; retain cleanup
  and collision handling. This requires compatible storage, not crash durability.
- Reports omit field values but expose IDs/field names. Summary-only omits both.
  Never use real private exports as fixtures; errors should not echo record values.

## Setup and verified commands

Run from the repository root on macOS/Linux with Python 3.11+. Standard library
only; no install, build, service, credentials, or configured static type checker.

```sh
python3 --version
python3 -m record_delta examples/before.jsonl examples/after.jsonl
python3 -m record_delta examples/before.jsonl examples/after.jsonl --format jsonl
python3 -m record_delta examples/before.jsonl examples/after.jsonl --summary-only
python3 -m record_delta examples/before.jsonl examples/before.jsonl --check
python3 -m unittest discover -s tests -v
python3 scripts/check_python_decimal.py
python3 scripts/check_release.py
git diff --check
```

These commands exit 0. The changed-export example counts one added, removed,
modified, and unchanged record. The equal-input check reports no differences.

```sh
python3 -m record_delta examples/before.jsonl examples/after.jsonl --check
python3 -m record_delta examples/unsorted.jsonl examples/after.jsonl
```

These intentionally exit 1 (valid differences) and 2 (invalid order). Invalid
input/I/O errors exit 2 with no partially validated report. Large spools require
temporary disk. See README for output-file commands; choose fresh paths in `out/`.

For fixes, reproduce the defect and add a meaningful regression. Preserve the
independent membership oracle, laziness tests, and failed-write/collision tests.
For numeric changes run the normal and decimal-fallback suites; the latter
changes only its own process, not installed Python settings. Exercise late
errors, Unicode/order, missing-vs-null, arrays, exact decimals, and line/depth
boundaries when relevant. Verify commands/links and release scans for doc edits.

## Ownership and handoff

Start with `git status --short --branch` and `git diff --stat`; preserve existing
edits and never stage/reset unrelated work. Origin is `JagritGill/record-delta`.
In the managed portfolio workspace, inspect parent `PROJECTS.md`/`BUILD_STATUS.md`
if present and coordinate with the current owner before overlapping tasks. Use
the connected Mac for Jagrit's work; report a disconnect instead of changing hosts.

Keep scope to this original repo and synthetic data; no private/employer source,
credentials, or personal paths. Put reports in ignored `out/`. Register new
intended files in the release inventory and keep scanning them; also review
provenance. No CodeRabbit or code sent to it; use local review/tests and existing CI.

Follow the request's action scope. Local edits do not authorize commits, pushes,
merges, releases, paid services, account/security changes, or hardware operations.
Do not bypass checks. Handoff lists changed files, exact commands/results,
environment, remaining limits, and unpublished state; separate current local
checks from historical CI and never claim a remote pass without observing it.
