"""Приёмочные тесты 01M1GHZTX9YEPF0TY46QWZAGD8 — AC-1
(tasks/01M1GHZTX9YEPF0TY46QWZAGD8/SPEC.md, «Критерии приёмки»).

AC-1: «Остановка auto/переход в merge_gate с зафиксированным sha
печатает подсказку «artel.py approve <id> <полный sha>» (сорок
шестнадцатеричных символов присутствуют в строке подсказки).»

Красен до реализации: сегодня ни подсказка остановки `auto`
(`orchestrator/config.py::AUTO_STOP["merge_gate"]`, форматируется
`orchestrator/auto.py::auto_stop_advice`), ни печать при входе в
`merge_gate` (`orchestrator/fsm.py:601`, ветка `acceptance` внутри
`fsm._cmd_approve`) не подставляют зафиксированный sha — обе строки
сегодня несут только `{id}`. Оба теста ниже ищут зафиксированный sha
(реальный HEAD ветки задачи на момент перехода) в строке напечатанной
подсказки и падают на его отсутствии.

Настоящий git (`tests.test_git_fixation.RealPultGitTest`), не заглушка
`gitcmd.git`: предмет проверки — фактическое значение зафиксированного
sha в строке подсказки, а не факт вызова функции форматирования.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import auto, fsm, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402


class Ac1HintIncludesFullShaTest(RealPultGitTest):

    def force_state(self, state: str) -> str:
        """Прыжок в состояние в обход обычной цепочки переходов.

        Сам переход настоящий (`store.set_state`), поэтому и хэш-фиксация
        настоящая — `record_fixation` (вызывается изнутри `set_state`)
        коммитит текущий реальный HEAD ветки задачи, не заглушку.
        """
        conn = store.db()
        current = store.get_task(conn, self.TASK)["state"]
        store.set_state(conn, self.TASK, state, "operator",
                        expected_state=current, detail="тест: подготовка")
        return self.head()

    def test_ac1_auto_stop_at_merge_gate_hint_includes_full_fixed_sha(self):
        """auto, остановившийся в merge_gate с зафиксированным sha,
        печатает подсказку с этим sha в готовом к копированию виде.

        Ловит мутацию: если подсказка `AUTO_STOP["merge_gate"]` останется
        прежней («artel.py approve {id}  (выполнит merge)», без sha), в
        напечатанной строке не найдётся зафиксированный sha — проверка
        подстроки не пройдёт.
        """
        sha = self.force_state("merge_gate")

        out = self.capture(auto.cmd_auto, self.TASK)

        hint_lines = [line for line in out.splitlines()
                     if "artel.py approve" in line]
        self.assertTrue(hint_lines,
                        f"строка подсказки не найдена в выводе auto:\n{out}")
        self.assertTrue(any(sha in line for line in hint_lines),
                        f"зафиксированный sha {sha} не найден в подсказке:\n{out}")

    def test_ac1_transition_into_merge_gate_prints_hint_with_full_sha(self):
        """Переход `acceptance -> merge_gate` печатает следующую команду
        approve сразу с sha, зафиксированным на этом же переходе.

        Ловит мутацию: если печать при входе в merge_gate (ветка
        `acceptance` в `fsm._cmd_approve`) останется прежней («artel.py
        approve {id}  (выполнит merge)», без sha), тест не найдёт
        зафиксированный sha в напечатанной строке.
        """
        sha = self.force_state("acceptance")
        self.capture(fsm.cmd_approve, self.TASK)  # "требует sha" — без перехода

        out = self.capture(fsm.cmd_approve, self.TASK, sha)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "merge_gate")
        hint_lines = [line for line in out.splitlines()
                     if "artel.py approve" in line]
        self.assertTrue(hint_lines,
                        f"строка подсказки не найдена в выводе approve:\n{out}")
        self.assertTrue(any(sha in line for line in hint_lines),
                        f"зафиксированный sha {sha} не найден в подсказке:\n{out}")


if __name__ == "__main__":
    unittest.main()
