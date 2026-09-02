"""AC-1 (tasks/01M1H186VEVG6NF40YKH1338MD/SPEC.md): содержимое
tasks/<id>/acceptance_tests/, содержащее образец формата идентификатора
задачи (тот же набор образцов, что использует CI-job
id-format-greplint), отклоняет переход tests_writing -> in_dev до
записи фиксации лока (tests_locked_sha не обновляется); сообщение
отказа называет файл и строку и несёт подсказку «формат идентификатора
знает только генератор; строй проверку от фактического идентификатора».

Красен до реализации: проверка образца формата идентификатора на
выходе из tests_writing (эта задача, требования 1-2) сегодня не
существует — `orchestrator/fsm.py::_tests_writing_ac_state` сегодня
проверяет только трассируемость AC (T023) и маркер красноты (T064).
`AC_TEST_WITH_ID_SAMPLE` (tasks/01M1H186VEVG6NF40YKH1338MD/
acceptance_tests/_sandbox.py) несёт полное покрытие фиктивных AC-1/AC-2
песочницы и валидный маркер красноты — обе существующие проверки это
пропускают, и переход tests_writing -> in_dev сегодня проходит. Тест
ожидает, что переход останется в tests_writing, и упадёт, пока
разработчик не добавит саму проверку (требования 1-2). Красен по
правильной причине: отсутствие ЕЩЁ НЕ НАПИСАННОЙ проверки, не поломка
существующего.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import fsm  # noqa: E402

from _sandbox import (AC_TEST_WITH_ID_SAMPLE, ID_SAMPLE_LINE,  # noqa: E402
                      TmpRootTest)


class IdFormatSampleBlocksTransitionTest(TmpRootTest):

    def test_ac1_id_format_sample_blocks_transition_before_lock(self):
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_WITH_ID_SAMPLE, name="test_ac.py")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "tests_writing",
            "переход не должен пройти: acceptance_tests/test_ac.py несёт "
            "образец формата идентификатора задачи (SPEC AC-1)")
        self.assertFalse(
            self.row()["tests_locked_sha"],
            "фиксация лока (tests_locked_sha) не должна записываться, "
            "пока переход отклонён по образцу формата идентификатора "
            "(SPEC AC-1)")

    def test_ac1_refusal_message_names_file_and_line(self):
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_WITH_ID_SAMPLE, name="test_ac.py")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertIn(
            "test_ac.py", out,
            "сообщение отказа обязано называть файл с образцом формата "
            "идентификатора (SPEC AC-1) — вывод: " + out)
        self.assertIn(
            str(ID_SAMPLE_LINE), out,
            f"сообщение отказа обязано называть строку {ID_SAMPLE_LINE} "
            f"(строку с образцом формата идентификатора в "
            f"acceptance_tests/test_ac.py, SPEC AC-1) — вывод: {out}")

    def test_ac1_refusal_message_carries_generator_hint(self):
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_WITH_ID_SAMPLE, name="test_ac.py")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertIn(
            "формат идентификатора знает только генератор; строй "
            "проверку от фактического идентификатора", out,
            "сообщение отказа обязано нести дословную подсказку (SPEC "
            "AC-1) — вывод: " + out)
