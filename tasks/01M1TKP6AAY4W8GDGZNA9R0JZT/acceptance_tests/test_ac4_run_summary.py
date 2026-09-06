"""AC-4 (SPEC.md, требование 2): `orchestrator.amend._run_summary()`
разбирает итог обязательного прогона по СВОДКЕ pytest («N passed in
Xs»/«M failed, N passed in Xs»), не по строке unittest «Ran N tests…
OK/FAILED»; сводка не найдена в хвосте — возвращается хвост как есть.

Красен до реализации: `_RUN_SUMMARY` (`orchestrator/amend.py`, не все
четыре теста файла — см. ниже; проверено прогоном) всё ещё несёт
unittest-регулярку (`r"Ran \\d+
tests? in [\\d.]+s..."`) — на реалистичном pytest-хвосте (со строкой-
разделителем `====`, как реально печатает pytest, см.
`test_ac1_ac2_run.py`) она не находит совпадения, `_run_summary` уходит
в fallback «весь хвост как есть»; `test_ac4_extracts_all_passed_summary_line`
и `test_ac4_extracts_failed_and_passed_counts` падают на `assertEqual`,
ожидая ИМЕННО извлечённую короткую сводку, а не полный хвост целиком.
`test_ac4_missing_summary_falls_back_to_full_tail` и
`test_ac4_ok_only_output_still_falls_back_when_not_pytest_style` УЖЕ
зелёные на текущем коде — контроль: fallback «нет совпадения — весь
хвост как есть» одинаково срабатывает что для старой, что для новой
регулярки на хвосте, который не совпадает НИ с одной из них.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import amend  # noqa: E402

PASSING_TAIL = (
    "планка: /tmp/tasks/T001/acceptance_tests, cwd: /tmp/code\n"
    "============================= test session starts "
    "==============================\n"
    "collected 5 items\n\n"
    "test_ac.py .....                                                    "
    "[100%]\n\n"
    "============================== 5 passed in 0.42s "
    "===============================\n")

FAILING_TAIL = (
    "планка: /tmp/tasks/T001/acceptance_tests, cwd: /tmp/code\n"
    "============================= test session starts "
    "==============================\n"
    "collected 5 items\n\n"
    "test_ac.py F....                                                    "
    "[100%]\n\n"
    "=================================== FAILURES "
    "===================================\n"
    "____________________________ test_ac1_first _____________________________\n"
    "AssertionError: намеренно красный тест без маркера\n\n"
    "=========================== short test summary info "
    "===========================\n"
    "FAILED test_ac.py::test_ac1_first - AssertionError: намеренно...\n"
    "========================= 1 failed, 4 passed in 0.31s "
    "=========================\n")


class RunSummaryPytestTest(unittest.TestCase):

    def test_ac4_extracts_all_passed_summary_line(self):
        """Из реалистичного зелёного pytest-хвоста извлекается ровно
        итоговая строка `N passed in Xs`, без предшествующих строк
        session-заголовка и прогресс-точек.

        Ловит мутацию: регулярка не обновлена под pytest (осталась
        искать «Ran … OK») — совпадения нет, возвращается ВЕСЬ хвост
        (несколько строк), `assertEqual` с однострочным ожиданием
        откажет.
        """
        summary = amend._run_summary(PASSING_TAIL)
        self.assertEqual(summary, "5 passed in 0.42s")

    def test_ac4_extracts_failed_and_passed_counts(self):
        """Из красного pytest-хвоста извлекается итоговая строка с числом
        упавших И прошедших тестов (`M failed, N passed in Xs`), без
        текста конкретного traceback'а/AssertionError.

        Ловит мутацию: регулярка захватывает блок FAILURES целиком
        (например, `.*` до конца хвоста) вместо только итоговой строки —
        `assertNotIn("AssertionError", ...)` откажет вместе с
        `assertEqual` на короткую сводку.
        """
        summary = amend._run_summary(FAILING_TAIL)
        self.assertEqual(summary, "1 failed, 4 passed in 0.31s")
        self.assertNotIn("AssertionError", summary)
        self.assertNotIn("FAILURES", summary)

    def test_ac4_missing_summary_falls_back_to_full_tail(self):
        """Хвост, не похожий на вывод pytest (регулярка не находит
        совпадения — вывод truncated иначе, чем ожидается), возвращается
        целиком, без потери диагностики — тот же принцип, что и раньше
        для формата unittest.

        Ловит мутацию: fallback убран или заменён на пустую строку/
        исключение при отсутствии совпадения.
        """
        tail = "стектрейс субпроцесса, обрезанный посередине без сводки"
        self.assertEqual(amend._run_summary(tail), tail)

    def test_ac4_ok_only_output_still_falls_back_when_not_pytest_style(self):
        """Старый unittest-формат («Ran N tests… OK»), случайно оставшийся
        где-то в хвосте (например, вложенный лог другого процесса), не
        распознаётся НОВОЙ pytest-регуляркой как сводка — возвращается
        весь хвост, а не обрезок по старому формату.

        Ловит мутацию: реализация оставляет ОБЕ регулярки (unittest И
        pytest) в попытке угодить обоим форматам — на чисто unittest-
        подобном хвосте она молча вернула бы старую unittest-сводку
        вместо честного fallback, маскируя то, что реальный прогон
        (pytest) никогда не производит такой хвост.
        """
        tail = "Ran 3 tests in 0.002s\n\nOK\n"
        self.assertEqual(amend._run_summary(tail), tail.strip())


if __name__ == "__main__":
    unittest.main()
