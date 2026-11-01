"""A merge join over sorted record iterators; holds one lookahead from each."""

from dataclasses import dataclass
from typing import Iterable, Iterator

from .diff import FieldChange, differences
from .reader import Record


@dataclass(frozen=True)
class Event:
    kind: str
    id: str
    fields: tuple[FieldChange, ...] = ()

    def to_dict(self) -> dict:
        return {"kind": self.kind, "id": self.id,
                "fields": [field.to_dict() for field in self.fields]}


def reconcile(before: Iterable[Record], after: Iterable[Record]) -> Iterator[Event]:
    """Inputs must have strictly ascending unique IDs; reader.records checks this."""
    left, right = iter(before), iter(after)
    a, b = next(left, None), next(right, None)
    while a is not None or b is not None:
        if b is None or (a is not None and a.id < b.id):
            yield Event("removed", a.id)
            a = next(left, None)
        elif a is None or b.id < a.id:
            yield Event("added", b.id)
            b = next(right, None)
        else:
            changes = differences(a.data, b.data)
            yield Event("modified" if changes else "unchanged", a.id, changes)
            a, b = next(left, None), next(right, None)
