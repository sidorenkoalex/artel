"""Зелёный с рождения: страховка от тавтологичной реализации, а не тест
НОВОГО поведения этой задачи — обратная сторона фикстуры AC-1..AC-4
(`test_ac1_ac2_ac3_ac4_pull_plank_resolves_branch_code.py` рядом): та же
планка, резолвящая `orchestrator/` от `__file__`, красная СЕГОДНЯ (кодовая
ветка задачи не несёт нового поведения, `ModuleNotFoundError` внутри
планки — тот же смысл, что «main/устаревшая копия» в тексте AC-7), и
обязана остаться красной ПОСЛЕ правки задачи тоже: правка регрессии №14
чинит материализацию/`cwd` прогона, а не то, что планка проверяет по
существу. Без этого теста AC-1..AC-4 доказывали бы только «переход не
падает», не «переход зависит от содержимого планки» — реализация,
всегда возвращающая `"pulled"` независимо от исхода `acceptance.run`,
прошла бы их незамеченной.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (BranchWithoutNewBehaviorSandbox,  # noqa: E402
                      MARKER_TEST_VIA_FILE)


class Ac7FixtureRednessWithoutNewBehaviorTest(BranchWithoutNewBehaviorSandbox):

    def test_ac7_red_when_code_branch_lacks_the_new_behavior(self):
        """Планка «через __file__» ищет `orchestrator.marker.value() ==
        "new"` — кодовая ветка задачи её не несёт (симулирует «main/
        устаревшая копия» из текста AC-7): переход обязан остаться
        красным (`"escalated"`), не пройти молчаливо.
        """
        self.commit_marker_plank({"test_via_file.py": MARKER_TEST_VIA_FILE})

        outcome = self.pull()

        self.assertEqual(
            outcome, "escalated",
            f"журнал: {self.journal_details()}")
        self.assertEqual(self.state(), "escalated")


if __name__ == "__main__":
    unittest.main()
