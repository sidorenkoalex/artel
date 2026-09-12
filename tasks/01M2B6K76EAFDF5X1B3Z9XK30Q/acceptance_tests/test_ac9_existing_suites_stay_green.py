"""Приёмочный тест AC-9 задачи 01M2B6K76EAFDF5X1B3Z9XK30Q.

Зелёный с рождения: `tests/test_auto_cycle.py` и `tests/test_fsm_autogate.py`
сегодня, до реализации этой задачи, уже зелёные (60 passed, 28 subtests
passed на момент написания) — тест фиксирует этот факт как планку,
которую реализация не имеет права уронить или ослабить, не сам по себе
проверяет ещё не написанный код. Не заменяет ревью диффа (сверка, что
файлы не ПРАВИЛИСЬ ради прохождения новых тестов, — предмет REVIEW.md,
не автоматизируемый чёрным ящиком), но красный прогон здесь — то, что
точно обязано остановить merge.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class ExistingAutoAndAutogateSuitesStayGreenTest(unittest.TestCase):

    def test_ac9_existing_auto_and_autogate_tests_pass(self):
        """`tests/test_auto_cycle.py` и `tests/test_fsm_autogate*.py`
        остаются зелёными без ослабления — ни один из них не изменён и
        не удалён ради прохождения новых тестов этой задачи (SPEC AC-9).

        Ловит мутацию: правка `orchestrator/fsm_autogate.py`,
        меняющая порядок/состав условий б/в/г/д `_autogate_conditions`
        (запрещено требованием «Не входит» SPEC) или сигнатуру,
        используемую существующими юнит-тестами `_AutogateConditionsUnitTest`,
        — прогон вернёт ненулевой код, `assertEqual` ниже поймает красноту.
        """
        result = subprocess.run(
            [sys.executable, "-m", "pytest",
             "tests/test_auto_cycle.py", "tests/test_fsm_autogate.py",
             "-p", "no:cacheprovider", "-o", "timeout=120"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=300)

        self.assertEqual(
            result.returncode, 0,
            "существующие тесты auto/автогейта обязаны остаться "
            "зелёными без ослабления (SPEC AC-9)\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
