"""Field-level structural differences; reports paths and change kinds, not values."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FieldChange:
    pointer: str
    kind: str

    def to_dict(self) -> dict:
        return asdict(self)


def child_pointer(parent: str, key: str) -> str:
    return parent + "/" + key.replace("~", "~0").replace("/", "~1")


def differences(before: object, after: object, pointer: str = "") -> tuple[FieldChange, ...]:
    if type(before) is not type(after):
        return (FieldChange(pointer, "changed"),)
    if isinstance(before, dict):
        changes = []
        for key in sorted(before.keys() | after.keys()):
            path = child_pointer(pointer, key)
            if key not in before:
                changes.append(FieldChange(path, "added"))
            elif key not in after:
                changes.append(FieldChange(path, "removed"))
            else:
                changes.extend(differences(before[key], after[key], path))
        return tuple(changes)
    if isinstance(before, list):
        changes = []
        for index in range(max(len(before), len(after))):
            path = child_pointer(pointer, str(index))
            if index >= len(before):
                changes.append(FieldChange(path, "added"))
            elif index >= len(after):
                changes.append(FieldChange(path, "removed"))
            else:
                changes.extend(differences(before[index], after[index], path))
        return tuple(changes)
    return () if before == after else (FieldChange(pointer, "changed"),)
