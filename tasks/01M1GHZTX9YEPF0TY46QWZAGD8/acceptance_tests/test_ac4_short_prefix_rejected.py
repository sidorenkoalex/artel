"""Приёмочный тест 01M1GHZTX9YEPF0TY46QWZAGD8 — AC-4
(tasks/01M1GHZTX9YEPF0TY46QWZAGD8/SPEC.md, «Критерии приёмки»).

AC-4: «approve <id> <короче 8 символов> отклоняется именованным
отказом про минимальную длину, не доходя до проверки совпадения.»

Красен до реализации: сегодня `fsm.confirm_fixation` не различает
«слишком короткий префикс» и «не совпадает» — любое значение, не
равное `current` целиком (в том числе настоящий, но короткий отрезок
начала `current`), падает в общую ветку `sha != current` и печатает
именно отказ о несовпадении (`f"sha {sha} не совпадает с
зафиксированным {current}"`). AC-4 требует ОТДЕЛЬНЫЙ именованный отказ
про минимальную длину до этой проверки — тест ниже падает на том, что
сегодняшний текст отказа несёт «не совпадает с зафиксированным» вместо
него.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402


class Ac4ShortPrefixRejectedTest(RealPultGitTest):

    def test_ac4_prefix_shorter_than_eight_chars_refused_by_dedicated_min_length_error(self):
        """approve с настоящим, но коротким (5 символов) отрезком начала
        зафиксированного sha отклоняется отдельным именованным отказом
        про минимальную длину — не тем же отказом, что несовпадение.

        Ловит мутацию: если реализация не заведёт отдельную проверку
        минимальной длины (8 символов, SPEC «Не входит») ДО сравнения
        совпадения, короткий, но настоящий префикс провалится через
        общую ветку «не совпадает с зафиксированным» (или, наоборот,
        ошибочно пройдёт approve, приняв его как валидный префикс) —
        обе мутации ловятся проверками ниже.
        """
        sha = self.enter_spec_gate()
        too_short = sha[:5]

        with self.assertRaises(SystemExit) as ctx:
            self.capture(fsm.cmd_approve, self.TASK, too_short)

        message = str(ctx.exception)
        self.assertNotIn(
            "не совпадает с зафиксированным", message,
            "короткий префикс обязан отклоняться ОТДЕЛЬНЫМ именованным "
            "отказом про минимальную длину, а не общей веткой "
            "несовпадения (AC-4, «не доходя до проверки совпадения»)")
        self.assertIn("8", message,
                      "отказ обязан называть минимальную длину — 8 "
                      "символов (SPEC «Не входит»)")
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_gate", "approve не должен исполниться")


if __name__ == "__main__":
    unittest.main()
