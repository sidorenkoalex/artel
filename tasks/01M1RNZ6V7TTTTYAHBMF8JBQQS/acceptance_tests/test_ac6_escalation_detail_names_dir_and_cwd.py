"""Красен до реализации: сегодняшний отказ приёмки после подтяжки main
(`fsm._pull_main_or_escalate`) называет в `detail` только текст «приёмочные
тесты красные после подтяжки … (слияние сохранено, откат не выполняется)»
и хвост вывода `unittest` — ни каталог, из которого шла планка, ни `cwd`
прогона нигде не назван (SPEC AC-6). До правки задачи этот тест краснеет
отсутствием этих слов в `detail`; после правки — зеленеет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (BranchWithoutNewBehaviorSandbox,  # noqa: E402
                      MARKER_TEST_VIA_FILE)


class Ac6EscalationDetailNamesDirAndCwdTest(BranchWithoutNewBehaviorSandbox):

    def test_ac6_escalation_detail_names_directory_and_cwd_on_one_line(self):
        """Красная планка после подтяжки main называет в `detail` (одной
        строкой) и каталог, из которого шла планка, и `cwd`, с которым она
        запускалась (AC-6) — иначе разбор класса дефекта регрессии №14
        снова требует ручной раскопки кода, а не чтения журнала.

        Ловит мутацию: `detail` эскалации несёт только текст «приёмочные
        тесты красные после подтяжки …» и хвост вывода `unittest`, без
        упоминания каталога/`cwd` — строка с `cwd` не находится вовсе.
        """
        self.commit_marker_plank({"test_via_file.py": MARKER_TEST_VIA_FILE})

        self.pull()

        details = self.journal_details()
        cwd_lines = [line for detail in details
                    for line in detail.split("\n")
                    if "cwd" in line.lower()]
        self.assertTrue(
            cwd_lines,
            f"ни одна строка журнала не называет cwd прогона: {details}")
        self.assertTrue(
            any("acceptance_tests" in line for line in cwd_lines),
            f"строка с cwd обязана называть и каталог планки "
            f"(acceptance_tests/): {cwd_lines}")


if __name__ == "__main__":
    unittest.main()
