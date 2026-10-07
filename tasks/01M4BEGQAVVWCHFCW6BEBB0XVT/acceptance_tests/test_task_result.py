"""Разовые факты задачи: границы гейта мержа и приложение к правилу роли.

Группа: разовый
Красен до реализации: PLAN с приложением ещё не создан разработчиком.
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import apply_check, artifact_text


class TaskResultTest(unittest.TestCase):
    def test_ac8_plan_appendix_replaces_developer_suite_rule(self):
        """PLAN приносит применимый патч с новым порядком прогонов роли.

        Ловит мутацию: старое указание `suite-run` как штатного пути шага
        осталось в добавленном тексте либо из правила исчез повтор `--failed`.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "разработчик ещё не подготовил PLAN")
        blocks = re.findall(r"```diff\n(.*?)\n```", plan, flags=re.S)
        patches = [block + "\n" for block in blocks
                   if "diff --git a/skills/coding-standards.md " in block]
        self.assertTrue(patches, "нет приложения для skills/coding-standards.md")
        for patch in patches:
            self.assertTrue(apply_check(patch) == "" or
                            apply_check(patch, reverse=True) == "",
                            "приложение не применяется и не лежит в дереве")
        added = "\n".join(line[1:] for patch in patches
                          for line in patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
        for phrase in ("полный набор", "CI", "гейт", "планк", "затронут",
                       "упавш", "suite-run", "--failed"):
            self.assertIn(phrase, added.lower() if phrase.islower() else added)
        self.assertRegex(added, r"не запуск|не гон")
        self.assertNotRegex(added, r"suite-run\s+<id>(?!\s+--failed)")


# AC-7: manual — эквивалентность поведения на всех входах не имеет конечного тестового оракула.
# Оператор сравнивает дифф гейта мержа и наложения PLAN.
# AC-9: manual — смысловое ослабление существующих тестов нельзя определить детерминированно по диффу.
# Сценарии CI и локального прогона покрыты AC-1–AC-6
# с подменённым gh, а Оператор проверяет сохранность прежних тестов.
