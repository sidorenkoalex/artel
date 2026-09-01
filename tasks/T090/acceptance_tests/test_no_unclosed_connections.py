"""AC-1 (tasks/T090/SPEC.md): полный прогон тестового набора `tests/` не
выдаёт ни одного `ResourceWarning: unclosed database` (сейчас — около
3663 таких предупреждений).

Не покрывается штатным CI-гейтом (`.github/workflows/ci.yml`, джоб
`python`, `unittest discover -s tests -v`): тот джоб гоняет тот же
набор, но проверяет только код возврата (зелёный/красный), а не текст
предупреждений в выводе — сам предмет AC-1 остался бы непроверенным без
отдельного теста здесь (в отличие от «весь набор зелёный», см.
tasks/T090/acceptance_tests/test_full_suite_regression.py).

Тяжёлый тест (гоняет весь `tests/` — свыше тысячи тестов — отдельным
подпроцессом, порядка двух минут): осознанно, буквальное прочтение
критерия «Полный прогон тестового набора `tests/`», тот же приём, что
tasks/T056/acceptance_tests/test_ac3_invariant_locked_in_test_suite.py и
tasks/T083/acceptance_tests/test_ac3_full_suite_green_with_arbitrary_branches.py.

Красен до реализации: до систематического закрытия соединений
`store.db()` полный прогон `tests/` выдаёт около 3663
`ResourceWarning: unclosed database` (эмпирически перепроверено перед
записью этого файла: 3756 на этой рабочей копии) — этот тест ловит
именно их отсутствие после реализации, не какую-то иную причину
красноты.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

WARNING_TEXT = "ResourceWarning: unclosed database"


class NoUnclosedDatabaseConnectionsTest(unittest.TestCase):

    def test_ac1_full_suite_run_has_no_unclosed_database_resourcewarning(self):
        result = subprocess.run(
            ["python3", "-m", "unittest", "discover", "-s", "tests"],
            cwd=REPO_ROOT, timeout=260, capture_output=True, text=True,
            encoding="utf-8")

        combined = result.stdout + result.stderr

        ran_match = re.search(r"^Ran (\d+) tests?", combined, re.M)
        self.assertTrue(
            ran_match and int(ran_match.group(1)) > 0,
            "прогон `tests/` не выполнил ни одного теста (сломан вызов "
            f"discover, а не предмет AC-1):\n{combined[-4000:]}")

        occurrences = combined.count(WARNING_TEXT)
        self.assertEqual(
            occurrences, 0,
            f"полный прогон `tests/` выдал {occurrences} × "
            f"«{WARNING_TEXT}» (AC-1 требует 0):\n{combined[-4000:]}")


if __name__ == "__main__":
    unittest.main()
