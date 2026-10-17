"""Серия 50 прогонов целевого теста под нагрузкой записана в PLAN.md.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан — `artifact_text("PLAN.md")` даёт None.

Сама серия (50 × целевой тест под `os.cpu_count()` процессами нагрузки)
не помещается в предел времени одного теста планки; планка держит запись
серии в PLAN.md — команду, число ядер и итог 50/50, — а свойство
«исход не зависит от нагрузки» детерминированно проверяет AC-2
(`test_ac2_starved_probe.py`). PLAN.md читается из ссылки документов
задачи помощником пульта.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mutant  # noqa: E402
from _pult import artifact_text  # noqa: E402


class LoadSeriesRecordTest(unittest.TestCase):

    def test_ac8_plan_records_command_cores_and_fifty_of_fifty(self):
        """PLAN.md называет команду серии, нагрузку, число ядер и итог 50/50.

        Сценарий: в PLAN.md задачи есть итог «50/50», nodeid целевого метода
        в команде прогона `pytest`, нагрузка `while True: pass` и число ядер
        (`os.cpu_count()`/«ядер» с числом).

        Ловит мутацию: разработчик прогнал серию без нагрузки или не записал
        её (в PLAN нет «while True: pass» либо итога 50/50) — метод красен.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет")
        self.assertRegex(plan, r"(?<!\d)50\s*/\s*50(?!\d)",
                         "в PLAN.md нет итога 50/50")
        self.assertIn(_mutant.TARGET_METHOD, plan,
                      "в PLAN.md нет nodeid целевого метода в команде серии")
        self.assertIn("pytest", plan, "в PLAN.md нет команды pytest серии")
        self.assertIn("while True: pass", plan,
                      "в PLAN.md нет команды нагрузки «while True: pass»")
        self.assertRegex(
            plan, r"(?i)(cpu_count|ядер|ядра|ядро|cores?)\D{0,40}\d+"
                  r"|\d+\s*(ядер|ядра|ядро|cores?)",
            "в PLAN.md не названо число ядер")


if __name__ == "__main__":
    unittest.main()
