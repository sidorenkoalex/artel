"""Регресс-тест на замечание major REVIEW T048 итерации 2:
`orchestrator.catalog.cmd_new` пересчитывает `branch` от РЕАЛЬНО
выданного `store.next_task_number`, а не только от `store.peek_task_number`
(ранняя проверка коллизии ветки, требование 1) — иначе под гонкой двух
конкурентных `new` (peek видит устаревшее значение счётчика, транзакция
`next_task_number` выдаёт следующее) заведённая задача получает `branch`,
не совпадающий с её фактическим `task_id`.

REVIEW итерации 2 воспроизвёл гонку вручную (Фаза B) и мутационно
подтвердил, что откат правки не роняет ни один тест пакета — этот файл
закрывает тот пробел исполняемой защитой.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest, fake_git  # noqa: E402


class PeekTaskNumberRaceTest(TmpRootTest):
    """`ROOT` намеренно не патчится — `cmd_new` читает настоящий
    `templates/SPEC.md` пульта, тем же приёмом, что `tests/
    test_analyst_role.py::_AnalystRoleTmpRootTest`."""

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "WORKTREES")

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.capture(catalog.cmd_init)

    def test_branch_follows_real_task_id_not_stale_peek(self):
        conn = store.db()
        # Пять «конкурентных» задач забирают номера 1..5 напрямую через
        # счётчик — peek этого теста после них устарел бы, если бы читался
        # заранее (моделируем это ниже подменой на 1 меньше реального).
        for _ in range(5):
            store.next_task_number(conn, config.DEFAULT_TARGET)

        real_peek = store.peek_task_number
        with mock.patch.object(
                store, "peek_task_number",
                side_effect=lambda c, t: real_peek(c, t) - 1):
            out = self.capture(catalog.cmd_new, "Задача под гонкой")

        task_id = out.split("]")[0].strip("[")
        self.assertEqual(task_id, "T006",
                         "next_task_number должен выдать реальный номер 6")

        row = store.db().execute(
            "SELECT branch FROM tasks WHERE id=?", (task_id,)).fetchone()
        expected_branch = (
            f"task/t006-{catalog.slugify('Задача под гонкой')}")
        self.assertEqual(
            row["branch"], expected_branch,
            "branch обязан считаться от реального task_id (T006), а не "
            "от устаревшего peek-значения (T005) — гонка REVIEW T048 "
            "итерации 2")

        wt_dir = config.WORKTREES / task_id / "tasks" / task_id
        self.assertTrue((wt_dir / "SPEC.md").exists())


if __name__ == "__main__":
    unittest.main()
