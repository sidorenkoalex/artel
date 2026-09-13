"""AC-4 задачи 01M2CN42RV0EBBP7HS4HP2VNY1: `orchestrator/catalog.py::
cmd_init` делает ленивый импорт `pool_seal` и зовёт `pool_seal.
restore_pool_if_missing(conn)` (не `canary.restore_pool_if_missing`),
требование 4.

Красен до реализации: `orchestrator.pool_seal` ещё не существует —
`ModuleNotFoundError` при импорте. Импорт вынесен в `setUp` (не на
уровень модуля), чтобы `ModuleNotFoundError` заваливал только тест
этого файла, а не прерывал сбор всей планки (pytest без
`--continue-on-collection-errors` останавливает сбор целиком при
ошибке импорта хотя бы одного модуля теста).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog  # noqa: E402

_SENTINEL_CONN = object()


class CatalogInitUsesPoolSealTest(unittest.TestCase):

    def setUp(self):
        try:
            from orchestrator import pool_seal
        except ModuleNotFoundError as exc:
            self.fail(f"orchestrator.pool_seal не найден: {exc}")
        self.pool_seal = pool_seal

    def test_ac4_cmd_init_calls_pool_seal_restore_pool_if_missing(self):
        """Сценарий: зовём `catalog.cmd_init()` с изолированными от
        реальной БД/диска побочными эффектами (`store.db`/`create_
        schema`/`seed_task_counters`/`_deploy_role_home_reference`/
        `budget.reseed_program_spend` замоканы заглушками) и проверяем,
        что восстановление пула идёт через `pool_seal.
        restore_pool_if_missing`, получая то же соединение, что вернул
        `store.db()`.

        Ловит мутацию: `cmd_init` не переключён на ленивый импорт
        `pool_seal` (остался `from . import canary`) — подмена атрибута
        реального модуля `pool_seal` не перехватит вызов вовсе,
        `assert_called_once_with` упадёт на нулевом числе вызовов.
        """
        with mock.patch.object(catalog.store, "db",
                               return_value=_SENTINEL_CONN), \
             mock.patch.object(catalog.store, "create_schema"), \
             mock.patch.object(catalog.store, "seed_task_counters"), \
             mock.patch.object(catalog, "_deploy_role_home_reference"), \
             mock.patch.object(catalog.budget, "reseed_program_spend"), \
             mock.patch.object(self.pool_seal, "restore_pool_if_missing",
                               return_value=None) as restore_mock:
            catalog.cmd_init()

        restore_mock.assert_called_once_with(_SENTINEL_CONN)


if __name__ == "__main__":
    unittest.main()
