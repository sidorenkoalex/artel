"""AC-3 (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md): «Команда печатает
сводку трассируемости: для каждого AC из SPEC — покрыт тестом, покрыт
пометкой, или не покрыт; непокрытые AC названы явно (номерами).»

Маркерная строка и имена тестовых методов фикстуры ниже собраны
конкатенацией, не литералом (та же осторожность, что `tasks/T081/
acceptance_tests/test_ac1_non_test_files_excluded.py`, коммит 7cb7e25):
`guard.scan_acceptance_tests` читает сырой текст `.py`-файлов регуляркой
— сплошной кусок текста «def, test_ac, 4, метод» или «решётка, AC, 2,
двоеточие, manual» в исходнике ЭТОГО файла читался бы как настоящее
покрытие/пометка задачи 01M1GJ3ZP1YGG5QRB6FQ44NN8D (класс дефекта
ANSWER-1, 31.08; здесь тем более коварно — AC-4 существует и в этой
самой SPEC.md). Конкатенация
ломает регулярку в исходнике; после вычисления f-строки в СОДЕРЖИМОЕ
фикстурного файла (которое реально уходит в git-коммит ветки-фикстуры
T900/T901) попадает целый, корректный текст.

Красен до реализации: `_sandbox.discover_dry_run_command_name()` падает
`AssertionError` — новой команды в таблице диспетчера ещё нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import DryRunSandbox  # noqa: E402

METHOD_NAME_AC1 = "test_ac" + "1_covered_by_test"
METHOD_NAME_AC4 = "test_ac" + "4_covered_by_test"
MARKER_LINE_AC2 = "# AC-" + "2: manual — покрыт пометкой"

TEST_FILE = f'''"""Фикстура трассируемости.

Зелёный с рождения: файл-фикстура другой задачи, не код 01M1GJ3ZP1YGG5QRB6FQ44NN8D.
"""
import unittest

{MARKER_LINE_AC2}


class TraceabilityFixtureTest(unittest.TestCase):

    def {METHOD_NAME_AC1}(self):
        """Фикстура — AC-1 покрыт тестом."""
        pass
'''

# Критерии фикстуры: AC-1 покрыт тестом, AC-2 покрыт пометкой, AC-4 не
# покрыт ничем (числа без двоеточия сразу после — не формат AC_MARKER).
AC_SECTION = (
    "AC-1. Критерий, покрытый тестом.\n"
    "AC-2. Критерий, покрытый пометкой.\n"
    "AC-4. Критерий, не покрытый ничем.\n"
)


class TraceabilitySummaryTest(DryRunSandbox):

    def test_ac3_uncovered_ac_is_named_explicitly_by_number(self):
        """SPEC фикстуры несёт три критерия: AC-1 (тест), AC-2 (пометка),
        AC-4 (ничего). Сводка обязана явно назвать номер непокрытого
        AC-4 в выводе.

        Ловит мутацию: реализация считает «покрыт» = «есть хоть один
        тестовый метод или пометка ГДЕ УГОДНО в файле», без сверки с
        конкретным номером AC-4 — тогда AC-4 никогда бы не попал в
        список непокрытых, хотя по факту не покрыт. Тест ищет "AC-4"
        как отдельный номер и падает, если сводка о нём молчит.
        """
        self.commit_fixture(AC_SECTION, {"test_trace.py": TEST_FILE})
        self.seed_task()

        out = self.run_dry_run()

        self.assertIn("AC-4", out,
                     "непокрытый AC-4 не назван явно в сводке")

    def test_ac3_summary_block_changes_when_the_gap_is_closed(self):
        """Дифференциальная проверка: две независимые фикстуры-задачи,
        отличающиеся ТОЛЬКО тем, что во второй AC-4 дополнительно покрыт
        тестом. Формат сводки — решение разработчика (SPEC требование 1
        общего порядка, конкретный текст не задан), поэтому тест не
        завязывается на конкретную формулировку «не покрыт» — вместо
        этого сравнивает кусок вывода вокруг "AC-4" между двумя
        прогонами: он обязан отличаться, раз реальное состояние
        покрытия AC-4 отличается.

        Ловит мутацию: сводка трассируемости строится ТОЛЬКО из статичного
        текста SPEC (список номеров AC-n) и не сверяется с фактическим
        покрытием (`tested`/`markers`) — тогда блок вокруг "AC-4" был бы
        побайтово одинаков в обоих прогонах, хотя один сценарий добавляет
        покрывающий тест, а другой нет.
        """
        gap_task = "T900"
        closed_task = "T901"
        self.commit_fixture(AC_SECTION, {"test_trace.py": TEST_FILE},
                           branch="task/t900-gap", task_id=gap_task)
        self.seed_task(task_id=gap_task, branch="task/t900-gap")

        closed_test_file = TEST_FILE.replace(
            f"{METHOD_NAME_AC1}(self):",
            f'{METHOD_NAME_AC4}(self):\n'
            '        """Фикстура — AC-4 тоже покрыт тестом."""\n'
            '        pass\n\n'
            f'    {METHOD_NAME_AC1}(self):')
        self.commit_fixture(AC_SECTION, {"test_trace.py": closed_test_file},
                           branch="task/t901-closed", task_id=closed_task)
        self.seed_task(task_id=closed_task, branch="task/t901-closed")

        out_gap = self.run_dry_run(task_id=gap_task)
        out_closed = self.run_dry_run(task_id=closed_task)

        block_gap = self._block_after(out_gap, "AC-4")
        block_closed = self._block_after(out_closed, "AC-4")
        self.assertNotEqual(
            block_gap, block_closed,
            "блок сводки вокруг AC-4 не изменился, хотя во втором "
            "сценарии AC-4 дополнительно покрыт тестом — сводка не "
            "сверяется с фактическим покрытием")

    @staticmethod
    def _block_after(text: str, label: str) -> str:
        idx = text.find(label)
        assert idx != -1, f"{label} не найден в выводе вовсе"
        rest = text[idx + len(label):]
        next_idx = rest.find("AC-")
        return rest if next_idx == -1 else rest[:next_idx]


if __name__ == "__main__":
    unittest.main()
