"""Local release-inventory and known-secret-pattern check; not a full audit."""

import ast
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "AGENTS.md",
    ".gitignore", ".github/workflows/ci.yml", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "record_delta/__init__.py", "record_delta/__main__.py", "record_delta/reader.py",
    "record_delta/diff.py", "record_delta/merge.py", "record_delta/report.py",
    "docs/architecture.md", "examples/before.jsonl", "examples/after.jsonl", "examples/unsorted.jsonl",
    "scripts/check_release.py", "scripts/check_python_decimal.py",
    "tests/test_core.py", "tests/test_cli.py", "tests/test_release.py",
}
IGNORED = {".git", "__pycache__", "out", ".venv"}
PATTERNS = {
    "GitHub credential": r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b",
    "cloud access key": r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    "private key": r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",
    "service credential": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b",
    "credential URL": r"https?://[^\s/@]+:[^\s/@]+@",
    "personal filesystem path": r"/(?:Users|home)/[A-Za-z0-9._-]+/",
    "assigned credential": r'''(?i)(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*["'][A-Za-z0-9_+/.=-]{12,}["']''',
}


def inspect_text(source: str) -> list[str]:
    return [name for name, pattern in PATTERNS.items() if re.search(pattern, source)]


def main() -> int:
    found, issues = set(), []
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if any(part in IGNORED for part in relative.parts):
            continue
        if path.is_symlink():
            issues.append(f"{relative}: symlink")
            continue
        if path.is_dir() or path.name == ".DS_Store":
            continue
        name = relative.as_posix()
        found.add(name)
        if name not in EXPECTED:
            issues.append(f"{name}: outside release inventory")
            continue
        if path.stat().st_size > 2_000_000:
            issues.append(f"{name}: unexpected size")
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeError:
            issues.append(f"{name}: non-text content")
            continue
        if "\x00" in source:
            issues.append(f"{name}: binary content")
        issues.extend(f"{name}: {label}" for label in inspect_text(source))
        if relative.parts[0] == "record_delta" and path.suffix == ".py":
            for node in ast.walk(ast.parse(source)):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [item.name.split(".")[0] for item in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    modules = [(node.module or "").split(".")[0]]
                for module in modules:
                    if module not in sys.stdlib_module_names or module in {"socket", "urllib", "http", "subprocess"}:
                        issues.append(f"{name}: import requires review: {module}")
    issues.extend(f"{name}: missing file" for name in sorted(EXPECTED - found))
    if issues:
        print("Release check failed; values redacted:\n" + "\n".join(issues))
        return 1
    print(f"PASS: {len(found)} inventoried text files; no matching credential or personal-path patterns.")
    print("PASS: runtime imports are local/standard-library modules without network/process imports.")
    print("Heuristic check only. Review provenance and staged files separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
