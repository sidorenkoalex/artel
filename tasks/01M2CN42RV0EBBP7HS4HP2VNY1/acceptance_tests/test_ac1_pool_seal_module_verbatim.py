"""AC-1 задачи 01M2CN42RV0EBBP7HS4HP2VNY1: `orchestrator/pool_seal.py`
существует и содержит все 13 функций требования 1 (`_pool_dir`,
`sealed_path`, `guids_path`, `_mac_key`, `_secret_fd`, `_hmac_tag_hex`,
`_openssl_encrypt`, `_openssl_decrypt`, `_serialize_pool`,
`_deserialize_pool`, `_authorized_pool_payload`,
`restore_pool_if_missing`, `pool_drift_warning`, `cmd_pool_seal`); их
тела дословно совпадают с телами тех же функций в
`orchestrator/canary.py` ДО переноса (перенос без изменения логики).

Красен до реализации: `orchestrator/pool_seal.py` не существует —
`importlib.import_module("orchestrator.pool_seal")` падает
`ModuleNotFoundError` на первом же тесте.
"""
import importlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import BASE_COMMIT, POOL_SEAL_NAMES, REPO_ROOT, git_show, \
    top_level_def_source  # noqa: E402

POOL_SEAL_PATH = REPO_ROOT / "orchestrator" / "pool_seal.py"


class PoolSealModuleExistsTest(unittest.TestCase):

    def test_ac1_pool_seal_module_defines_all_thirteen_names(self):
        """Сценарий: импортируем `orchestrator.pool_seal` и проверяем,
        что все 13 имён требования 1 присутствуют и вызываемы.

        Ловит мутацию: перенос забыл одну из функций (например,
        `_secret_fd` осталась только в `canary.py`, а в `pool_seal.py`
        не появилась) — `hasattr`/`callable` для этого имени не
        пройдёт.
        """
        pool_seal = importlib.import_module("orchestrator.pool_seal")
        for name in POOL_SEAL_NAMES:
            self.assertTrue(hasattr(pool_seal, name),
                            f"orchestrator.pool_seal.{name} отсутствует")
            self.assertTrue(callable(getattr(pool_seal, name)),
                            f"orchestrator.pool_seal.{name} не вызываем")


class PoolSealBodiesAreVerbatimTest(unittest.TestCase):
    """Тела всех 13 функций в `orchestrator/pool_seal.py` совпадают
    байт-в-байт с телами тех же функций в `orchestrator/canary.py` на
    коммите {BASE_COMMIT} (голова ветки задачи до правок разработчика)
    — перенос дословный, требование 1."""

    def test_ac1_each_function_body_matches_pre_transfer_canary_source(self):
        """Сценарий: для каждого из 13 имён сравниваем точный исходный
        текст (включая декораторы/докстринги/комментарии внутри тела) в
        `pool_seal.py` с тем же именем в `canary.py` на коммите-базе
        задачи.

        Ловит мутацию: перенос попутно правит тело (переформатировал
        строку, поправил опечатку в комментарии, снял декоратор
        `@contextmanager` у `_secret_fd`, поменял местами ветки условия)
        — построчное сравнение разойдётся хотя бы на одну функцию.
        """
        base_source = git_show("orchestrator/canary.py", BASE_COMMIT)
        pool_seal_source = POOL_SEAL_PATH.read_text(encoding="utf-8")

        mismatches = []
        for name in POOL_SEAL_NAMES:
            before = top_level_def_source(base_source, name)
            self.assertIsNotNone(
                before, f"{name} не найдена в canary.py на {BASE_COMMIT} — "
                        f"ошибка самой планки/базового коммита")
            after = top_level_def_source(pool_seal_source, name)
            if after is None:
                mismatches.append(f"{name}: отсутствует в pool_seal.py")
            elif after != before:
                mismatches.append(f"{name}: тело отличается от исходного")

        self.assertFalse(mismatches, "; ".join(mismatches))


if __name__ == "__main__":
    unittest.main()
