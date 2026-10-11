"""Приёмочный тест 01M1GHZTX9YEPF0TY46QWZAGD8 — AC-5
(tasks/01M1GHZTX9YEPF0TY46QWZAGD8/SPEC.md, «Критерии приёмки»).

AC-5: «approve <id> без sha ведёт себя как раньше — печатает
зафиксированный sha и просит повторить.»

Зелёный с рождения: критерий явно требует НЕ МЕНЯТЬ сегодняшнее
поведение (`fsm.confirm_fixation`, ветка `sha is None`) — approve без
аргумента sha уже печатает зафиксированный sha и просьбу повторить
вызов, не исполняя переход (`orchestrator/fsm.py`:
"approve требует sha — зафиксирован {current}" / "повтори: artel.py
approve {id} {current}"). Эта задача не трогает данную ветку кода —
тест защищает её от случайной порчи побочным эффектом изменений
AC-1..AC-4, не проверяет новую логику.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402


class Ac5NoShaUnchangedTest(RealPultGitTest):

    def test_ac5_approve_without_sha_prints_fixed_sha_and_asks_to_repeat(self):
        """approve <id> без sha печатает зафиксированный sha и просит
        повторить вызов, не переводя задачу дальше.

        Ловит мутацию: если правка сравнения sha (AC-1..AC-4) случайно
        затронет ветку `sha is None` (например, начнёт требовать
        непустую строку раньше проверки на `None`, или перестанет
        печатать зафиксированный sha), тест перестанет находить sha в
        выводе или поймает незапланированный переход состояния.
        """
        sha = self.enter_spec_gate()

        out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertIn(sha, out)
        self.assertIn("повтори", out)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_gate")


if __name__ == "__main__":
    unittest.main()
