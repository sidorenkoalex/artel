"""Приёмочные тесты AC-8 задачи 01M28SWSQ46B8A9FX6KBVJ3Y0G: сценарии
AC-5 («снят единственный тест критерия без пометки» — отказ) и AC-7
(«корректная правка» — лок сдвинут) — те же самые, но для
`amend-tests ... --from-branch`.

Красен до реализации: `test_ac8_missing_criterion_test_refuses_and_leaves_
lock_on_the_branch` — `_cmd_amend_tests_from_branch` сегодня не сверяет
трассируемость расхождения вовсе, правка фиксируется без отказа.
`test_ac8_valid_edit_still_moves_lock_via_from_branch` УЖЕ зелёный на
текущем коде — контроль, не молчаливый пропуск: валидное расхождение
фиксируется и сегодня, эта задача не меняет этот исход.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (  # noqa: E402
    AC_TEST_MISSING_AC1_NO_MARKER, AC_TEST_VALID_EDIT_BOTH_COVERED,
    FromBranchGateSandbox, amend)
from orchestrator import gitcmd  # noqa: E402


class FromBranchScenariosTest(FromBranchGateSandbox):

    def test_ac8_missing_criterion_test_refuses_and_leaves_lock_on_the_branch(self):
        """Расхождение на голове артефактной ветки снимает единственный
        тест критерия AC-1 без пометки — `--from-branch` отказывает,
        называя AC-1, `tests_locked_sha` остаётся на прежнем sha.

        Ловит мутацию: проверка трассируемости добавлена только в
        worktree-путь (`_cmd_amend_tests`), `_cmd_amend_tests_from_branch`
        её не наследует — расхождение с той же сломанной планкой
        фиксируется без единого отказа именно на этом, втором входе.
        """
        old_locked = self.row()["tests_locked_sha"]
        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py":
                 AC_TEST_MISSING_AC1_NO_MARKER},
            "правка планки (автокоммит роли, минуя amend-tests) — снят "
            "тест AC-1 без пометки")

        with self.assertRaises(SystemExit) as ctx:
            amend.cmd_amend_tests(self.TASK, "снят тест AC-1 без пометки",
                                  from_branch=True)

        self.assertIn("AC-1", str(ctx.exception),
                      "отказ обязан называть критерий AC-1 — тот, чей тест снят")
        self.assertEqual(
            self.row()["tests_locked_sha"], old_locked,
            "tests_locked_sha не должен сдвигаться при отказе трассируемости")

    def test_ac8_valid_edit_still_moves_lock_via_from_branch(self):
        """Расхождение на голове артефактной ветки по-прежнему покрывает
        оба критерия SPEC_V2 (AC-1 — двумя тестами, AC-2 — валидной
        меткой) — `--from-branch` фиксирует расхождение как обычно,
        `tests_locked_sha` сдвигается на sha головы ветки.

        Ловит мутацию: проверка трассируемости отказывает на ЛЮБОМ
        расхождении независимо от реального покрытия — валидная правка
        через `--from-branch` тоже блокируется.
        """
        old_locked = self.row()["tests_locked_sha"]
        new_sha = self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py":
                 AC_TEST_VALID_EDIT_BOTH_COVERED},
            "правка планки (автокоммит роли, минуя amend-tests) — "
            "расширяет проверку AC-1")

        amend.cmd_amend_tests(self.TASK, "правка расширяет проверку AC-1",
                              from_branch=True)

        new_locked = self.row()["tests_locked_sha"]
        self.assertNotEqual(new_locked, old_locked,
                            "tests_locked_sha обязан сдвинуться")
        self.assertEqual(new_locked, new_sha,
                         "tests_locked_sha обязан указывать на sha головы "
                         "артефактной ветки")
        self.assertEqual(new_locked, gitcmd.branch_head_sha(self.branch))


if __name__ == "__main__":
    unittest.main()
