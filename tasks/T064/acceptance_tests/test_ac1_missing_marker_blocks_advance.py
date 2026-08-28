"""AC-1 (tasks/T064/SPEC.md): тест-файл `acceptance_tests/test_*.py`
без строки «Красен до реализации:» и без строки «Зелёный с рождения:»
в докстринге модуля -> выход задачи из состояния `tests_writing`
отклоняется guard'ом, и сообщение отказа называет файл, которому не
хватает маркера.

Красен до реализации: `scripts/guard.py`/`orchestrator/fsm.py`
(`_tests_writing_ac_state`, тем же местом, что и трассируемость AC ->
тест из T023 — `acceptance_traceability_errors`) сегодня не проверяют
маркер красноты в докстринге модуля. `AC_TEST_NO_MARKER`
(tasks/T064/acceptance_tests/_sandbox.py) несёт полное покрытие AC-1 и
AC-2 фиктивного SPEC песочницы БЕЗ маркера — трассируемость AC (T023)
это пропускает, и переход `tests_writing -> in_dev` сегодня проходит.
Тест ожидает, что он останется в `tests_writing`, и упадёт, пока
разработчик не добавит саму проверку маркера (SPEC T064, требования
1-2). Красен по правильной причине: отсутствие ЕЩЁ НЕ НАПИСАННОЙ
проверки, не поломка чего-то существующего.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import fsm  # noqa: E402

from _sandbox import AC_TEST_NO_MARKER, TmpRootTest  # noqa: E402


class MissingMarkerBlocksAdvanceTest(TmpRootTest):

    def test_ac1_missing_marker_blocks_tests_writing_exit(self):
        self.enter_tests_writing()
        # Полное покрытие AC-1/AC-2 фиктивного SPEC песочницы тестами —
        # трассируемость AC (T023) не имеет права быть причиной отказа
        # здесь, единственная переменная — отсутствие маркера красноты.
        self.write_acceptance_tests(AC_TEST_NO_MARKER, name="test_ac.py")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "tests_writing",
            "переход не должен пройти: файл acceptance_tests/test_ac.py "
            "не несёт ни «Красен до реализации:», ни «Зелёный с "
            "рождения:» в докстринге модуля (SPEC AC-1)")

    def test_ac1_refusal_message_names_the_file_missing_the_marker(self):
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_NO_MARKER, name="test_ac.py")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertIn(
            "test_ac.py", out,
            "сообщение отказа обязано называть файл, которому не "
            "хватает маркера (SPEC AC-1) — вывод: " + out)
