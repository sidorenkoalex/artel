"""AC-17 (SPEC.md): существующий набор тестов (`tests/`) остаётся
зелёным после изменений.

Отдельный процесс (`subprocess`), не `unittest.TestLoader` в этом же
интерпретаторе (тот приём — `tasks/T065/acceptance_tests/
test_ac5_invariant_tests_stay_green.py` — годится для ИМЕНОВАННЫХ
классов; здесь критерий называет весь каталог `tests/` целиком, без
перечисления конкретных тестов, а `unittest discover` внутри уже
идущего `discover` рискует посчитать тесты дважды/спутать sys.path
этой же песочницы с корневым `tests/`, отдельный процесс с чистым
`sys.path` — самый прямой способ проверить буквально «`tests/`
зелёный», без лишних приёмов изоляции).

Зелёный с рождения: этот тест не про код задачи 01M1NEEWH5K1XPFRDGRMPYSBXJ
(которого ещё нет), а про то, что её код (когда появится) не сломает
уже существующий набор `tests/`. Он проходит уже сегодня, на пустой
ветке до всякой реализации, и обязан продолжать проходить после неё —
красноту здесь создал бы только сам факт поломки существующих тестов
изменениями этой задачи, не отсутствие её кода.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class ExistingTestsStayGreenTest(unittest.TestCase):

    def test_ac17_tests_directory_passes_in_a_clean_subprocess(self):
        res = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=1800)
        self.assertEqual(
            res.returncode, 0,
            f"`python3 -m unittest discover -s tests` завершился с кодом "
            f"{res.returncode} — существующий набор тестов не зелёный:\n"
            f"--- stdout ---\n{res.stdout[-4000:]}\n"
            f"--- stderr ---\n{res.stderr[-4000:]}")


if __name__ == "__main__":
    unittest.main()
