"""Приёмочный тест AC-3 задачи 01M28SWSQ46B8A9FX6KBVJ3Y0G:
`_cmd_amend_tests_from_branch` обязан звать ту же проверку трассируемости
по содержимому SPEC.md и `acceptance_tests/` ГОЛОВЫ артефактной ветки (не
диска worktree), до сдвига `tests_locked_sha`; непустой результат —
отказ тем же текстом, что AC-1.

Красен до реализации: `_cmd_amend_tests_from_branch` (orchestrator/
amend.py) сегодня не вызывает проверку трассируемости вовсе — расхождение
на ветке, снимающее тест AC-1 без пометки, журналируется и фиксируется
как обычное валидное расхождение (та же дыра, что и у worktree-пути,
копилка 11.09): тест падает на отсутствии отказа.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (  # noqa: E402
    AC_TEST_MISSING_AC1_NO_MARKER, FromBranchGateSandbox, REFUSAL_PREFIX_RE,
    amend)


class MissingTraceabilityFromBranchTest(FromBranchGateSandbox):

    def test_ac3_divergence_missing_criterion_refuses_before_lock_shift(self):
        """Голова артефактной ветки расходится с `tests_locked_sha`: SPEC.md
        не менялся, `acceptance_tests/test_ac.py` на ветке снял
        единственный тест AC-1 без пометки (то же содержимое, что AC-1/
        AC-5 worktree-пути, здесь — автокоммит роли прямо на ветку, минуя
        `amend-tests`) — `amend-tests ... --from-branch` отказывает тем
        же префиксом сообщения, что и worktree-путь (AC-1), называя AC-1,
        ДО сдвига `tests_locked_sha`.

        Ловит мутацию: `_cmd_amend_tests_from_branch` продолжает читать
        `acceptance_tests/` только со старого `tests_locked_sha` (или
        не читает вовсе) вместо содержимого ГОЛОВЫ ветки — сломанное
        содержимое никогда не попадает в проверку, команда фиксирует
        расхождение как обычно, без единого отказа.
        """
        old_locked = self.row()["tests_locked_sha"]
        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py":
                 AC_TEST_MISSING_AC1_NO_MARKER},
            "правка планки (автокоммит роли, минуя amend-tests) — снят "
            "тест AC-1 без пометки")

        with self.assertRaises(SystemExit) as ctx:
            amend.cmd_amend_tests(self.TASK, "расхождение ломает AC-1",
                                  from_branch=True)

        message = str(ctx.exception)
        match = REFUSAL_PREFIX_RE.match(message)
        self.assertIsNotNone(
            match, f"отказ не начинается с ожидаемого префикса AC-1: {message!r}")
        self.assertEqual(match.group("task"), self.TASK)
        self.assertIn("AC-1", message,
                      "отказ обязан называть критерий AC-1 — тот, чей тест снят")
        self.assertEqual(
            self.row()["tests_locked_sha"], old_locked,
            "tests_locked_sha не должен сдвигаться при отказе трассируемости")


if __name__ == "__main__":
    unittest.main()
