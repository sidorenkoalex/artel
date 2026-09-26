"""AC-5 и AC-6 (tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md): область узла —
`tests/**` на любой глубине, но НЕ `tasks/*/acceptance_tests/**`; файл под
`tests/`, у которого в base ноль тестовых методов, находкой не считается.

Красен до реализации: обёртки `_test_integrity_gate_refuses` в
`orchestrator/fsm_advance.py` (требование 6) ещё нет — вызов падает
`AttributeError` на каждом сценарии, включая те два, чьё ожидание —
«отказа нет» (до реализации они краснеют не «зелёным ожиданием», а тем же
отсутствием обёртки).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import OTHER_TASK, REFUSAL_ACTION, TestIntegritySandbox  # noqa: E402


class NestedTestsPathTest(TestIntegritySandbox):

    def test_ac5_finding_in_nested_tests_path_refuses(self):
        """Удалён `tests/deep/test_nested.py` — файл ВТОРОГО уровня под
        `tests/`: гейт отказывает так же, как на файле верхнего уровня.

        Ловит мутацию: область узла скопирована у гейта заявки мутации
        (`f.startswith("tests/test_") and f.count("/") == 1`, orchestrator/
        advance_gates/review.py) — тест, заведённый в подкаталоге, можно
        удалить мимо рубежа, хотя полный набор (`pytest tests`,
        `acceptance.run_full_suite`) его собирает наравне с верхним
        уровнем.
        """
        self.remove("tests/deep/test_nested.py")
        self.commit()

        outcome = self.run_gate()

        self.assertTrue(outcome.refused,
                        f"гейт обязан отказать; журнал: {outcome.journal}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn("tests/deep/test_nested.py", outcome.detail)


class ForeignPlankOutOfScopeTest(TestIntegritySandbox):

    def test_ac5_task_acceptance_tests_are_out_of_scope(self):
        """Удалён файл планки приёмки ПОСТОРОННЕЙ задачи
        (`tasks/<id>/acceptance_tests/test_plank.py`) — этим гейтом он не
        рассматривается, отказа нет: планку держит лок, а не этот рубеж.

        Ловит мутацию: область расширена до «любой `*.py` с тестовыми
        методами в диффе» без исключения `tasks/*/acceptance_tests/` —
        штатная материализация и пересборка планок начинает отказывать
        переходу, а лок планки получает второго, несогласованного с ним
        хозяина.
        """
        self.remove(f"tasks/{OTHER_TASK}/acceptance_tests/test_plank.py")
        self.commit()

        outcome = self.run_gate()

        self.assertFalse(
            outcome.refused,
            f"планка приёмки — не область этого гейта (AC-5); "
            f"журнал: {outcome.journal}")
        self.assertNotIn(REFUSAL_ACTION, outcome.actions, outcome.journal)


class FileWithoutTestMethodsTest(TestIntegritySandbox):

    def test_ac6_deleted_file_without_test_methods_is_not_a_finding(self):
        """Удалён `tests/helpers_without_tests.py` — файл под `tests/`, у
        которого в base ноль тестовых методов: защиты в нём нет, находкой
        удаление не считается, переход этим гейтом не отклонён.

        Ловит мутацию: находка (а) заводится по одному факту «путь под
        `tests/` исчез», без разбора содержимого base — уборка помощника,
        `__init__.py` или опустевшего после законного переезда тестов
        файла начинает требовать мандата Оператора без предмета
        (требование 5).
        """
        self.remove("tests/helpers_without_tests.py")
        self.commit()

        outcome = self.run_gate()

        self.assertFalse(
            outcome.refused,
            f"файл без тестовых методов в base находкой не считается "
            f"(AC-6); журнал: {outcome.journal}")
        self.assertNotIn(REFUSAL_ACTION, outcome.actions, outcome.journal)


if __name__ == "__main__":
    unittest.main()
