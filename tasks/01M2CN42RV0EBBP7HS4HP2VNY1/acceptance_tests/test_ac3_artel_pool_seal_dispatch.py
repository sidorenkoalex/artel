"""AC-3 задачи 01M2CN42RV0EBBP7HS4HP2VNY1: `orchestrator/artel.py::
_cmd_canary` вызывает `pool_seal.cmd_pool_seal()` (не
`canary.cmd_pool_seal()`) для подкоманды `pool-seal` (требование 4).

Красен до реализации: `artel.py` импортирует только `canary` (не
`pool_seal`) — `artel.pool_seal` падает `AttributeError` на первом же
обращении внутри теста.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artel  # noqa: E402


class ArtelPoolSealDispatchTest(unittest.TestCase):

    def test_ac3_pool_seal_subcommand_calls_pool_seal_module(self):
        """Сценарий: `artel.py canary pool-seal` разбирается
        `_cmd_canary(["pool-seal"])` — проверяем, что вызывается ровно
        `pool_seal.cmd_pool_seal()` без аргументов.

        Ловит мутацию: `_cmd_canary` не поправлен и продолжает звать
        `canary.cmd_pool_seal()` — подмена `artel.pool_seal.
        cmd_pool_seal` не перехватит вызов вовсе, `assert_called_once_
        with` упадёт на нулевом числе вызовов.
        """
        with mock.patch.object(artel.pool_seal, "cmd_pool_seal") as psc:
            artel._cmd_canary(["pool-seal"])
        psc.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
