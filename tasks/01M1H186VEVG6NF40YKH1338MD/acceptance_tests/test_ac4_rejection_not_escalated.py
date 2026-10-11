"""AC-4 (tasks/01M1H186VEVG6NF40YKH1338MD/SPEC.md): отказ перехода по
основанию «образец формата идентификатора» не переводит задачу в
escalated и не требует ответа Оператора — задача остаётся в
tests_writing, test_author правит acceptance_tests/ и повторяет advance
тем же путём, что при отказе по трассируемости AC или маркеру
красноты.

Красен до реализации: сценарий целиком опирается на проверку из
требований 1-2 этой же задачи, которой сегодня ещё нет — первый advance
(с образцом формата идентификатора в acceptance_tests/) сегодня НЕ
отклоняется вовсе и сразу переводит задачу в in_dev, так что первый же
ассерт («состояние осталось tests_writing») упадёт раньше, чем тест
дойдёт до проверки собственно отсутствия эскалации и повторного
advance. Упадёт, пока разработчик не добавит саму проверку (требования
1, 3).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import fsm  # noqa: E402

from _sandbox import (AC_TEST_CLEAN, AC_TEST_WITH_ID_SAMPLE,  # noqa: E402
                      TmpRootTest)


class RejectionDoesNotEscalateTest(TmpRootTest):

    def test_ac4_rejection_leaves_task_in_tests_writing_not_escalated(self):
        """Отказ по образцу не эскалирует: задача остаётся в tests_writing,
        решения Оператора не требуется.
        
        Ловит мутацию: разработчик оформляет отказ переводом в escalated
        (как батч вопросов) — состояние станет escalated.
        """
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_WITH_ID_SAMPLE, name="test_ac.py")

        self.capture(fsm.cmd_advance, self.TASK)

        state = self.state()
        self.assertEqual(
            state, "tests_writing",
            "отказ по образцу формата идентификатора обязан оставить "
            "задачу в tests_writing (SPEC AC-4)")
        self.assertNotEqual(
            state, "escalated",
            "отказ по этому основанию не имеет права переводить задачу "
            "в escalated (SPEC AC-4)")

    def test_ac4_fixing_the_file_and_retrying_advance_succeeds_unassisted(self):
        """После починки файла повторный advance проходит сам, без
        вмешательства Оператора.
        
        Ловит мутацию: отказ оставляет блокирующее состояние (маркер,
        запись), из-за которого чистый повтор не проходит.
        """
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_WITH_ID_SAMPLE, name="test_ac.py")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(
            self.state(), "tests_writing",
            "предусловие сценария: первый advance обязан быть отклонён "
            "(SPEC AC-1) — иначе повторный advance ниже не проверяет "
            "именно путь исправления без вмешательства Оператора (SPEC "
            "AC-4)")

        # test_author правит acceptance_tests/ — тот же файл, без
        # образца формата идентификатора — и повторяет advance САМ, без
        # вмешательства Оператора (SPEC AC-4).
        self.write_acceptance_tests(AC_TEST_CLEAN, name="test_ac.py")
        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "in_dev",
            "после правки файла (убран образец формата идентификатора) "
            "повторный advance обязан пройти тем же путём, что и отказы "
            "по трассируемости AC/маркеру красноты (SPEC AC-4)")
