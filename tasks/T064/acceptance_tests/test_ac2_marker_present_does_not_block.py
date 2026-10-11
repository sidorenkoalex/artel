"""AC-2 (tasks/T064/SPEC.md): тест-файл с такой строкой (с непустым
объяснением после двоеточия — «Красен до реализации:» или «Зелёный с
рождения:») не вызывает отказа перехода по этому основанию.

Зелёный с рождения: сценарий "маркер присутствует с непустым
объяснением -> переход не блокируется по признаку маркера" верен и
сегодня (до T064 такой проверки просто нет вовсе, значит она и не
блокирует), и обязан остаться верным после реализации задачи (SPEC
требование 1-2 добавляют отказ только для ОТСУТСТВИЯ маркера, не для
его присутствия). Тест не должен ни разу покраснеть в ходе реализации
T064 — красный прогон здесь означал бы, что разработчик реализовал
проверку шире, чем того требует AC-2 (регресс, не прогресс).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import fsm  # noqa: E402

from _sandbox import (AC_TEST_WITH_GREEN_MARKER,  # noqa: E402
                      AC_TEST_WITH_RED_MARKER, TmpRootTest)


class MarkerPresentDoesNotBlockTest(TmpRootTest):

    def test_ac2_red_marker_with_explanation_does_not_block_transition(self):
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_WITH_RED_MARKER, name="test_ac.py")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "in_dev",
            "докстринг несёт «Красен до реализации:» с непустым "
            "объяснением — переход обязан пройти (SPEC AC-2)")

    def test_ac2_green_marker_with_explanation_does_not_block_transition(self):
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_WITH_GREEN_MARKER,
                                    name="test_ac.py")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "in_dev",
            "докстринг несёт «Зелёный с рождения:» с непустым "
            "объяснением — переход обязан пройти (SPEC AC-2)")
