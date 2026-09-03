"""AC-7 (tasks/01M1KT0792125J9ZNJNZJ86E9Q/SPEC.md): «Полный набор `tests/`
зелёный; приёмочные тесты A7 (`tasks/01M1H224X5A8W159MKF1Q24R5Y/
acceptance_tests`, 44) зелёные».

Зелёный с рождения: и `tests/`, и приёмочные тесты A7 уже проходят
СЕГОДНЯ, до правки строк из «Материалы» этой SPEC (`runner.py`/
`answer.py`/`checkpoint.py`) — эта задача ничего в них не меняет, только
проверяет отсутствие регрессии от своих будущих правок. Это не тавтология
с автогейтом `orchestrator/fsm_autogate.py::_autogate_conditions`
(который на входе в `acceptance` прогоняет ТОЛЬКО `tests/` в worktree
КОДОВОЙ ветки этой задачи — каталог `tasks/01M1H224.../acceptance_tests`
не под `tests/`, тем автогейтом не задет вовсе): вторая половина критерия
(44 теста A7, которые как раз плотно бьют по `runner.py`/`checkpoint.py`/
`artifact_branch.py` — файлы, которые эта задача правит) не проверена ни
одним существующим автоматическим гейтом.
"""
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

A7_ACCEPTANCE_TESTS = _REPO_ROOT / "tasks/01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests"


def _discover(start_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(start_dir), "-q"],
        cwd=_REPO_ROOT, capture_output=True, text=True, timeout=600)


class FullSuiteGreenTest(unittest.TestCase):

    def test_ac7_tests_directory_is_fully_green(self):
        """Полный набор `tests/` пульта (`python3 -m unittest discover -s
        tests`) заканчивается кодом возврата 0 — буквальный первый пункт
        AC-7.

        Ловит мутацию: любую правку `runner.py`/`answer.py`/
        `checkpoint.py` по этой SPEC, которая ломает существующее
        поведение (например, начинает искать TZ.md ТОЛЬКО в артефактной
        ветке, теряя фоллбэк на кодовую — регрессия на AC-2/`tests/
        test_analyst_role.py::RunWithoutAgentTest`) — прогон вернётся
        ненулевым кодом.
        """
        res = _discover(_REPO_ROOT / "tests")

        self.assertEqual(
            res.returncode, 0,
            f"tests/ не зелёный:\n{(res.stdout + res.stderr)[-4000:]}")

    def test_ac7_a7_acceptance_tests_are_still_green(self):
        """Приёмочные тесты A7 (`tasks/01M1H224X5A8W159MKF1Q24R5Y/
        acceptance_tests`, 44 штуки — планка, залоченная по conventions-
        core) остаются зелёными после правок этой задачи в
        `runner.py`/`checkpoint.py`/`artifact_branch.py`, которые они
        плотно проверяют.

        Ловит мутацию: правка `checkpoint._commit_external_step_
        artifacts`, устраняющая AC-6 этой SPEC ценой поломки уже
        залоченного поведения A7 (например, забывающая убрать
        `tasks/<id>/` из рабочего каталога роли после коммита, что
        проверяет `tasks/01M1H224.../acceptance_tests/
        test_ac7_full_scenario_no_pult_writes.py` и смежные) — эти 44
        теста покраснели бы.
        """
        res = _discover(A7_ACCEPTANCE_TESTS)

        self.assertEqual(
            res.returncode, 0,
            f"приёмочные тесты A7 не зелёные:\n{(res.stdout + res.stderr)[-4000:]}")


if __name__ == "__main__":
    unittest.main()
