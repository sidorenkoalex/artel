"""`lease.run_task_command` — одна обвязка «префикс id + блокировка задачи»
вместо семи копий в командах (SPEC 01M5MHVRS39CDP5V4HBWY4K7WK,
требование 4: проверки (а)-(г))."""
import ast
import inspect
import os
import socket
import sqlite3
import textwrap
import unittest
from datetime import datetime, timezone
from unittest import mock

from orchestrator import (answer, ci_rerun, config, fsm, lease, liveness,
                          pull_main, runner, store, workspace)
from tests.sandbox import InitializedTmpRootTest

FULL = "01M5ZZTESTAAAAAAAAAAAAAAAA"
DECOY = "01M5ZZTESTBBBBBBBBBBBBBBBB"
PREFIX = "01M5ZZTESTA"

# (модуль, команда, тело, добавочные аргументы команды до `session_id`,
# добавочные аргументы после него, ожидаемые добавочные аргументы тела).
COMMANDS = (
    (fsm, "cmd_spec_audit", "_cmd_spec_audit", (), (), ()),
    (fsm, "cmd_reject", "_cmd_reject", ("причина",), (), ("причина",)),
    (pull_main, "cmd_pull_main", "_cmd_pull_main", (), (), ()),
    (workspace, "cmd_workspace", "_cmd_workspace", (), (), ()),
    (ci_rerun, "cmd_ci_rerun", "_cmd_ci_rerun", ("флейк",), (), ("флейк",)),
    (runner, "cmd_run", "_cmd_run", (), (), ()),
    (answer, "cmd_zones_extend", "_cmd_zones_extend", ("a/, b/",),
     ("matrix.md",), ("a/, b/", "matrix.md")),
)


def dotted(node) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


class FrozenDatetime(datetime):
    frozen = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.frozen if tz is None else cls.frozen.astimezone(tz)


class PrefixSandbox(InitializedTmpRootTest):
    """Задача FULL и сосед DECOY с общим началом id: PREFIX уникален для
    FULL, но разворачивается именно поиском по префиксу."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        for task_id in (FULL, DECOY):
            store.insert_task(self.conn, task_id, "Задача", "in_dev",
                              f"task/{task_id.lower()}-x",
                              config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)


class RunTaskCommandTest(PrefixSandbox):

    def test_body_gets_connection_and_full_id_run_locked_gets_full_id(self):
        """(а) Тело получает (соединение, полный id); `run_locked` — полный id.

        `lease.run_locked` обёрнут шпионом с пропуском к настоящему.
        Ловит мутацию: `run_task_command` отдаёт телу или `run_locked`
        неразвёрнутый префикс, теряет возврат тела либо передаёт в
        `run_locked` именованные `on_refusal`/`same_host_ok`/`force`.
        """
        result = object()
        body = mock.Mock(return_value=result)
        with mock.patch.object(lease, "run_locked",
                               wraps=lease.run_locked) as spy:
            got = lease.run_task_command(PREFIX, "sess-a", body)
        self.assertIs(got, result)
        body.assert_called_once()
        args, kwargs = body.call_args
        self.assertEqual(kwargs, {})
        self.assertEqual(len(args), 2)
        self.assertIsInstance(args[0], sqlite3.Connection)
        self.assertEqual(args[1], FULL)
        spy.assert_called_once()
        spy_args, spy_kwargs = spy.call_args
        self.assertEqual(spy_args[1], FULL)
        self.assertEqual(spy_args[2], "sess-a")
        self.assertEqual(spy_kwargs, {})

    def test_foreign_live_lease_refusal_matches_acquire_text(self):
        """(б) Чужой живой lease этой машины: `SystemExit` с текстом эталона.

        Lease FULL — на чужой сессии с живым pid родителя и этой машиной;
        часы `liveness` остановлены, возраст heartbeat одинаков для эталона
        `lease.acquire(conn, FULL, "sess-x")` и вызова с префиксом.
        Ловит мутацию: префикс разворачивается после взятия lease (отказ
        несёт префикс, а не полный id) либо обвязка зовёт `run_locked` с
        `same_host_ok=True` (чужой lease этой машины пропущен, тело вызвано).
        """
        heartbeat = FrozenDatetime.frozen.strftime("%Y-%m-%d %H:%M:%SZ")
        store.insert_lease(self.conn, FULL, "sess-holder", os.getppid(),
                           socket.gethostname(), heartbeat)
        before = dict(store.lease_row(self.conn, FULL))
        body = mock.Mock()
        with mock.patch.object(liveness, "datetime", FrozenDatetime):
            reference, _fresh = lease.acquire(self.conn, FULL, "sess-x")
            self.assertIsNotNone(reference)
            with self.assertRaises(SystemExit) as cm:
                lease.run_task_command(PREFIX, "sess-x", body)
        self.assertIn(FULL, reference)
        self.assertEqual(cm.exception.code, reference)
        body.assert_not_called()
        self.assertEqual(dict(store.lease_row(self.conn, FULL)), before)


class CommandsLintTest(unittest.TestCase):

    def test_commands_delegate_to_run_task_command(self):
        """(в) Линтер AST семи команд: обвязка — только `lease.run_task_command`.

        В теле команды нет `store.db`, `store.resolve_task_id`,
        `lease.run_locked`; есть один вызов `lease.run_task_command` со
        вторым позиционным аргументом `session_id`; в лямбде третьего
        аргумента id задачи в вызове `_cmd_*` — параметр лямбды.
        Ловит мутацию: в команде возвращена своя копия обвязки или потерян `session_id`.
        """
        for module, name, _body, _pre, _post, _extra in COMMANDS:
            with self.subTest(command=name):
                func = ast.parse(textwrap.dedent(
                    inspect.getsource(getattr(module, name)))).body[0]
                calls = [n for n in ast.walk(func) if isinstance(n, ast.Call)]
                names = [dotted(c.func) for c in calls]
                for banned in ("store.db", "store.resolve_task_id",
                               "lease.run_locked"):
                    self.assertNotIn(banned, names, f"{name}: {banned}")
                wrapped = [c for c in calls
                           if dotted(c.func) == "lease.run_task_command"]
                self.assertEqual(len(wrapped), 1, name)
                args = wrapped[0].args
                self.assertGreaterEqual(len(args), 3, name)
                self.assertIsInstance(args[1], ast.Name, name)
                self.assertEqual(args[1].id, "session_id", name)
                if isinstance(args[2], ast.Lambda):
                    params = {a.arg for a in args[2].args.args}
                    inner = [c for c in ast.walk(args[2].body)
                             if isinstance(c, ast.Call)
                             and dotted(c.func).split(".")[-1].startswith("_cmd_")]
                    self.assertTrue(inner, name)
                    for c in inner:
                        self.assertIsInstance(c.args[1], ast.Name, name)
                        self.assertIn(c.args[1].id, params, name)


class CommandsReachBodyTest(PrefixSandbox):

    def test_each_command_reaches_body_with_full_id(self):
        """(г) Каждая из семи команд с префиксом доходит до `_cmd_*` с полным id.

        Тело подменено `mock.patch.object(<модуль>, "_cmd_…")`,
        `run_task_command` и `run_locked` настоящие.
        Ловит мутацию: лямбда команды передаёт в `_cmd_*` неразвёрнутый
        `task_id` внешней функции или теряет добавочные аргументы
        (`reason`, `paths_arg`, `matrix_path`); `cmd_run` не возвращает
        результат обвязки.
        """
        for module, name, body_name, pre, post, extra in COMMANDS:
            with self.subTest(command=name):
                result = object()
                with mock.patch.object(module, body_name,
                                       return_value=result) as spy:
                    got = getattr(module, name)(PREFIX, *pre, "sess-g", *post)
                spy.assert_called_once()
                args, kwargs = spy.call_args
                self.assertEqual(kwargs, {})
                self.assertIsInstance(args[0], sqlite3.Connection)
                self.assertEqual(args[1:], (FULL, *extra))
                if name == "cmd_run":
                    self.assertIs(got, result)
                self.assertIsNone(store.lease_row(store.db(), FULL),
                                  f"{name}: lease не снят после тела")


if __name__ == "__main__":
    unittest.main()
