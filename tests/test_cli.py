import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from record_delta.report import publish_new_file

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "record_delta", *map(str, args)], cwd=ROOT,
                              capture_output=True, text=True, check=False)

    def test_example_and_check_exit(self):
        result = self.cli("examples/before.jsonl", "examples/after.jsonl", "--check")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, 'modified "acct-002": added "/features/1", changed "/plan"\n'
                         'removed "acct-003"\nadded "acct-004"\n'
                         'summary: added=1 removed=1 modified=1 unchanged=1\n')

    def test_equal_input_check_exit(self):
        result = self.cli("examples/before.jsonl", "examples/before.jsonl", "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unchanged=3", result.stdout)

    def test_jsonl_deterministic_and_omits_values(self):
        args = ("examples/before.jsonl", "examples/after.jsonl", "--format", "jsonl")
        first, second = self.cli(*args), self.cli(*args)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        output = [json.loads(line) for line in first.stdout.splitlines()]
        self.assertEqual(output[-1], {"kind": "summary", "added": 1, "removed": 1, "modified": 1,
                                      "unchanged": 1, "before_records": 3, "after_records": 3})
        self.assertNotIn("starter", first.stdout)
        self.assertNotIn("audit", first.stdout)

    def test_summary_only_omits_ids_and_paths(self):
        result = self.cli("examples/before.jsonl", "examples/after.jsonl", "--summary-only", "--format", "jsonl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertNotIn("acct-", result.stdout)
        self.assertEqual(json.loads(result.stdout)["modified"], 1)

    def test_late_invalid_record_produces_no_partial_stdout(self):
        result = self.cli("examples/unsorted.jsonl", "examples/after.jsonl")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("before, line 2", result.stderr)
        self.assertNotIn("acct-", result.stderr)

    def test_validation_failure_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "report.jsonl"
            result = self.cli("examples/before.jsonl", "examples/unsorted.jsonl", "--output", destination)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_existing_output_and_input_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "records.jsonl"
            original = (ROOT / "examples/before.jsonl").read_bytes()
            target.write_bytes(original)
            result = self.cli(target, "examples/after.jsonl", "--output", target)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_new_output_is_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.jsonl"
            result = self.cli("examples/before.jsonl", "examples/after.jsonl", "--format", "jsonl", "--output", target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(target.read_text().splitlines()[-1])["kind"], "summary")
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_empty_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.jsonl"
            path.write_text("")
            result = self.cli(path, path, "--check", "--format", "jsonl")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["before_records"], 0)

    def test_report_larger_than_spool_threshold_is_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            before, after, target = (Path(directory) / name for name in ("before.jsonl", "after.jsonl", "report.jsonl"))
            before.write_text("")
            with after.open("w", encoding="utf-8") as handle:
                for index in range(6000):
                    record_id = f"item-{index:06d}-" + "x" * 220
                    handle.write(json.dumps({"id": record_id}) + "\n")
            result = self.cli(before, after, "--format", "jsonl", "--output", target, "--check")
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertGreater(target.stat().st_size, 1_048_576)
            lines = target.read_text().splitlines()
            self.assertEqual(len(lines), 6001)
            self.assertEqual(json.loads(lines[-1])["added"], 6000)
            self.assertEqual(json.loads(lines[0])["id"], "item-000000-" + "x" * 220)
            self.assertEqual(json.loads(lines[-2])["id"], "item-005999-" + "x" * 220)

    def test_missing_file_and_invalid_key(self):
        for args in (("missing.jsonl", "examples/after.jsonl"),
                     ("examples/before.jsonl", "examples/after.jsonl", "--key", "")):
            result = self.cli(*args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)


class PublicationTests(unittest.TestCase):
    def test_write_failure_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.txt"
            with patch("record_delta.report.shutil.copyfileobj", side_effect=OSError("synthetic disk failure")):
                with self.assertRaises(OSError):
                    publish_new_file(io.StringIO("report"), target)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_destination_created_during_write_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.txt"
            def competing_write(source, temporary):
                temporary.write(source.read())
                target.write_text("other writer")
            with patch("record_delta.report.shutil.copyfileobj", side_effect=competing_write):
                with self.assertRaises(FileExistsError):
                    publish_new_file(io.StringIO("our report"), target)
            self.assertEqual(target.read_text(), "other writer")
            self.assertEqual(list(Path(directory).iterdir()), [target])
