"""AC-4 (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md): «Разбор тестовых
файлов и AC-маркеров команда получает через
scripts/guard.py::scan_acceptance_tests (либо разбирающее его ядро
scan_ac_content над содержимым, прочитанным с ветки) — без собственной
параллельной реализации того же разбора.»

Патчатся ОБА варианта пути делегирования, названные критерием
(`scan_acceptance_tests` и его ядро `scan_ac_content`), атрибутом
модуля `scripts.guard` — установленная и единообразная конвенция всей
кодовой базы (все 7 сегодняшних вызывателей, включая
`orchestrator/acceptance.py` и `orchestrator/fsm.py`, делают `from
scripts import guard` и зовут `guard.scan_acceptance_tests(...)`
атрибутом, не `from scripts.guard import scan_acceptance_tests`) —
патч атрибута модуля увидит любой код, написанный в этом же стиле.

Фикстура ниже намеренно не несёт ни одного `test_ac<n>_...`-метода и ни
одного `# AC-n: ...`-маркера (та же осторожность, что `tasks/T081/
acceptance_tests/test_ac1_non_test_files_excluded.py`, коммит 7cb7e25):
`guard.scan_acceptance_tests` читает сырой текст `.py`-файлов регуляркой
— такой литерал в исходнике ЭТОГО файла читался бы как настоящее
покрытие/пометка задачи 01M1GJ3ZP1YGG5QRB6FQ44NN8D (класс дефекта
ANSWER-1, 31.08). Критерию AC-4 не нужен реалистичный AC-маркер в
фикстуре — важно только, что её содержимое НЕ совпадает с сентинелом.

Красен до реализации: `_sandbox.discover_dry_run_command_name()` падает
`AssertionError` — новой команды в таблице диспетчера ещё нет.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import guard  # noqa: E402

from _sandbox import DryRunSandbox  # noqa: E402

REAL_TEST_FILE = '''"""Фикстура — реальное содержимое не должно совпадать с сентинелом.

Зелёный с рождения: файл-фикстура другой задачи, не код 01M1GJ3ZP1YGG5QRB6FQ44NN8D.
"""
import unittest


class RealFixtureTest(unittest.TestCase):

    def test_ordinary_method(self):
        """Фикстура."""
        pass
'''

AC_SECTION = "AC-1. Обычный критерий.\nAC-2. Обычный критерий.\n"

SENTINEL_AC = 777777
SENTINEL_REASON = "SENTINEL-DELEGATION-PROOF-4b6c1"
SENTINEL_TESTED = {888888}


class ReusesGuardScanTest(DryRunSandbox):

    def test_ac4_output_reflects_patched_guard_return_value(self):
        """`scripts.guard.scan_acceptance_tests`/`scan_ac_content`
        подменены на сентинельный результат, не связанный с реальным
        содержимым фикстуры (AC-777777 с уникальной причиной,
        "покрытый тестом" AC-888888 — числа заведомо не встречаются ни
        в фикстуре, ни в разумной собственной реализации разбора).
        Вывод обязан нести эти сентинельные значения — иначе он получен
        НЕ через `guard`, а собственным (пусть и похожим) разбором.

        Ловит мутацию: команда реализует свой собственный regex/парсер
        AC-маркеров и тестовых методов вместо вызова `guard.
        scan_acceptance_tests`/`scan_ac_content` — тогда патч этих
        функций не повлияет на вывод, сентинельные значения (777777,
        888888, SENTINEL-DELEGATION-PROOF-4b6c1) не появятся, хотя
        реальные тестовые файлы ветки они переживут (собственный парсер
        разберёт их напрямую, а не через подменённый `guard`).
        """
        self.commit_fixture(AC_SECTION, {"test_real.py": REAL_TEST_FILE})
        self.seed_task()

        sentinel_markers = {SENTINEL_AC: ("manual", SENTINEL_REASON)}
        with mock.patch.object(
                guard, "scan_acceptance_tests",
                return_value=(SENTINEL_TESTED, sentinel_markers)), \
             mock.patch.object(
                guard, "scan_ac_content",
                return_value=(SENTINEL_TESTED, sentinel_markers)):
            out = self.run_dry_run()

        self.assertIn(str(SENTINEL_AC), out,
                     "сентинельный AC-номер из подменённого guard "
                     "отсутствует в выводе — разбор не идёт через "
                     "scripts.guard")
        self.assertIn(SENTINEL_REASON, out,
                     "сентинельная причина из подменённого guard "
                     "отсутствует в выводе — разбор не идёт через "
                     "scripts.guard")


if __name__ == "__main__":
    unittest.main()
