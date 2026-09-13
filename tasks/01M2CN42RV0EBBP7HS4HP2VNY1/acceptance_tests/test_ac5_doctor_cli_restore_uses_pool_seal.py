"""AC-5 задачи 01M2CN42RV0EBBP7HS4HP2VNY1: `orchestrator/doctor/cli.py`
зовёт `doctor.pool_seal.restore_pool_if_missing(conn)` вместо
`doctor.canary.restore_pool_if_missing(conn)` (требование 4).

Поведенческий прогон `cmd_doctor(restore=True)` целиком (включая
`all_checks`/сироты/токены) уже требует стенда полного `doctor` —
такой стенд покрыт приёмочными тестами ДРУГОЙ, уже смерженной задачи
(`tasks/01M1NSR5M5THYRC0RFWPMVE2DW/acceptance_tests/`, см. докстринг
`tests/test_doctor_canary_pool.py`) и не воспроизводится здесь заново
(правило скила test-authoring: не копировать существующий стенд).
Здесь — точечная проверка места вызова источником (AST), той же
техникой, что review-checklist задач класса «рефакторинг» называет
«патчуемые имена на месте»; полное поведение переноса дополнительно
подтверждает AC-10 (повторный прогон tests/test_doctor_canary_pool.py
после правки его патчей).

Красен до реализации: `cmd_doctor` всё ещё зовёт `doctor.canary.
restore_pool_if_missing` — множество вызовов не содержит `doctor.
pool_seal.restore_pool_if_missing`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import REPO_ROOT, dotted_call_names  # noqa: E402

CLI_PATH = REPO_ROOT / "orchestrator" / "doctor" / "cli.py"


class DoctorCliRestoreCallSiteTest(unittest.TestCase):

    def test_ac5_cmd_doctor_restore_calls_pool_seal_not_canary(self):
        """Сценарий: разбираем исходник `orchestrator/doctor/cli.py`
        через `ast`, собираем множество точечных обращений-вызовов
        (`a.b.c(...)`), сверяем присутствие/отсутствие двух конкретных
        путей.

        Ловит мутацию: разработчик переносит остальные точки (artel,
        catalog, canary_pool) на `pool_seal`, но забывает именно эту —
        `doctor.pool_seal.restore_pool_if_missing` не найдётся среди
        вызовов, либо `doctor.canary.restore_pool_if_missing` останется
        среди них.
        """
        source = CLI_PATH.read_text(encoding="utf-8")
        calls = dotted_call_names(source)
        self.assertIn(
            "doctor.pool_seal.restore_pool_if_missing", calls,
            "cmd_doctor не зовёт doctor.pool_seal.restore_pool_if_missing")
        self.assertNotIn(
            "doctor.canary.restore_pool_if_missing", calls,
            "cmd_doctor всё ещё зовёт doctor.canary.restore_pool_if_missing")


if __name__ == "__main__":
    unittest.main()
