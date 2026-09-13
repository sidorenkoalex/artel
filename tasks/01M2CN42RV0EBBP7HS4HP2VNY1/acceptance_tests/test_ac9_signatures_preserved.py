"""AC-9 задачи 01M2CN42RV0EBBP7HS4HP2VNY1: сигнатуры `cmd_canary`,
`cmd_pool_seal`, `restore_pool_if_missing`, `pool_drift_warning` не
изменились относительно состояния до переноса (требование 6) — три
последних сверяются в `orchestrator.pool_seal` (новое место жительства
после переноса), `cmd_canary` остаётся в `orchestrator.canary`.

Ожидаемые строки сигнатур сняты `inspect.signature` с `orchestrator/
canary.py` на коммите-базе задачи (812c9064, до какого-либо переноса) —
зафиксированы литералом ниже, не вычисляются заново из текущего кода
(иначе тест ничего бы не проверял: сравнивал бы код сам с собой).

Красен до реализации: `orchestrator.pool_seal` не существует —
`ModuleNotFoundError` на первом обращении к нему.
"""
import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import canary  # noqa: E402

# Сняты `str(inspect.signature(...))` с orchestrator/canary.py на
# коммите 812c9064edd802bc64546a209742df550c586892 (ГОЛОВА ветки задачи
# до правок разработчика).
EXPECTED_CMD_CANARY = "(*, k: int, sha: str | None = None) -> None"
EXPECTED_POOL_SEAL = {
    "cmd_pool_seal": "() -> None",
    "restore_pool_if_missing": "(conn) -> str | None",
    "pool_drift_warning": "() -> str | None",
}


class SignaturesPreservedTest(unittest.TestCase):

    def test_ac9_cmd_canary_signature_unchanged_in_canary_module(self):
        """Ловит мутацию: перенос попутно меняет сигнатуру `cmd_canary`
        (например, снимает `*`-разделитель keyword-only или тип
        `sha`) — сравнение строкового представления `inspect.signature`
        разойдётся с зафиксированным до переноса значением.
        """
        self.assertEqual(str(inspect.signature(canary.cmd_canary)),
                         EXPECTED_CMD_CANARY)

    def test_ac9_pool_seal_function_signatures_unchanged_after_move(self):
        """Ловит мутацию: перенос `cmd_pool_seal`/`restore_pool_if_
        missing`/`pool_drift_warning` в `pool_seal.py` попутно меняет
        сигнатуру одной из трёх (например, добавляет параметр `*,
        audit_conn=None` там, где раньше его не было) — сравнение
        разойдётся с зафиксированным до переноса значением для этого
        имени.
        """
        from orchestrator import pool_seal
        for name, expected in EXPECTED_POOL_SEAL.items():
            actual = str(inspect.signature(getattr(pool_seal, name)))
            self.assertEqual(actual, expected,
                             f"сигнатура pool_seal.{name} изменилась при "
                             f"переносе: {actual!r} != {expected!r}")


if __name__ == "__main__":
    unittest.main()
