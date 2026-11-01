from decimal import Decimal
import io
import itertools
import unittest

from record_delta.diff import FieldChange, differences
from record_delta.merge import reconcile
from record_delta.reader import InputError, MAX_LINE_BYTES, Record, records, validate_structure


def decode(text):
    return list(records(io.BytesIO(text.encode("utf-8"))))


class ReaderTests(unittest.TestCase):
    def test_empty_stream_and_line_endings(self):
        self.assertEqual(decode(""), [])
        self.assertEqual([record.id for record in decode('{"id":"a"}\r\n{"id":"b"}')], ["a", "b"])

    def test_exact_numbers_and_large_exponents(self):
        values = decode('{"id":"a","n":1.00000000000000000000001,"big":1e10000}\n')[0].data
        self.assertEqual(values["n"], Decimal("1.00000000000000000000001"))
        self.assertNotEqual(values["n"], Decimal(1))
        self.assertEqual(values["big"], Decimal("1e10000"))

    def test_portable_explicit_exponent_boundary(self):
        for spelling in ("1e1000000", "1e-1000000", "1e+0001000000", "1E" + "0" * 5000 + "1"):
            with self.subTest(spelling=spelling[:30]):
                self.assertEqual(decode('{"id":"a","n":' + spelling + '}')[0].data["n"], Decimal(spelling))
        for spelling in ("1e1000001", "1e-1000001", "1e" + "9" * 5000):
            with self.subTest(spelling=spelling[:30]), self.assertRaisesRegex(InputError, "exponent magnitude"):
                decode('{"id":"a","n":' + spelling + '}')

    def test_custom_key(self):
        output = list(records(io.BytesIO(b'{"sku":"a"}\n'), key="sku"))
        self.assertEqual(output[0].id, "a")

    def test_strict_schema_and_numbers(self):
        payloads = ['[]', '{}', '{"id":1}', '{"id":""}', '{"id":"a","id":"b"}',
                    '{"id":"a","x":{"n":1,"n":2}}', '{"id":"a","n":NaN}',
                    '{"id":"a","n":Infinity}', '{"id":"a","n":-Infinity}',
                    '{"id":"a","n":1e999999999999999999999999999}',
                    '{"id":"bad\\nkey"}', '{"id":"a","value":"\\ud800"}',
                    '{"id":"a","\\ud800":"value"}', '\n', '{', '\ufeff{"id":"a"}']
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(InputError):
                decode(payload)

    def test_rejects_invalid_utf8(self):
        with self.assertRaises(InputError):
            list(records(io.BytesIO(b'{"id":"\xff"}')))

    def test_sort_order_and_duplicates(self):
        for text in ('{"id":"b"}\n{"id":"a"}\n', '{"id":"a"}\n{"id":"a"}\n'):
            with self.assertRaisesRegex(InputError, "line 2.*strictly ascending"):
                decode(text)

    def test_unicode_order_and_valid_surrogate_pair(self):
        self.assertEqual([item.id for item in decode('{"id":"Z"}\n{"id":"a"}\n{"id":"é"}\n')], ["Z", "a", "é"])
        self.assertEqual(decode('{"id":"a","text":"\\ud83d\\ude00"}')[0].data["text"], "😀")

    def test_depth_boundary(self):
        value = "leaf"
        for _ in range(64):
            value = [value]
        validate_structure(value)
        with self.assertRaises(InputError):
            validate_structure([value])

    def test_oversized_line(self):
        with self.assertRaisesRegex(InputError, "line exceeds"):
            list(records(io.BytesIO(b" " * (MAX_LINE_BYTES + 1))))

    def test_bounded_read_and_lazy_decoding(self):
        class Bounded(io.BytesIO):
            def readline(self, limit=-1):
                self.asserted = limit
                if limit != MAX_LINE_BYTES + 1:
                    raise AssertionError("unbounded line read")
                return super().readline(limit)
        stream = Bounded(b'{"id":"a"}\ninvalid\n')
        iterator = records(stream)
        self.assertEqual(next(iterator).id, "a")
        self.assertEqual(stream.tell(), len(b'{"id":"a"}\n'))
        with self.assertRaises(InputError):
            next(iterator)


class DifferenceTests(unittest.TestCase):
    def test_json_pointer_escaping_and_empty_name(self):
        self.assertEqual(differences({"a/b~c": 1, "": 0}, {"a/b~c": 2, "": 1}),
                         (FieldChange("/", "changed"), FieldChange("/a~1b~0c", "changed")))

    def test_missing_null_and_container_replacement(self):
        self.assertEqual(differences({}, {"x": None}), (FieldChange("/x", "added"),))
        self.assertEqual(differences({"x": [1]}, {"x": {"0": 1}}), (FieldChange("/x", "changed"),))

    def test_arrays_are_positional(self):
        self.assertEqual(differences(["a", "b"], ["new", "a", "b"]),
                         (FieldChange("/0", "changed"), FieldChange("/1", "changed"), FieldChange("/2", "added")))

    def test_decimal_equivalence_and_boolean_distinction(self):
        self.assertEqual(differences(Decimal("1"), Decimal("1.00")), ())
        self.assertEqual(differences(Decimal("-0"), Decimal("0")), ())
        self.assertEqual(differences(True, Decimal("1")), (FieldChange("", "changed"),))

    def test_symmetry_for_small_json_values(self):
        values = [None, False, True, Decimal(0), Decimal(1), "", "x", [], [None], {}, {"a": None}, {"a/b~c": Decimal(1)}]
        inverse = {"added": "removed", "removed": "added", "changed": "changed"}
        for before, after in itertools.product(values, repeat=2):
            forward = differences(before, after)
            backward = differences(after, before)
            self.assertEqual([(item.pointer, inverse[item.kind]) for item in forward],
                             [(item.pointer, item.kind) for item in backward])


class MergeTests(unittest.TestCase):
    def test_exhaustive_membership_and_modification_cases(self):
        ids = "abcd"
        cases = 0
        for left_mask, right_mask, changed_mask in itertools.product(range(16), repeat=3):
            left_ids = {record_id for index, record_id in enumerate(ids) if left_mask & (1 << index)}
            right_ids = {record_id for index, record_id in enumerate(ids) if right_mask & (1 << index)}
            changed_ids = {record_id for index, record_id in enumerate(ids) if changed_mask & (1 << index)}
            before = [Record(record_id, {"id": record_id, "score": Decimal(0)}) for record_id in sorted(left_ids)]
            after = [Record(record_id, {"id": record_id, "score": Decimal(int(record_id in changed_ids))}) for record_id in sorted(right_ids)]
            actual = list(reconcile(before, after))
            expected = []
            for record_id in sorted(left_ids | right_ids):
                kind = ("added" if record_id not in left_ids else "removed" if record_id not in right_ids
                        else "modified" if record_id in changed_ids else "unchanged")
                expected.append((record_id, kind))
            with self.subTest(left=left_mask, right=right_mask, changed=changed_mask):
                self.assertEqual([(event.id, event.kind) for event in actual], expected)
                for event in actual:
                    self.assertEqual(event.fields, (FieldChange("/score", "changed"),) if event.kind == "modified" else ())
            cases += 1
        self.assertEqual(cases, 4096)

    def test_merge_is_lazy(self):
        consumed = [0, 0]
        def stream(side):
            for number in itertools.count():
                consumed[side] += 1
                record_id = f"{number:012d}"
                yield Record(record_id, {"id": record_id})
        events = list(itertools.islice(reconcile(stream(0), stream(1)), 3))
        self.assertEqual(len(events), 3)
        self.assertEqual(consumed, [3, 3])
