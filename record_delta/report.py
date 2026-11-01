"""Deterministic report formatting and safe, no-overwrite publication."""

import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import TextIO

from .merge import Event


def event_line(event: Event, format: str) -> str:
    if format == "jsonl":
        return json.dumps(event.to_dict(), ensure_ascii=True, separators=(",", ":")) + "\n"
    text = f"{event.kind} {json.dumps(event.id, ensure_ascii=True)}"
    if event.fields:
        text += ": " + ", ".join(f"{field.kind} {json.dumps(field.pointer, ensure_ascii=True)}"
                                  for field in event.fields)
    return text + "\n"


def summary_line(counts: dict, format: str) -> str:
    summary = {"kind": "summary", **counts,
               "before_records": counts["removed"] + counts["modified"] + counts["unchanged"],
               "after_records": counts["added"] + counts["modified"] + counts["unchanged"]}
    if format == "jsonl":
        return json.dumps(summary, separators=(",", ":")) + "\n"
    return "summary: " + " ".join(f"{kind}={count}" for kind, count in counts.items()) + "\n"


def publish_new_file(source: TextIO, destination: Path) -> None:
    """Write a sibling temporary file, then atomically link it into a new name.

    A hard-link create never replaces an existing path, even if another process
    creates the destination after validation. Requires hard-link-capable storage.
    """
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         prefix=".record-delta-", dir=destination.parent,
                                         delete=False) as handle:
            temporary = Path(handle.name)
            shutil.copyfileobj(source, handle)
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
