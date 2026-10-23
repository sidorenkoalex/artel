"""Обвязка «префикс id задачи + блокировка задачи» команд — `lease.run_task_command`.

Группа: долгоживущий
Красен до реализации: функции lease.run_task_command ещё нет (AttributeError), семь команд ещё несут свою копию обвязки store.db/resolve_task_id/run_locked; сигнатуры команд (AC-6) уже соблюдены.

Ид задач порождаются при каждом запуске модулем `random`; зерно печатается
и входит в текст провала.
"""
import ast
import inspect
import os
import random
import socket
import sqlite3
import textwrap
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from orchestrator import (answer, ci_rerun, config, fsm, lease, liveness,
                          pull_main, runner, store, workspace)
from tests.sandbox import InitializedTmpRootTest

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Семь команд таблицы SPEC: (модуль, имя, ожидаемые первые параметры
# сигнатуры с умолчаниями; `inspect.Parameter.empty` — без умолчания).
EMPTY = inspect.Parameter.empty
COMMANDS = (
    (fsm, "cmd_spec_audit", (("task_id", EMPTY), ("session_id", None))),
    (fsm, "cmd_reject", (("task_id", EMPTY), ("reason", EMPTY),
                         ("session_id", None))),
    (pull_main, "cmd_pull_main", (("task_id", EMPTY), ("session_id", None))),
    (workspace, "cmd_workspace", (("task_id", EMPTY), ("session_id", None))),
    (ci_rerun, "cmd_ci_rerun", (("task_id", EMPTY), ("reason", EMPTY),
                                ("session_id", None))),
    (runner, "cmd_run", (("task_id", EMPTY), ("session_id", None))),
    (answer, "cmd_zones_extend", (("task_id", EMPTY), ("paths_arg", EMPTY),
                                  ("session_id", None),
                                  ("matrix_path", None))),
)


def dotted(node) -> str:
    """`a.b.c` вызова -> строка; иное — пустая строка."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


class FrozenDatetime(datetime):
    """`datetime` модуля `liveness` с остановленными часами: возраст
    heartbeat одинаков для эталона и проверяемого вызова."""

    frozen = None

    @classmethod
    def now(cls, tz=None):
        return cls.frozen if tz is None else cls.frozen.astimezone(tz)


class PrefixTaskSandbox(InitializedTmpRootTest):
    """Песочница с задачами, чьи id порождаются случайно: у целевой задачи
    есть «сосед» с общим началом id, поэтому префикс разворачивается
    именно поиском по префиксу, а не точным совпадением."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()

    def seed_task(self) -> tuple[str, str]:
        """(полный id, уникальный префикс) новой задачи в песочнице."""
        rng = self.rng
        while True:
            full = "".join(rng.choice(ULID_ALPHABET) for _ in range(26))
            shared = rng.randint(2, 8)
            other = rng.choice([c for c in ULID_ALPHABET if c != full[shared]])
            decoy = (full[:shared] + other
                     + "".join(rng.choice(ULID_ALPHABET) for _ in range(25 - shared)))
            if store.task_id_matches(self.conn, full[:shared]):
                continue
            break
        for task_id in (full, decoy):
            store.insert_task(self.conn, task_id, "Задача", "in_dev",
                              f"task/{task_id.lower()}-x",
                              config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        prefix = full[:shared + 1 + rng.randint(0, 4)]
        return full, prefix

    def msg(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"


class RunTaskCommandTest(PrefixTaskSandbox):
    """Связка `run_task_command` — `store.resolve_task_id` — `run_locked` —
    `acquire` — БД песочницы; настоящие все звенья, кроме тела команды."""

    def test_ac1_body_gets_connection_and_full_id_and_result_is_returned(self):
        """Префикс существующей задачи -> тело получает (соединение, полный id).

        На нескольких случайных задачах с соседом по префиксу вызывается
        `lease.run_task_command(<префикс>, <сессия>, body)`; тело — шпион,
        возвращающий уникальный объект. Проверяется: тело вызвано ровно один
        раз ровно двумя позиционными аргументами — `sqlite3.Connection` и
        полным id; функция возвращает объект, который вернуло тело.
        Ловит мутацию: тело получает неразвёрнутый `task_id` вместо
        развёрнутого (шпион видит префикс), либо `run_task_command` забывает
        `return` (вместо объекта тела — None), либо тело зовётся с `sid`
        вместо пары (conn, id).
        """
        for _ in range(3):
            full, prefix = self.seed_task()
            with self.subTest(prefix=prefix, seed=self.seed):
                result = object()
                body = mock.Mock(return_value=result)
                got = lease.run_task_command(prefix, "sess-a", body)
                self.assertIs(got, result, self.msg("возврат — не результат тела"))
                self.assertEqual(body.call_count, 1, self.msg("тело не один раз"))
                args, kwargs = body.call_args
                self.assertEqual(kwargs, {}, self.msg("тело с именованными аргументами"))
                self.assertEqual(len(args), 2, self.msg(f"аргументы тела: {args!r}"))
                self.assertIsInstance(args[0], sqlite3.Connection, self.msg("не соединение"))
                self.assertEqual(args[1], full, self.msg("тело получило не полный id"))

    def test_ac2_run_locked_gets_full_id_without_named_arguments(self):
        """`run_locked` получает полный id, без `on_refusal`/`same_host_ok`/`force`.

        `lease.run_locked` обёрнут шпионом с пропуском к настоящему; тело
        во время работы читает строку lease: блокировка взята под полным
        id задачи (развёрнут ДО взятия), а не под префиксом.
        Ловит мутацию: `run_locked` зовётся с префиксом (lease берётся по
        несуществующему ключу, тело видит пустую строку lease полного id),
        либо обвязка передаёт `same_host_ok=True`/`force=True`/
        `on_refusal="print"` — шпион видит именованный аргумент.
        """
        for _ in range(3):
            full, prefix = self.seed_task()
            with self.subTest(prefix=prefix, seed=self.seed):
                seen = {}

                def body(conn, task_id):
                    seen["lease"] = store.lease_row(conn, full)
                    seen["prefix_lease"] = store.lease_row(conn, prefix)

                with mock.patch.object(lease, "run_locked",
                                       wraps=lease.run_locked) as spy:
                    lease.run_task_command(prefix, "sess-b", body)
                self.assertEqual(spy.call_count, 1, self.msg("run_locked не один раз"))
                args, kwargs = spy.call_args
                self.assertEqual(args[1], full, self.msg("run_locked получил не полный id"))
                for name in ("on_refusal", "same_host_ok", "force"):
                    self.assertNotIn(name, kwargs, self.msg(f"передан {name}"))
                self.assertIsNotNone(seen.get("lease"),
                                     self.msg("во время тела нет lease полного id"))
                self.assertEqual(seen["lease"]["session_id"], "sess-b")
                self.assertIsNone(seen.get("prefix_lease"),
                                  self.msg("lease взят под префиксом"))

    def test_ac3_foreign_live_lease_refuses_with_reference_text(self):
        """Чужой живой lease: `SystemExit` с текстом отказа эталона `acquire`.

        Строка lease каждой случайной задачи записана на чужую сессию с
        живым pid (pid этого процесса) и этой машиной, возраст heartbeat —
        случайный в пределах свежести, часы `liveness` остановлены. Эталон —
        `lease.acquire(conn, <полный id>, "sess-x")`; затем
        `run_task_command(<префикс>, "sess-x", body)`. Текст `SystemExit`
        совпадает с эталоном целиком (включая полный id), тело не вызвано,
        строка lease не изменилась.
        Ловит мутацию: префикс разворачивается после взятия lease (отказ
        несёт префикс вместо полного id, либо lease берётся по префиксу и
        тело исполняется), либо обвязка зовёт `run_locked(...,
        same_host_ok=True)` — чужой lease этой машины пропускается, тело
        вызвано, `SystemExit` нет.
        """
        for _ in range(3):
            full, prefix = self.seed_task()
            with self.subTest(prefix=prefix, seed=self.seed):
                frozen = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(
                    seconds=self.rng.randint(0, 10 ** 8))
                age = self.rng.randint(0, max(0, int(config.LEASE_STALE_AFTER_SEC) - 1))
                heartbeat = (frozen - timedelta(seconds=age)).strftime(
                    "%Y-%m-%d %H:%M:%SZ")
                store.insert_lease(self.conn, full, "sess-holder", os.getpid(),
                                   socket.gethostname(), heartbeat)
                before = dict(store.lease_row(self.conn, full))
                body = mock.Mock()
                FrozenDatetime.frozen = frozen
                with mock.patch.object(liveness, "datetime", FrozenDatetime):
                    reference, _fresh = lease.acquire(self.conn, full, "sess-x")
                    self.assertIsNotNone(reference, self.msg("эталон не отказал"))
                    with self.assertRaises(SystemExit) as cm:
                        lease.run_task_command(prefix, "sess-x", body)
                self.assertIn(full, reference)
                self.assertEqual(cm.exception.code, reference,
                                 self.msg("текст отказа не совпал с эталоном"))
                body.assert_not_called()
                self.assertEqual(dict(store.lease_row(self.conn, full)), before,
                                 self.msg("строка lease изменилась"))


class CommandsDelegateTest(unittest.TestCase):
    """Разбор AST и сигнатур семи команд — без песочницы."""

    def test_ac4_commands_delegate_wrapping_to_run_task_command(self):
        """Тело каждой из семи команд отдаёт обвязку `lease.run_task_command`.

        Исходный текст каждой команды разбирается AST: нет вызовов
        `store.db`, `store.resolve_task_id`, `lease.run_locked`; есть вызов
        `lease.run_task_command`, второй позиционный аргумент которого —
        имя `session_id`; если третий аргумент — лямбда, в вызове `_cmd_*`
        внутри неё id задачи (второй аргумент) — параметр этой лямбды.
        Ловит мутацию: в команде возвращена своя копия обвязки
        (`store.db()`+`resolve_task_id`+`run_locked`), потерян `session_id`
        (вторым аргументом передан `None`), либо лямбда берёт `task_id`
        внешней функции (неразвёрнутый префикс уходит в `_cmd_*`).
        """
        for module, name, _params in COMMANDS:
            with self.subTest(command=f"{module.__name__}.{name}"):
                fn = getattr(module, name)
                tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
                func = tree.body[0]
                calls = [n for n in ast.walk(func) if isinstance(n, ast.Call)]
                names = [dotted(c.func) for c in calls]
                for banned in ("store.db", "store.resolve_task_id",
                               "lease.run_locked"):
                    self.assertNotIn(banned, names, f"{name}: вызов {banned}")
                wrapped = [c for c in calls
                           if dotted(c.func) == "lease.run_task_command"]
                self.assertEqual(len(wrapped), 1,
                                 f"{name}: нет вызова lease.run_task_command")
                call = wrapped[0]
                self.assertGreaterEqual(len(call.args), 2, name)
                second = call.args[1]
                self.assertIsInstance(second, ast.Name, name)
                self.assertEqual(second.id, "session_id",
                                 f"{name}: вторым аргументом не session_id")
                if len(call.args) >= 3 and isinstance(call.args[2], ast.Lambda):
                    lam = call.args[2]
                    params = {a.arg for a in lam.args.args}
                    inner = [c for c in ast.walk(lam.body)
                             if isinstance(c, ast.Call)
                             and dotted(c.func).split(".")[-1].startswith("_cmd_")]
                    self.assertTrue(inner, f"{name}: в лямбде нет вызова _cmd_*")
                    for c in inner:
                        self.assertGreaterEqual(len(c.args), 2, name)
                        tid = c.args[1]
                        self.assertIsInstance(tid, ast.Name, name)
                        self.assertIn(tid.id, params,
                                      f"{name}: id задачи в _cmd_* — не параметр лямбды")

    def test_ac6_command_names_and_signatures_kept(self):
        """Имена семи команд и порядок/умолчания их параметров прежние.

        Для каждой команды по `inspect.signature` сверяются первые
        параметры: имена, порядок, вид (позиционно-именованный) и
        умолчания — `session_id=None` на прежнем месте, у
        `cmd_zones_extend` за ним `matrix_path=None`.
        Ловит мутацию: у команды снят необязательный `session_id` или его
        умолчание (вызов `cmd_run(task_id)` из `auto` падает TypeError),
        либо `session_id` переставлен после `matrix_path` — позиционный
        вызов `cmd_zones_extend(id, paths, sid)` отдаёт сессию в матрицу.
        """
        for module, name, expected in COMMANDS:
            with self.subTest(command=f"{module.__name__}.{name}"):
                fn = getattr(module, name, None)
                self.assertTrue(callable(fn), f"{name} не найдена")
                params = list(inspect.signature(fn).parameters.values())
                self.assertGreaterEqual(len(params), len(expected), name)
                for param, (pname, default) in zip(params, expected):
                    self.assertEqual(param.name, pname, name)
                    self.assertEqual(param.kind,
                                     inspect.Parameter.POSITIONAL_OR_KEYWORD, name)
                    self.assertEqual(param.default, default, f"{name}.{pname}")
                for param in params[len(expected):]:
                    self.assertIsNot(param.default, EMPTY,
                                     f"{name}: новый обязательный параметр {param.name}")


if __name__ == "__main__":
    unittest.main()
