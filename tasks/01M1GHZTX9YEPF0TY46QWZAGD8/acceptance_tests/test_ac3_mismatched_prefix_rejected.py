"""Приёмочный тест 01M1GHZTX9YEPF0TY46QWZAGD8 — AC-3
(tasks/01M1GHZTX9YEPF0TY46QWZAGD8/SPEC.md, «Критерии приёмки»).

AC-3: «approve <id> <8+ символов, не являющиеся префиксом
зафиксированного> отклоняется с печатью зафиксированного sha (прежнее
поведение несовпадения).»

Зелёный с рождения: критерий явно требует СОХРАНИТЬ сегодняшнее
поведение несовпадения — `fsm.confirm_fixation` уже сравнивает
переданное значение с зафиксированным `current` на равенство и уже
отклоняет несовпадение `sys.exit`'ом с текстом, включающим `current`
(`orchestrator/fsm.py::confirm_fixation`, ветка `sha != current`).
Восьмисимвольное значение, не являющееся префиксом `current`, заведомо
`!= current` и сегодня, и после введения префиксного сравнения (оно
по построению не совпадёт ни с одним префиксом `current`) — тест не
должен покраснеть ни до, ни после реализации этой задачи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402


class Ac3MismatchedPrefixRejectedTest(RealPultGitTest):

    def test_ac3_eight_char_value_not_a_prefix_is_refused_with_fixed_sha_printed(self):
        """approve с 8-символьным значением, не совпадающим с началом
        зафиксированного sha, отклоняется с печатью самого
        зафиксированного sha в тексте отказа.

        Ловит мутацию: если введённое AC-2 префиксное сравнение начнёт
        сверять только ДЛИНУ (например, «8+ символов — принять»,
        забыв сравнить содержимое с `current`), это заведомо непрефиксное
        значение пройдёт approve вместо отказа.
        """
        sha = self.enter_spec_gate()
        wrong = ("0" if sha[0] != "0" else "1") + sha[1:8]
        self.assertEqual(len(wrong), 8)
        self.assertFalse(sha.startswith(wrong),
                         "предпосылка теста: значение не префикс sha")

        with self.assertRaises(SystemExit) as ctx:
            self.capture(fsm.cmd_approve, self.TASK, wrong)

        self.assertIn(sha, str(ctx.exception),
                      "отказ обязан печатать зафиксированный sha (AC-3)")
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_gate")


if __name__ == "__main__":
    unittest.main()
