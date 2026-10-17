"""Мутация «отчёт о таймауте печатает значение config, а не N» — целевой тест
краснеет.

Группа: разовый
Зелёный с рождения: утверждения :620 (N в строке «не уложился») и :621-622 (нет значения config копии) на main уже ловят такую мутацию; планка держит, что правка задачи их не обезвредит.

Мутация вносится во временную копию рабочей копии кода (`_mutant.py`):
в `render` копии `orchestrator/suite_run.py` число строки «не уложился»
берётся из `config.FULL_SUITE_TIMEOUT_SEC`, а не из переданного предела.
Немутированный целевой тест в такой же копии обязан быть зелёным.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mutant  # noqa: E402

TITLE = 'f"прогон не уложился в предел {seconds} с "'
MUTANT = 'f"прогон не уложился в предел {config.FULL_SUITE_TIMEOUT_SEC} с "'


class ReportTextMutationTest(unittest.TestCase):

    def test_ac7_report_printing_config_value_turns_target_red(self):
        """Строка «не уложился» с числом config — целевой тест красен.

        Сценарий: немутированный целевой тест в копии зелёный; в копии с
        мутацией `render` (обрыв по-прежнему по N, число в строке — 60 из
        `config.py` копии) целевой тест красен.

        Ловит мутацию: правка задачи ослабляет утверждения о числе в строке
        «не уложился» (например, проверяет N по всему отчёту, а не в той же
        строке, или снимает проверку значения config) — отчёт с 60 проходит,
        целевой тест зелёный, метод красен.
        """
        baseline = _mutant.instrumented_run()
        self.assertTrue(baseline.green, baseline.context(
            "немутированный целевой тест не зелёный"))
        run = _mutant.mutated_run((_mutant.SUITE_RUN_REL, TITLE, MUTANT))
        self.assertFalse(run.green, run.context(
            "мутация «отчёт печатает значение config» выжила"))


if __name__ == "__main__":
    unittest.main()
