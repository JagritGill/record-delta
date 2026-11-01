"""Run core tests against Python's standard-library decimal fallback in isolation.

Only this process disables the optional C accelerator. No installations or
interpreter settings are changed. CLI subprocess tests run in the main suite.
"""

from pathlib import Path
import sys

sys.modules["_decimal"] = None

import decimal
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    if decimal.Decimal.__new__.__module__ != "decimal":
        raise SystemExit("Expected the standard-library Python decimal backend")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_core.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
