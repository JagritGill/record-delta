"""Strict JSONL decoding and sorted-key validation, one physical line at a time."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import BinaryIO, Iterator
import json

MAX_LINE_BYTES = 1_048_576
MAX_DEPTH = 64
MAX_ABS_EXPONENT = 1_000_000


class InputError(ValueError):
    """Invalid export; messages deliberately omit input values."""


@dataclass(frozen=True)
class Record:
    id: str
    data: dict


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate JSON object key")
        result[key] = value
    return result


def finite_number(token: str) -> Decimal:
    # Decimal backends differ in the largest exponent they accept. Enforce a
    # portable bound before constructing the number or converting a huge int.
    coefficient, marker, exponent = token.lower().partition("e")
    scale = 0
    if marker:
        magnitude = exponent.lstrip("+-").lstrip("0") or "0"
        if len(magnitude) > len(str(MAX_ABS_EXPONENT)) or int(magnitude) > MAX_ABS_EXPONENT:
            raise InputError(f"numeric exponent magnitude exceeds {MAX_ABS_EXPONENT}")
        scale = int(magnitude) * (-1 if exponent.startswith("-") else 1)
    sign = int(coefficient.startswith("-"))
    integral, _, fraction = coefficient.lstrip("-").partition(".")
    digits = tuple(ord(char) - ord("0") for char in integral + fraction)
    try:
        # The pure-Python string constructor converts the whole coefficient to
        # int, whose digit limit can differ across interpreters. The public
        # tuple constructor preserves the exact digits without that conversion.
        number = Decimal((sign, digits, scale - len(fraction)))
    except (InvalidOperation, ValueError) as exc:
        raise InputError("unsupported JSON number") from exc
    if not number.is_finite():
        raise InputError("JSON numbers must be finite")
    return number


def reject_constant(token: str) -> None:
    raise InputError("nonstandard JSON numeric constant")


def validate_structure(value: object) -> None:
    stack = [(value, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise InputError(f"nesting exceeds {MAX_DEPTH} levels")
        if isinstance(node, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in node):
                raise InputError("unpaired Unicode surrogate")
        elif isinstance(node, dict):
            stack.extend((key, depth + 1) for key in node)
            stack.extend((child, depth + 1) for child in node.values())
        elif isinstance(node, list):
            stack.extend((child, depth + 1) for child in node)


def records(handle: BinaryIO, *, key: str = "id", label: str = "input") -> Iterator[Record]:
    """Require ascending unique string IDs using Python Unicode code-point order."""
    if not isinstance(key, str) or not key or len(key) > 256:
        raise InputError("key must be a nonempty field name of at most 256 characters")
    previous = None
    line_number = 0
    while True:
        line = handle.readline(MAX_LINE_BYTES + 1)
        if not line:
            return
        line_number += 1
        try:
            if len(line) > MAX_LINE_BYTES:
                raise InputError(f"line exceeds {MAX_LINE_BYTES} bytes")
            if not line.strip():
                raise InputError("blank lines are not allowed")
            try:
                value = json.loads(line.decode("utf-8"), object_pairs_hook=unique_object,
                                   parse_int=finite_number, parse_float=finite_number,
                                   parse_constant=reject_constant)
            except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
                raise InputError("invalid UTF-8 JSON or excessive parser nesting") from exc
            if not isinstance(value, dict):
                raise InputError("each record must be a JSON object")
            validate_structure(value)
            record_id = value.get(key)
            if not isinstance(record_id, str) or not 1 <= len(record_id) <= 256:
                raise InputError("record key must be a string of 1 to 256 characters")
            if any(ord(char) < 32 or ord(char) == 127 for char in record_id):
                raise InputError("record key must not contain ASCII control characters")
            if previous is not None and record_id <= previous:
                raise InputError("record keys must be strictly ascending and unique")
            previous = record_id
            yield Record(record_id, value)
        except InputError as exc:
            raise InputError(f"{label}, line {line_number}: {exc}") from exc
