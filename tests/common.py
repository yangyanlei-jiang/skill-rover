import importlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def module(self, name):
        try:
            return importlib.import_module("skill_rover." + name)
        except ImportError as exc:
            self.fail("Missing implementation: " + str(exc))

    def skill(self, name="pdf-extract", extra="", body="Extract PDF tables."):
        path = self.base / ("source-" + name)
        path.mkdir(exist_ok=True)
        (path / "SKILL.md").write_text(
            "---\nname: " + name + "\ndescription: Extract PDF tables and text.\n" + extra + "---\n\n" + body,
            encoding="utf-8",
        )
        return path

