"""Юнит-тесты `orchestrator.artel._parse_new_args` (tasks/T102/SPEC.md):
разбор argv команды `new` отклоняет нераспознанное ДО обращения к
`catalog.cmd_new` — на этом уровне без сандбокса/git, т.к. функция
только читает список аргументов и печатает/выходит.

`_cmd_canary` (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW, требование 2) — та же
идея для подкоманды `canary`: `pool-seal` не должна обращаться к `--k`
вовсе."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

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


class CmdCanaryDispatchTest(unittest.TestCase):
    """`artel._cmd_canary` — маршрутизация `canary pool-seal` до
    `cmd_pool_seal` БЕЗ разбора `--k` (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW,
    требование 2), `canary --k N` — до `cmd_canary` как раньше."""

    def test_pool_seal_routes_to_pool_seal_without_k_arg(self):
        """Ловит мутацию: `pool-seal` падает в общую ветку разбора `--k`
        (например, пытается распарсить `--k` из отсутствующих
        аргументов) вместо прямого вызова `cmd_pool_seal` — либо
        `cmd_canary` был бы вызван вместо/вместе с `cmd_pool_seal`."""
        with mock.patch.object(artel.canary, "cmd_pool_seal") as seal_mock:
            with mock.patch.object(artel.canary, "cmd_canary") as run_mock:
                artel._cmd_canary(["pool-seal"])
        seal_mock.assert_called_once_with()
        run_mock.assert_not_called()

    def test_k_flag_routes_to_the_run_command(self):
        """Ловит мутацию: `--k` ошибочно маршрутизируется в
        `cmd_pool_seal` (регресс существовавшего до этой задачи
        поведения `canary --k N`) — `run_mock` не получил бы вызова с
        разобранным `k=3`."""
        with mock.patch.object(artel.canary, "cmd_pool_seal") as seal_mock:
            with mock.patch.object(artel.canary, "cmd_canary") as run_mock:
                artel._cmd_canary(["--k", "3"])
        run_mock.assert_called_once_with(k=3, sha=None)
        seal_mock.assert_not_called()

    def test_k_flag_with_explicit_sha_passes_it_through(self):
        """SPEC 01M2B6K02YVJBWE1JDWP85EJH0, требование 1/AC-2: `--sha
        <sha>` разобран и передан `cmd_canary` как есть.

        Ловит мутацию: `_sha_arg` не читается вовсе (значение `sha`
        всегда `None`) — явный `--sha` терялся бы, целевой sha прогона
        всегда вычислялся бы по умолчанию из `origin`."""
        with mock.patch.object(artel.canary, "cmd_canary") as run_mock:
            artel._cmd_canary(["--k", "3", "--sha", "abc123"])
        run_mock.assert_called_once_with(k=3, sha="abc123")


if __name__ == "__main__":
    unittest.main()
