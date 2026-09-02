"""Юнит-тесты `orchestrator.artel._parse_new_args` (tasks/T102/SPEC.md):
разбор argv команды `new` отклоняет нераспознанное ДО обращения к
`catalog.cmd_new` — на этом уровне без сандбокса/git, т.к. функция
только читает список аргументов и печатает/выходит."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel  # noqa: E402


class ParseNewArgsValidFormsTest(unittest.TestCase):

    def test_title_only_returns_title_and_no_tz(self):
        self.assertEqual(artel._parse_new_args(["Название"]),
                         ("Название", None))

    def test_title_with_tz_returns_both(self):
        self.assertEqual(
            artel._parse_new_args(["Название", "--tz", "путь.txt"]),
            ("Название", "путь.txt"))


class ParseNewArgsHelpTest(unittest.TestCase):

    def _run(self, rest: list) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = artel._parse_new_args(rest)
        self.assertIsNone(result, "help-путь не должен возвращать (title, tz)")
        return buf.getvalue()

    def test_empty_rest_prints_usage(self):
        self.assertIn('new "<название>"', self._run([]))

    def test_long_help_flag_prints_usage(self):
        self.assertIn('new "<название>"', self._run(["--help"]))

    def test_short_help_flag_prints_usage(self):
        self.assertIn('new "<название>"', self._run(["-h"]))


class ParseNewArgsRejectsUnrecognizedTest(unittest.TestCase):

    def test_extra_positional_argument_exits_naming_it(self):
        with self.assertRaises(SystemExit) as ctx:
            artel._parse_new_args(["Название", "лишнее"])
        self.assertIn("лишнее", str(ctx.exception))
        self.assertIn('new "<название>"', str(ctx.exception))

    def test_unknown_flag_exits_naming_it(self):
        with self.assertRaises(SystemExit) as ctx:
            artel._parse_new_args(["Название", "--unknown"])
        self.assertIn("--unknown", str(ctx.exception))
        self.assertIn('new "<название>"', str(ctx.exception))

    def test_dash_prefixed_title_exits_naming_it(self):
        with self.assertRaises(SystemExit) as ctx:
            artel._parse_new_args(["-x"])
        self.assertIn("-x", str(ctx.exception))
        self.assertIn('new "<название>"', str(ctx.exception))

    def test_dangling_tz_flag_still_exits_via_tz_arg(self):
        with self.assertRaises(SystemExit) as ctx:
            artel._parse_new_args(["Название", "--tz"])
        self.assertIn("--tz", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
