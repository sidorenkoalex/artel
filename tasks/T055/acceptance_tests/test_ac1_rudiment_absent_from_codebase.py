"""AC-1 (tasks/T055/SPEC.md): `_seed_uncommitted_artifacts` отсутствует в
кодовой базе; grep по имени `_seed_uncommitted_artifacts` по репозиторию —
ноль вхождений.

Сканируется сама кодовая база — `orchestrator/` (требования 1, 2: функция
и её вызов) и `tests/` (требование 6: тест-спутник рудимента удаляется
целиком). Каталоги `tasks/` и `docs/` из скана сознательно исключены: имя
рудимента там законно остаётся историческим текстом — находка аудита
(docs/audits/code-revision-2026-08-28.md), собственные ТЗ/SPEC этой
задачи и более ранний tasks/T045/PLAN.md, назвавший функцию до этой
задачи. Их правка не входит в T055 (требование 5: правки — только
в orchestrator/workspace.py).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import workspace  # noqa: E402

REMOVED_NAME = "_seed_uncommitted_artifacts"
SCAN_DIRS = ("orchestrator", "tests")


class RudimentAbsentFromCodebaseTest(unittest.TestCase):

    def test_ac1_name_has_zero_occurrences_in_orchestrator_and_tests(self):
        offenders = []
        for rel in SCAN_DIRS:
            for path in sorted((REPO_ROOT / rel).rglob("*.py")):
                text = path.read_text(encoding="utf-8")
                if REMOVED_NAME in text:
                    offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(
            offenders, [],
            f"имя {REMOVED_NAME} обязано отсутствовать в orchestrator/ и "
            f"tests/, найдено в: {offenders}")

    def test_ac1_workspace_module_has_no_such_attribute(self):
        self.assertFalse(
            hasattr(workspace, REMOVED_NAME),
            f"orchestrator.workspace обязан не содержать атрибут "
            f"{REMOVED_NAME}")


if __name__ == "__main__":
    unittest.main()
