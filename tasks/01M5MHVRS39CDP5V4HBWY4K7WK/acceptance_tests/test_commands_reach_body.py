"""Семь команд с префиксом id доходят до своего тела `_cmd_*` с полным id и прежними аргументами.

Группа: разовый
Зелёный с рождения: семь команд уже разворачивают префикс до lease и передают тело с добавочными аргументами — AC-5/AC-10 держат это поведение при переводе обвязки на lease.run_task_command.

Почему разовый: критерии AC-5 и AC-10 прямо требуют подменить закрытое тело
`_cmd_*` (`mock.patch.object(<модуль>, "_cmd_…")`), а долгоживущему файлу
`tests/` patch закрытого имени запрещён (`scripts/guard.py`, признак
«patch закрытого»). Проверка обвязки на публичном интерфейсе — в
долгоживущем файле задачи (AC-1..AC-4, AC-6).
"""
import inspect
import random
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

if CODE_ROOT and CODE_ROOT not in sys.path:
    sys.path.insert(0, CODE_ROOT)

from orchestrator import (answer, ci_rerun, config, fsm,  # noqa: E402
                          pull_main, runner, store, workspace)
from tests.sandbox import InitializedTmpRootTest  # noqa: E402

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class CommandsReachBodyTest(InitializedTmpRootTest):
    """Связка «команда — run_task_command — run_locked — acquire — БД
    песочницы»; подменено только тело `_cmd_*`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()

    def seed_task(self) -> tuple[str, str]:
        """(полный id, уникальный префикс): у задачи есть сосед с общим
        началом id, поэтому префикс разворачивается поиском по префиксу."""
        rng = self.rng
        while True:
            full = "".join(rng.choice(ULID_ALPHABET) for _ in range(26))
            shared = rng.randint(2, 8)
            if not store.task_id_matches(self.conn, full[:shared]):
                break
        other = rng.choice([c for c in ULID_ALPHABET if c != full[shared]])
        decoy = (full[:shared] + other
                 + "".join(rng.choice(ULID_ALPHABET) for _ in range(25 - shared)))
        for task_id in (full, decoy):
            store.insert_task(self.conn, task_id, "Задача", "in_dev",
                              f"task/{task_id.lower()}-x",
                              config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        return full, full[:shared + 1 + rng.randint(0, 4)]

    def word(self) -> str:
        return "".join(self.rng.choice("абвгдежзик") for _ in range(8))

    def cases(self, prefix: str, sid: str):
        """(модуль, команда, тело, позиционные аргументы команды, ожидаемые
        добавочные аргументы тела по имени)."""
        reason_r, reason_c = self.word(), self.word()
        paths, matrix = f"src/{self.word()}.py", f"/tmp/{self.word()}.md"
        return (
            (fsm, "cmd_spec_audit", "_cmd_spec_audit", (prefix, sid), {}),
            (fsm, "cmd_reject", "_cmd_reject", (prefix, reason_r, sid),
             {"reason": reason_r}),
            (pull_main, "cmd_pull_main", "_cmd_pull_main", (prefix, sid), {}),
            (workspace, "cmd_workspace", "_cmd_workspace", (prefix, sid), {}),
            (ci_rerun, "cmd_ci_rerun", "_cmd_ci_rerun", (prefix, reason_c, sid),
             {"reason": reason_c}),
            (runner, "cmd_run", "_cmd_run", (prefix, sid), {}),
            (answer, "cmd_zones_extend", "_cmd_zones_extend",
             (prefix, paths, sid, matrix),
             {"paths_arg": paths, "matrix_path": matrix}),
        )

    def command_names(self) -> list[str]:
        return [c[1] for c in self.cases("", "")]

    def case(self, command: str, prefix: str):
        """Набор `cases` одной команды для префикса и случайной сессии."""
        sid = f"sess-{self.word()}"
        return next(c for c in self.cases(prefix, sid) if c[1] == command)

    def call_with_spy(self, module, command, body_name, args):
        """Зовёт команду с телом-шпионом; (шпион, возврат команды,
        аргументы тела, связанные по сигнатуре настоящего тела)."""
        real = getattr(module, body_name)
        result = object()
        with mock.patch.object(module, body_name,
                               return_value=result) as spy:
            got = getattr(module, command)(*args)
        bound = None
        if spy.call_count == 1:
            bound = inspect.signature(real).bind(*spy.call_args.args,
                                                 **spy.call_args.kwargs)
            bound = dict(bound.arguments)
        return spy, got, result, bound

    def test_ac10_each_command_reaches_body_with_full_id(self):
        """Каждая из семи команд с уникальным префиксом зовёт своё тело с полным id.

        Для каждой команды заводится случайная задача с соседом по префиксу,
        команда зовётся с префиксом и сессией; тело `_cmd_*` подменено
        шпионом, `run_task_command`/`run_locked`/`acquire` настоящие.
        Шпион вызван ровно один раз, его аргумент id (по сигнатуре тела —
        второй, после соединения) — полный id задачи, не префикс; первый
        аргумент — соединение БД.
        Ловит мутацию: лямбда команды передаёт в `_cmd_*` имя `task_id`
        внешней функции (в тело уходит неразвёрнутый префикс), либо
        команда больше не доходит до тела (обвязка зовёт тело чужой
        команды или не зовёт его) — шпион видит префикс или 0 вызовов.
        """
        for command in self.command_names():
            full, prefix = self.seed_task()
            module, _c, body_name, args, _e = self.case(command, prefix)
            with self.subTest(command=command, prefix=prefix, seed=self.seed):
                spy, _got, _result, bound = self.call_with_spy(
                    module, command, body_name, args)
                self.assertEqual(spy.call_count, 1,
                                 f"{command}: тело вызвано {spy.call_count} раз "
                                 f"(зерно: {self.seed})")
                values = list(bound.values())
                self.assertIsInstance(values[0], sqlite3.Connection, command)
                self.assertEqual(values[1], full,
                                 f"{command}: тело получило не полный id "
                                 f"(зерно: {self.seed})")

    def test_ac5_extra_arguments_reach_body_and_run_returns_result(self):
        """Добавочные аргументы доходят до тела, `cmd_run` возвращает результат.

        `cmd_reject` (`reason`), `cmd_ci_rerun` (`reason`), `cmd_zones_extend`
        (`paths_arg`, `matrix_path`) зовутся со случайными значениями —
        тело-шпион получает их по своим именам с теми же значениями.
        `cmd_run` с телом-шпионом, возвращающим уникальный объект, отдаёт
        вызывающему этот же объект.
        Ловит мутацию: замыкание теряет добавочный аргумент или путает
        порядок (`matrix_path` уходит на место `paths_arg`, в тело `None`
        вместо причины), либо `cmd_run` перестаёт возвращать результат
        `run_task_command` (вызывающий получает None вместо объекта тела).
        """
        for command in ("cmd_reject", "cmd_ci_rerun", "cmd_zones_extend",
                        "cmd_run"):
            _full, prefix = self.seed_task()
            module, _c, body_name, args, expected = self.case(command, prefix)
            with self.subTest(command=command, prefix=prefix, seed=self.seed):
                spy, got, result, bound = self.call_with_spy(
                    module, command, body_name, args)
                self.assertEqual(spy.call_count, 1, command)
                for name, value in expected.items():
                    self.assertEqual(bound.get(name), value,
                                     f"{command}: {name} в теле — {bound.get(name)!r} "
                                     f"(зерно: {self.seed})")
                if command == "cmd_run":
                    self.assertIs(got, result,
                                  f"cmd_run вернул {got!r}, не результат тела")


if __name__ == "__main__":
    unittest.main()
