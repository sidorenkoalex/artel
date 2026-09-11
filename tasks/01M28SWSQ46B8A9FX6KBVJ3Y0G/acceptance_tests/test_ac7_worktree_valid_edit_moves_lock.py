"""Приёмочный тест AC-7 задачи 01M28SWSQ46B8A9FX6KBVJ3Y0G: корректная
правка worktree (оба критерия SPEC_V2 песочницы по-прежнему покрыты) —
`tests_locked_sha` сдвигается как раньше, новая проверка трассируемости
не блокирует валидную правку.

Зелёный с рождения: `guard.acceptance_traceability_errors` на корректно
покрытой планке возвращает пустой список уже сегодня (правило T023
существует независимо от этой задачи) — добавление вызова этой функции
в `_cmd_amend_tests` не меняет исход для правки без нарушений, только
для правки, снимающей покрытие (см. остальные файлы этой планки, где
тест красен). Этот тест — контроль на отсутствие регресса «трассируемость
теперь блокирует и валидные правки», не молчаливый пропуск.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (  # noqa: E402
    AC_TEST_VALID_EDIT_BOTH_COVERED, WorktreeGateSandbox, amend)
from orchestrator import gitcmd  # noqa: E402


class ValidEditWorktreeTest(WorktreeGateSandbox):

    def test_ac7_valid_edit_still_moves_lock_to_new_commit(self):
        """Правка worktree по-прежнему покрывает оба критерия SPEC_V2
        (AC-1 — теперь двумя тестовыми методами, AC-2 — валидной меткой
        manual) — `amend-tests` коммитит правку на артефактную ветку и
        сдвигает `tests_locked_sha` на sha этого коммита, без единого
        отказа.

        Ловит мутацию: проверка трассируемости отказывает на ЛЮБОЙ
        правке независимо от реального покрытия (например сравнивает
        число тестов со старым числом вместо честного прогона `guard.
        acceptance_traceability_errors`) — валидная правка тоже
        блокируется, регрессия к «amend-tests больше не работает».
        """
        old_locked = self.row()["tests_locked_sha"]
        self.edit_tests(AC_TEST_VALID_EDIT_BOTH_COVERED)

        amend.cmd_amend_tests(self.TASK, "правка расширяет проверку AC-1")

        new_locked = self.row()["tests_locked_sha"]
        self.assertNotEqual(
            new_locked, old_locked,
            "tests_locked_sha обязан сдвинуться на новый коммит валидной правки")
        self.assertEqual(
            new_locked, gitcmd.branch_head_sha(self.branch),
            "tests_locked_sha обязан указывать на голову артефактной ветки")


if __name__ == "__main__":
    unittest.main()
