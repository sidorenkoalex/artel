"""AC-7 задачи 01M2CN42RV0EBBP7HS4HP2VNY1: `orchestrator/doctor/
__init__.py` импортирует `pool_seal` наряду с `canary` в общем списке
импортов пакета `orchestrator`, так что `doctor.pool_seal.<имя>`
разрешается тем же путём, что и `doctor.canary.<имя>` сегодня
(требование 4).

Красен до реализации: `doctor/__init__.py` не импортирует `pool_seal`
— `doctor.pool_seal` падает `AttributeError`.
"""
import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import doctor  # noqa: E402


class DoctorFacadeExportsPoolSealTest(unittest.TestCase):

    def test_ac7_doctor_pool_seal_attribute_is_the_real_module(self):
        """Сценарий: сверяем, что фасад `doctor` несёт атрибут
        `pool_seal`, и что это ИМЕННО модуль `orchestrator.pool_seal`
        (не одноимённая заглушка/копия) — тем же способом, каким
        `doctor.canary` сегодня разрешается атрибутом фасада (докстринг
        `doctor/__init__.py`: «единственное место, где коллаборанты...
        импортируются напрямую»).

        Ловит мутацию: `pool_seal` добавлен в докстринг-комментарий, но
        не в реальный кортеж `from .. import (...)` — `hasattr` не
        пройдёт; либо фасад создаёт локальную переменную `pool_seal`,
        указывающую на что-то другое (не модуль) — `assertIs` это
        поймает.
        """
        expected = importlib.import_module("orchestrator.pool_seal")
        self.assertTrue(
            hasattr(doctor, "pool_seal"),
            "doctor.pool_seal отсутствует — фасад не импортирует "
            "pool_seal наряду с canary")
        self.assertIs(doctor.pool_seal, expected)


if __name__ == "__main__":
    unittest.main()
