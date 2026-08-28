"""Юнит-тесты orchestrator/gates.py: политика гейтов из gates.yaml
(ADR-0007, tasks/T066/SPEC.md, требование 1).
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, gates  # noqa: E402


class GatesPolicyTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patcher = mock.patch.object(config, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, content: str) -> None:
        (self.root / "gates.yaml").write_text(content, encoding="utf-8")

    def test_auto_value_returns_auto(self):
        self.write("gates:\n  acceptance: auto\n")
        self.assertEqual(gates.policy("acceptance"), gates.AUTO)

    def test_manual_value_returns_manual(self):
        self.write("gates:\n  acceptance: manual\n")
        self.assertEqual(gates.policy("acceptance"), gates.MANUAL)

    def test_unknown_value_defaults_to_manual(self):
        self.write("gates:\n  acceptance: sometimes\n")
        self.assertEqual(gates.policy("acceptance"), gates.MANUAL)

    def test_missing_gate_key_defaults_to_manual(self):
        self.write("gates:\n  spec_gate: manual\n")
        self.assertEqual(gates.policy("acceptance"), gates.MANUAL)

    def test_missing_gates_section_defaults_to_manual(self):
        self.write("some_other_key: значение\n")
        self.assertEqual(gates.policy("acceptance"), gates.MANUAL)

    def test_missing_file_defaults_to_manual(self):
        self.assertFalse((self.root / "gates.yaml").exists())
        self.assertEqual(gates.policy("acceptance"), gates.MANUAL)

    def test_unreadable_yaml_defaults_to_manual(self):
        self.write("gates:\n  acceptance: [auto\n  не валидный YAML\n")
        self.assertEqual(gates.policy("acceptance"), gates.MANUAL)

    def test_gates_key_not_a_mapping_defaults_to_manual(self):
        self.write("gates: auto\n")
        self.assertEqual(gates.policy("acceptance"), gates.MANUAL)

    def test_each_gate_read_independently(self):
        self.write("gates:\n  spec_gate: auto\n  acceptance: manual\n"
                   "  merge_gate: auto\n")
        self.assertEqual(gates.policy("spec_gate"), gates.AUTO)
        self.assertEqual(gates.policy("acceptance"), gates.MANUAL)
        self.assertEqual(gates.policy("merge_gate"), gates.AUTO)


if __name__ == "__main__":
    unittest.main()
