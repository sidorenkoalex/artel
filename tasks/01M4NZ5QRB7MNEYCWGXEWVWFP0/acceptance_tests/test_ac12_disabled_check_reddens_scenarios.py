"""AC-12: мутация «проверка матрицы отключена» краснит сценарии AC-1 и AC-8 долгоживущего файла задачи.

Группа: разовый
Красен до реализации: `mandate.matrix_refusals` ещё нет — подмена `mock.patch.object` падает AttributeError.

Разовый: предмет — сам долгоживущий файл этой задачи
(`tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`) — его методы
AC-1 (канал `answer`) и AC-8 (канал `zones-extend`) прогоняются под
подменой `mandate.matrix_refusals` функцией, возвращающей пустой список;
оба обязаны покраснеть. Модуль импортируется целиком (не классы по
имени), чтобы pytest не собрал его тесты второй раз из этого файла.
"""
import unittest
from unittest import mock

from orchestrator.advance_gates import mandate
from tests import test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix as matrix_tests


def run_disabled(case: unittest.TestCase) -> unittest.TestResult:
    result = unittest.TestResult()
    with mock.patch.object(mandate, "matrix_refusals", lambda *args, **kwargs: []):
        case.run(result)
    return result


class DisabledCheckReddensTest(unittest.TestCase):

    def test_ac12_disabled_matrix_refusals_reddens_ac1_answer_and_ac8_zones_extend(self):
        """Под подменой «`matrix_refusals` всегда пуст» краснеют и AC-1 (`answer`), и AC-8 (`zones-extend`).

        Сценарий: метод AC-1 долгоживущего файла (мандат тестов без раздела
        матрицы в `escalated`/`in_dev`) и метод AC-8 (негодные матрицы
        `zones-extend`) прогоняются под подменой; каждый результат несёт
        провал (сценарий отказа создал ANSWER).

        Ловит мутацию: один из каналов проверяет форму матрицы своей копией
        мимо `mandate.matrix_refusals` — под подменой его метод остаётся
        зелёным.
        """
        cases = {
            "answer (AC-1)": matrix_tests.AnswerWithoutSectionTest(
                "test_ac1_weakening_mandate_without_section_is_refused"),
            "zones-extend (AC-8)": matrix_tests.ZonesExtendMatrixTest(
                "test_ac8_zones_extend_requires_well_formed_matrix"),
        }
        for channel, case in cases.items():
            with self.subTest(channel=channel):
                result = run_disabled(case)
                self.assertTrue(result.failures, (
                    f"{channel}: под отключённой проверкой нет провала; "
                    f"ошибки: {[text for _, text in result.errors]}"))
                self.assertEqual(result.errors, [], f"{channel}: {result.errors}")


if __name__ == "__main__":
    unittest.main()
