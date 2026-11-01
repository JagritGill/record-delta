"""Validate both exports before publishing a report or an exit status."""

import argparse
from pathlib import Path
import shutil
import sys
import tempfile

from .merge import reconcile
from .reader import records
from .report import event_line, publish_new_file, summary_line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare sorted JSONL exports offline; report paths, not field values.")
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--key", default="id", help="top-level unique string key (default: id)")
    parser.add_argument("--format", choices=("text", "jsonl"), default="text")
    parser.add_argument("--summary-only", action="store_true", help="omit record IDs and changed paths")
    parser.add_argument("--check", action="store_true", help="exit 1 when valid exports differ")
    parser.add_argument("--output", type=Path, help="create a new report file without overwriting")
    args = parser.parse_args(argv)
    counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}
    try:
        # Spill large reports to temporary disk; do not expose partial findings
        # if a malformed or unsorted record appears late in either export.
        with tempfile.SpooledTemporaryFile(mode="w+t", encoding="utf-8", newline="\n",
                                           max_size=1_048_576) as spool:
            with args.before.open("rb") as before, args.after.open("rb") as after:
                events = reconcile(records(before, key=args.key, label="before"),
                                   records(after, key=args.key, label="after"))
                for event in events:
                    counts[event.kind] += 1
                    if event.kind != "unchanged" and not args.summary_only:
                        spool.write(event_line(event, args.format))
            spool.write(summary_line(counts, args.format))
            spool.seek(0)
            if args.output:
                publish_new_file(spool, args.output)
                print(f"Wrote {args.output}", file=sys.stderr)
            else:
                shutil.copyfileobj(spool, sys.stdout)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1 if args.check and any(counts[kind] for kind in ("added", "removed", "modified")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
