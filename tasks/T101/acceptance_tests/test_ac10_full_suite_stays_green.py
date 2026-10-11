"""AC-10 (SPEC T101) — существующий набор тестов (`tests/`) остаётся
зелёным после изменений.

`REPO_ROOT` берётся от `__file__`, не от cwd процесса `unittest
discover` (тот же приём, что `tests/test_advance_fixation.py`
`AcceptanceRunTest`/`LockTest` — REPO_ROOT считается ОТ РАСПОЛОЖЕНИЯ
файла): на гейте этот тест запускается из worktree ветки задачи, и
`__file__` там резолвится в корень ИМЕННО этого рабочего дерева, со
всеми правками разработчика уже на месте.

Прогон — тем же приёмом, что автогейт acceptance
(`orchestrator/fsm_autogate.py::_autogate_conditions`,
`acceptance.run_full_suite`), а не отдельный `subprocess.run`: второй
способ гонять один и тот же набор не должен заводиться отдельно от
уже существующего (тот же довод, что у `acceptance.py`, требование 3 —
не плодить параллельные источники одной и той же проверки).

Зелёный с рождения: полный набор `tests/` уже зелёный до правок кода
этой задачи — тест проверяет, что fingerprint не сломал его, не то,
что задача сама его чинит.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import acceptance  # noqa: E402


class FullSuiteStaysGreenTest(unittest.TestCase):

    def test_ac10_existing_test_suite_remains_green(self):
        green, tail = acceptance.run_full_suite(REPO_ROOT)

        self.assertTrue(green, f"tests/ красный после правок T101:\n{tail}")


if __name__ == "__main__":
    unittest.main()
