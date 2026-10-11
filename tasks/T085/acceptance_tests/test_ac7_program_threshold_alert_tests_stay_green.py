"""AC-7 (tasks/T085/SPEC.md): тесты информационных алертов порога
программы (журнал, `alerts kind=threshold`, дедуп, отсутствие
ack-обязательства — `tests/test_doctor.py`, `tests/test_multitarget.py`,
`tests/test_multitarget_invariants.py`) сохранены или обновлены и
проходят зелёными.

Прогон настоящим `python3 -m unittest` (тем же способом, что
`orchestrator/acceptance.run_full_suite`) именно этих трёх модулей —
единственный источник истины «проходят зелёными», не пересказ. Они уже
часть защищённого `tests/` (принцип целостности, ADR-0002: разработчик
не имеет права ослаблять их вне ADR) — критерий здесь в том, что после
изменений SPEC требований 1-3 их порог-специфичные классы
(`ProgramThresholdAlertTest`, `ProgramSpendTest`,
`ProgramSpendAcrossTargetsTest`) остаются зелёными, не только
структурно присутствуют.

Зелёный с рождения: эти три файла уже проходят сегодня (до кода задачи)
— удаление условия A1 из автогейта acceptance живёт в другом модуле
(`orchestrator/fsm.py::_autogate_conditions`) и не касается
`orchestrator/budget.py::check_program_spend`/`orchestrator/alerts.py`,
которые тестируют эти три файла (SPEC требование 2: алерты
информационные, не трогаются).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

MODULES = ("tests.test_doctor", "tests.test_multitarget",
          "tests.test_multitarget_invariants")


class ProgramThresholdAlertTestsStayGreenTest(unittest.TestCase):

    def test_ac7_doctor_multitarget_and_invariants_tests_pass(self):
        res = subprocess.run(
            ["python3", "-m", "unittest", *MODULES],
            cwd=config.ROOT, capture_output=True, text=True, timeout=180)

        self.assertEqual(
            res.returncode, 0,
            f"AC-7: {', '.join(MODULES)} обязаны проходить зелёными "
            f"(информационные алерты порога программы — журнал, "
            f"kind=threshold, дедуп, отсутствие ack-обязательства):\n"
            f"{res.stdout[-3000:]}\n{res.stderr[-3000:]}")


if __name__ == "__main__":
    unittest.main()
