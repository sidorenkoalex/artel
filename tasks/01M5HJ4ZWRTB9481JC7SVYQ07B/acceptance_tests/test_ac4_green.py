"""AC-4: новые тесты зелёные без мутаций, соседи и линт детерминированности — без правок и зелёные.

Группа: разовый
Красен до реализации: файла tests/test_canary_parallel_protection.py ещё нет — вложенный pytest кончается кодом 4 (путь не найден).

Прогоны — вложенным pytest в рабочей копии кода задачи теми же флагами,
что у планки (`-p no:cacheprovider -p timeout`).
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import changed_paths  # noqa: E402
from _runs import (INVARIANTS, LINT_NODE, NEIGHBOURS, NEW_FILE,  # noqa: E402
                   code_root, run_pytest, tail)


class GreenWithoutMutationsTest(unittest.TestCase):

    def _assert_green(self, *targets: str) -> None:
        res = run_pytest(code_root(), *targets)
        out = res.stdout + res.stderr
        self.assertEqual(res.returncode, 0,
                         f"pytest {' '.join(targets)} — код {res.returncode}:\n"
                         f"{tail(out)}")
        self.assertIsNone(re.search(r"\d+ skipped", out),
                          f"pytest {' '.join(targets)}: есть пропущенные тесты:\n"
                          f"{tail(out)}")

    def test_ac4_new_file_green_alone(self):
        """Файл задачи отдельно — зелёный, без пропусков.

        Сценарий: `pytest tests/test_canary_parallel_protection.py` в рабочей
        копии кода; код возврата 0, пропущенных тестов нет.
        Ловит мутацию: тест AC-12 ждёт код 128 + SIGINT вместо 128 + SIGTERM
        (красен уже на коде без мутаций) или тест помечен `skipUnless` по
        платформе — прогон красен либо несёт «skipped», и тест краснеет.
        """
        self._assert_green(NEW_FILE)

    def test_ac4_new_file_green_with_neighbours_and_lint(self):
        """Файл задачи вместе с соседями и `DeterministicTestsLintTest` — зелёный.

        Сценарий: один прогон pytest по файлу задачи,
        tests/test_canary_parallel.py, tests/test_canary_run_task.py и
        `tests/test_invariants.py::DeterministicTestsLintTest`; код 0.
        Ловит мутацию: код подменённого дочернего в строковом литерале ждёт
        `time.sleep(0.1)` в цикле или файл задачи оставляет глобальное
        состояние (обработчики сигналов, `config.*`), ломающее соседей, —
        линт или сосед краснеет, и тест краснеет.
        """
        self._assert_green(NEW_FILE, *NEIGHBOURS, LINT_NODE)

    def test_ac4_neighbours_and_invariants_unchanged(self):
        """Соседние файлы тестов и tests/test_invariants.py не тронуты задачей.

        Сценарий: пути задачи по правилу гейта зон не содержат
        tests/test_invariants.py, tests/test_canary_parallel.py,
        tests/test_canary_run_task.py.
        Ловит мутацию: разработчик добавил запись `_EXCEPTIONS` в
        tests/test_invariants.py, чтобы линт пропустил ожидание в цикле, —
        путь появляется в диффе, и тест краснеет.
        """
        touched = sorted(set(changed_paths()) & {INVARIANTS, *NEIGHBOURS})
        self.assertEqual(touched, [], f"задача правит файлы без права: {touched}")


if __name__ == "__main__":
    unittest.main()
