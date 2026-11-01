# Record Delta

**Compare two sorted JSON Lines exports without loading both datasets into memory.**

Record Delta finds added, removed, and modified records using a merge join.
For modified records it reports changed field paths, not the old/new field
values. Use it to check migration exports, fixture snapshots, or periodic data
dumps. It runs offline and never modifies the inputs or executes their contents.

Requires Python 3.11+ on macOS or Linux. Runtime and tests use only the standard
library: no package install, service, credentials, or network access is needed.

## Quickstart

From this folder:

```sh
python3 -m record_delta examples/before.jsonl examples/after.jsonl
python3 -m record_delta examples/before.jsonl examples/after.jsonl --format jsonl
python3 -m record_delta examples/before.jsonl examples/after.jsonl --summary-only
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
```

The first command prints:

```text
modified "acct-002": added "/features/1", changed "/plan"
removed "acct-003"
added "acct-004"
summary: added=1 removed=1 modified=1 unchanged=1
```

The examples are synthetic. The first record is unchanged despite different
object-key order and `1` versus `1.0`. The second changes a plan and appends an
array entry. One record disappears and another appears.

## CI checks and report files

```sh
# Exits 1 because these valid exports differ.
python3 -m record_delta examples/before.jsonl examples/after.jsonl --check

# Exits 0 because the two inputs are equal.
python3 -m record_delta examples/before.jsonl examples/before.jsonl --check

mkdir -p out
python3 -m record_delta examples/before.jsonl examples/after.jsonl --format jsonl --output out/changes.jsonl
```

Exit codes: **0** valid comparison (or equal inputs with `--check`); **1** valid
inputs differ and `--check` was requested; **2** invalid input or an I/O error.
Diagnostics go to stderr. JSONL output ends with a `kind: "summary"` record
containing the four change counts plus before/after record counts. Unchanged
records are counted but not emitted individually.

Both files are fully validated before any report reaches stdout or a destination
file. Reports exceeding a 1 MiB in-memory spool threshold spill to temporary
disk. `--output` creates a new file and refuses to replace an existing file,
symlink, or input path. It writes a sibling temporary file, then publishes it
with an atomic hard-link create. Use a new filename for subsequent runs.

Normal reports include **record IDs and field names**; they omit other field
values. Those identifiers can still be sensitive. `--summary-only` omits IDs
and paths and produces only counts. This is not an anonymization tool.

## Input contract

Each physical line is one JSON object, for example:

```json
{"id":"item-001","quantity":2,"metadata":{"region":"west"}}
```

- Inputs must already be sorted by a unique, top-level **string** key, default
  `id`. Use `--key sku` for another field name; it is a literal field name,
  not a nested path. Numeric IDs are not accepted.
- Order is Unicode code-point order, case-sensitive, without locale collation
  or Unicode normalization. For example, `"10"` sorts before `"2"`.
- Each key has 1–256 characters and no ASCII control characters. Missing,
  duplicate, and out-of-order keys are errors, including near end-of-file.
- UTF-8 only, without a byte-order mark. LF and CRLF are accepted; the final
  newline is optional. Empty files are valid. Blank lines are rejected.
- A physical line, including its line ending, is at most **1 MiB**. Structural
  nesting is capped at 64 levels, with the root at level zero.
- Duplicate object keys, unpaired Unicode surrogates, and nonstandard numeric
  constants such as `NaN` and `Infinity` are rejected. Explicit numeric exponent
  magnitude is capped at **1,000,000** before decimal parsing, keeping this limit
  consistent across Python builds.

The tool deliberately does not sort your exports. Automatic in-memory sorting
would defeat its streaming input design. Export or prepare data in the declared
key order first. `examples/unsorted.jsonl` demonstrates validation failure.

## Comparison semantics

| Situation | Result |
| --- | --- |
| Same object fields in a different order | Unchanged |
| JSON numbers `1`, `1.0`, `1e0` | Equal, using exact decimal parsing |
| Boolean `true` versus number `1` | Changed |
| Missing field versus explicit `null` | Added or removed field |
| Object replaced by array or scalar | One change at the container's path |
| Newly added or removed object subtree | One path for the whole subtree |
| Arrays | Compared by index; insertions can cause multiple changed paths |

Paths use [JSON Pointer escaping](https://www.rfc-editor.org/rfc/rfc6901): `~`
becomes `~0` and `/` becomes `~1` within a field name. Object fields are traversed
in sorted order; arrays in index order. Reports are deterministic for the same
decoded inputs. The output describes differences; it is **not JSON Patch** and
cannot reconstruct omitted values.

## Architecture, verification, and limits

See [architecture and tradeoffs](docs/architecture.md) for module boundaries,
memory/disk behavior, exact-number choices, and publication guarantees.

Tests cover **4,096 exhaustive membership/modification combinations**, structural
diff symmetry, pointer escaping, numeric precision, lazy consumption, invalid
input, output collision races, and failed-write cleanup. CI runs on Python
3.11 and 3.15. The release check scans the exact file inventory and known
credential/private-path patterns; it is a heuristic, not a comprehensive audit.

This is a focused export-comparison tool. It does not query databases, infer
schemas, align moved array entries, normalize Unicode, or perform fuzzy matching.
Large reports require temporary disk space. Inputs must remain unchanged during
the run; there is no cross-file snapshot lock. Hard-link-based output requires
a compatible filesystem and is not a guarantee of crash/power-loss durability.
No measured performance, production adoption, or authorship claims are implied.

Created with AI assistance in Codex. Original project files use the [MIT License](LICENSE).
See [dependency attribution and provenance](THIRD_PARTY_NOTICES.md).
