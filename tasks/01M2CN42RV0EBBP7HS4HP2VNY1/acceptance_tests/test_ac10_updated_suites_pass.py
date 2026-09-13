"""AC-10 задачи 01M2CN42RV0EBBP7HS4HP2VNY1: полный набор `tests/`
зелёный после переноса, включая `tests/test_canary.py` и `tests/
test_doctor_canary_pool.py` с обновлёнными путями импортов/патчей
(требование 8) и без изменения существующих ассертов.

«Полный набор `tests/` зелёный» проверяет CI/автогейт, не эта планка
(решение Оператора 05.09, скил test-authoring, «Перед завершением») —
здесь прогоняются именно эти два файла, названные SPEC поимённо как
единственные, чьи импорты/патчи трогает эта задача (та же техника, что
залоченная планка 01M1TKP08PKB87K8772H69GCXJ,
`test_ac6_existing_suite_still_green.py`, использовала для трёх файлов,
названных её SPEC поимённо).

Зелёный с рождения: `tests/test_canary.py` и `tests/test_doctor_canary_
pool.py` уже проходят целиком ДО переноса (сам перенос ещё не начат,
патчи ещё указывают на `canary`, который сегодня и несёт весь код) —
тест фиксирует это как гарантию на будущее: после переноса и правки
путей импортов/патчей на `pool_seal` (требование 8) оба файла обязаны
остаться зелёными без правки самих ассертов.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import run_unittest_modules  # noqa: E402

SUITES = ("tests.test_canary", "tests.test_doctor_canary_pool")


class UpdatedTestSuitesStillGreenTest(unittest.TestCase):

    def test_ac10_test_canary_and_test_doctor_canary_pool_pass(self):
        """Ловит мутацию: перенос сделан, но `tests/test_canary.py`/
        `tests/test_doctor_canary_pool.py` не обновлены (патчи всё ещё
        целятся в исчезнувшие атрибуты `canary.keychain`/`canary.
        _serialize_pool`/`doctor.canary.keychain` и т.п.) — файлы падают
        `AttributeError`, `returncode != 0` это поймает вместе с полным
        выводом для диагностики.
        """
        result = run_unittest_modules(*SUITES)
        self.assertEqual(
            result.returncode, 0,
            f"tests/test_canary.py и/или tests/test_doctor_canary_pool.py "
            f"упали:\n--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
