"""Команда `pull-main` при молчании git: именованный отказ, а не «main уже в ветке».

SPEC 01M4PMR5EVFK4KQDPWB1KEGM7V, требование 6, на пути команды. Долгоживущий
файл задачи `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py` этого
свойства не держит, разовая планка задачи после мержа не гоняется — без
этого файла регрессия «сбой git отвечает Оператору “main уже в ветке”»
прошла бы CI (REVIEW итерации 1, R1-F1).

Песочница — `PullMainSandbox` долгоживущего файла (импорт, не копия).
Вершина origin main «не получена» — `fsm._origin_main_sha` → `None` (ту же
точку песочница подменяет константой, как `tests/test_ci_rerun_command.py`);
`commits_behind` → `None` — ошибкой git на `rev-list --count`, как в
песочнице.
"""
import unittest
from unittest import mock

from orchestrator import fsm, pull, store
from tests.test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main import (
    OLD_STAMP, PullMainSandbox, pull_main_module)


class PullMainUnavailableTest(PullMainSandbox):

    def unavailable_journal(self) -> list:
        return [row for row in store.task_steps(store.db(), self.TASK)
                if row["action"] == pull.UNAVAILABLE_ACTION]

    def assert_named_refusal(self, text: str, case: str) -> None:
        module = pull_main_module()
        tag = f"зерно: {self.seed}; {case}; вывод: {text!r}"
        self.assertIn("pull-main: отказ", text, tag)
        self.assertNotIn(module.PULL_MAIN_ALREADY_FRESH, text, tag)
        self.assertEqual(self.merges(), [], tag)
        self.plank_run.assert_not_called()
        self.push.assert_not_called()
        self.assertEqual(self.git_pushes(), [], tag)
        self.assertEqual(self.ceiling_resets(), [], tag)
        self.assertEqual(self.task()["updated_at"], OLD_STAMP, tag)
        self.assertNotIn(module.PULL_MAIN_ACTION, self.actions(), tag)
        self.assertEqual(self.task()["state"], "verifying", tag)

    def test_unreachable_origin_main_is_named_refusal(self):
        """Вершина origin main не получена — отказ команды, не «main уже в ветке».

        Сценарий: вершина origin main не получена (`fsm._origin_main_sha` → `None`).
        Вывод — отказ `pull-main` без `PULL_MAIN_ALREADY_FRESH`; слияния,
        прогона планки, отправки головы, записи `PULL_MAIN_ACTION` и сброса
        потолка нет, задача в `verifying`; запись журнала
        `pull.UNAVAILABLE_ACTION` называет причину — недоступную вершину origin.

        Ловит мутацию: на пути `operator_pull` исход `Unavailable` для
        неполученной вершины origin main заменён на `Fresh()` — вывод
        содержит `PULL_MAIN_ALREADY_FRESH`, отказа нет; либо причина
        отказа не записана в журнал задачи (только в stdout).
        """
        with mock.patch.object(fsm, "_origin_main_sha", return_value=None):
            text = self.run_pull_main()
        self.assert_named_refusal(text, "origin")
        rows = self.unavailable_journal()
        self.assertEqual(len(rows), 1, text)
        self.assertIn("в origin не получена", rows[0]["detail"], text)

    def test_unanswered_commits_behind_is_named_refusal(self):
        """`commits_behind` → `None` — отказ команды, не «main уже в ветке».

        Сценарий: `rev-list --count` отвечает ошибкой git. Вывод — отказ
        `pull-main` без `PULL_MAIN_ALREADY_FRESH`; слияния, прогона планки,
        отправки головы, записи `PULL_MAIN_ACTION` и сброса потолка нет,
        задача в `verifying`; запись журнала `pull.UNAVAILABLE_ACTION`
        называет причину — неустановленное отставание ветки.

        Ловит мутацию: на пути `operator_pull` исход `Unavailable` для
        `commits_behind` → `None` заменён на `Fresh()` — вывод содержит
        `PULL_MAIN_ALREADY_FRESH`, отказа нет; либо причина отказа не
        записана в журнал задачи (только в stdout).
        """
        self.behind = None
        text = self.run_pull_main()
        self.assert_named_refusal(text, "behind")
        rows = self.unavailable_journal()
        self.assertEqual(len(rows), 1, text)
        self.assertIn("отставание ветки", rows[0]["detail"], text)


if __name__ == "__main__":
    unittest.main()
