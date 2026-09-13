"""AC-6 задачи 01M2CN42RV0EBBP7HS4HP2VNY1: `orchestrator/doctor/
canary_pool.py::check_canary_pool_drift` зовёт `doctor.pool_seal.
pool_drift_warning()` вместо `doctor.canary.pool_drift_warning()`
(требование 4).

Полное поведенческое покрытие этой функции (не сходится/сходится/
чужой не-.md файл в каталоге) уже несёт `tests/test_doctor_canary_
pool.py::CanaryPoolDriftCheckTest` — здесь только точечная проверка,
что вызов ушёл именно на `pool_seal` (та же техника AST, что и AC-5);
AC-10 повторно прогоняет этот файл целиком после правки его патча
`doctor.canary.keychain` → `doctor.pool_seal.keychain`.

Красен до реализации: `check_canary_pool_drift` всё ещё зовёт `doctor.
canary.pool_drift_warning` — множество вызовов не содержит `doctor.
pool_seal.pool_drift_warning`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import REPO_ROOT, dotted_call_names  # noqa: E402

CANARY_POOL_PATH = REPO_ROOT / "orchestrator" / "doctor" / "canary_pool.py"


class DoctorCanaryPoolDriftCallSiteTest(unittest.TestCase):

    def test_ac6_check_canary_pool_drift_calls_pool_seal_not_canary(self):
        """Сценарий: разбираем исходник `orchestrator/doctor/
        canary_pool.py` через `ast`, собираем множество точечных
        вызовов, сверяем присутствие/отсутствие двух конкретных путей.

        Ловит мутацию: `check_canary_pool_drift` не поправлен и
        продолжает звать `doctor.canary.pool_drift_warning()` —
        `doctor.pool_seal.pool_drift_warning` не найдётся среди
        вызовов.
        """
        source = CANARY_POOL_PATH.read_text(encoding="utf-8")
        calls = dotted_call_names(source)
        self.assertIn(
            "doctor.pool_seal.pool_drift_warning", calls,
            "check_canary_pool_drift не зовёт doctor.pool_seal."
            "pool_drift_warning")
        self.assertNotIn(
            "doctor.canary.pool_drift_warning", calls,
            "check_canary_pool_drift всё ещё зовёт doctor.canary."
            "pool_drift_warning")


if __name__ == "__main__":
    unittest.main()
