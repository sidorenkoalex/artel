"""Приёмочные тесты T046 — секция «Предложения системе» в PLAN.md/REVIEW.md
(SPEC.md, AC-1..AC-5).

AC-1 и AC-3 называют содержимое `templates/` и `skills/` — оба защищённые
пути (SPEC, требование 4): исполнитель НЕ коммитит правки этих путей в
ветку задачи напрямую, а готовит их как дифф, приложенный к PLAN.md;
финальный коммит в сами файлы делает Оператор отдельным MR. Поэтому в
момент прогона этого набора (гейты текущей ветки задачи) живые файлы
`templates/PLAN.md`, `templates/REVIEW.md` и `skills/*.md` содержимого
секции нести не будут — это не баг реализации, а прямое следствие
требования 4. Проверить итоговое содержимое этих файлов автоматически на
этой стадии невозможно (оно появится только после отдельного MR
Оператора); отсюда `manual`, а не тест и не `skip` (см. test-authoring:
`skip` — «не проверяем сейчас», `manual` — «проверяет Оператор на
приёмке», что здесь буквально так — приёмка диффа Оператором).
"""

# AC-1: manual — templates/PLAN.md и templates/REVIEW.md защищены (SPEC,
# требование 4): исполнитель готовит текст правки как дифф в PLAN.md, не
# коммитит его в templates/ в этой ветке. Живые файлы шаблонов получат
# секцию только после отдельного MR Оператора по этому диффу — до этого
# момента автоматическая проверка содержимого templates/*.md недостижима
# в рамках задачи. Оператор проверяет соответствие диффа AC-1 при приёмке
# самого MR в templates/.

# AC-3: manual — тем же основанием, что AC-1: skills/*.md — защищённый
# путь (SPEC, требование 4), правка готовится как дифф в PLAN.md и
# коммитится в skills/ только Оператором отдельным MR. Содержимое живого
# skills/*.md на момент прогона этого набора абзаца не несёт; Оператор
# проверяет его при приёмке того MR.

# AC-4: skip — «существующий набор тестов tests/ зелёный» уже исполняется
# штатным CI-гейтом на каждом коммите ветки задачи и требуется merge_gate
# (orchestrator/fsm.py, cmd_approve при state == "merge_gate") — тем же
# основанием, что tasks/T045/acceptance_tests/test_ac10_full_suite_
# regression.py (AC-10 там сформулирован идентично). Дублирующий здесь
# subprocess-прогон всего tests/ не даёт новой гарантии сверх штатного
# гейта, только удлиняет приёмочный прогон этой задачи.

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

PROTECTED_PREFIXES = ("templates/", "skills/")


# ---------------------------------------------------------------------
# AC-2: guard.py принимает PLAN.md/REVIEW.md и с заполненной, и с
# пустой, и с отсутствующей секцией «Предложения системе» — во всех
# трёх случаях без нарушений по этой секции.
# ---------------------------------------------------------------------

PLAN_BASE = """---
task: T046
type: plan
author_role: developer
status: draft
schema_version: 2
---

# PLAN: тест секции «Предложения системе»

## Подход
Текст.

## Шаги
1. Шаг.

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Текст.
{section}"""

REVIEW_BASE = """---
task: T046
type: review
author_role: reviewer
status: draft
iteration: 1
schema_version: 2
---

# REVIEW: тест секции «Предложения системе»

## Соответствие SPEC
| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | |

## Замечания
- ...

## Вердикт
approved
{section}"""

SECTION_FILLED = """
## Предложения системе
- conventions-core.md: скил не упоминает X — механика натирает.
"""

SECTION_EMPTY = """
## Предложения системе
"""

SECTION_ABSENT = ""


class GuardAcceptsOptionalSectionTest(unittest.TestCase):
    """AC-2: заполненная/пустая/отсутствующая секция — все три валидны."""

    def test_ac2_filled_section_on_plan_is_valid(self):
        text = PLAN_BASE.format(section=SECTION_FILLED)
        errors = guard.check_content("PLAN.md", text)
        self.assertEqual(errors, [])

    def test_ac2_empty_section_on_plan_is_valid(self):
        text = PLAN_BASE.format(section=SECTION_EMPTY)
        errors = guard.check_content("PLAN.md", text)
        self.assertEqual(errors, [])

    def test_ac2_missing_section_on_plan_is_valid(self):
        text = PLAN_BASE.format(section=SECTION_ABSENT)
        errors = guard.check_content("PLAN.md", text)
        self.assertEqual(errors, [])

    def test_ac2_filled_section_on_review_is_valid(self):
        text = REVIEW_BASE.format(section=SECTION_FILLED)
        errors = guard.check_content("REVIEW.md", text)
        self.assertEqual(errors, [])

    def test_ac2_empty_section_on_review_is_valid(self):
        text = REVIEW_BASE.format(section=SECTION_EMPTY)
        errors = guard.check_content("REVIEW.md", text)
        self.assertEqual(errors, [])

    def test_ac2_missing_section_on_review_is_valid(self):
        text = REVIEW_BASE.format(section=SECTION_ABSENT)
        errors = guard.check_content("REVIEW.md", text)
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------
# AC-5: дифф задачи вне templates/ и skills/ не трогает эти пути; правки
# templates/ и skills/ оформлены отдельно — как подготовленный для
# Оператора дифф в PLAN.md, а не как прямой коммит в ветку задачи;
# порядок финального коммита Оператором по этому диффу описан в PLAN.md.
# ---------------------------------------------------------------------

DIFF_TARGET_RE = re.compile(
    r"(?:diff --git |--- |\+\+\+ |\*\*\* )(?:a/|b/)?"
    r"(templates/PLAN\.md|templates/REVIEW\.md|skills/[\w\-]+\.md)"
)


class ProtectedPathsTest(unittest.TestCase):
    """AC-5: реальный дифф ветки относительно main и текст PLAN.md
    задачи — без моков, по образцу
    tasks/T043/acceptance_tests/test_retro_protected_paths.py
    (`ProtectedPathsUntouchedTest`), сужено на templates/ и skills/
    (единственные защищённые пути, названные в AC-5 этой задачи)."""

    @staticmethod
    def _git(*args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def test_ac5_branch_diff_does_not_touch_protected_paths(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        offending = [p for p in changed if p.startswith(PROTECTED_PREFIXES)]
        self.assertEqual(
            offending, [],
            f"дифф ветки {branch} относительно main трогает защищённые "
            f"пути напрямую: {offending} (SPEC T046, требование 4 — эти "
            f"правки идут диффом в PLAN.md, не прямым коммитом)")

    def test_ac5_plan_attaches_diff_for_protected_paths(self):
        plan_path = REPO_ROOT / "tasks" / "T046" / "PLAN.md"
        self.assertTrue(
            plan_path.exists(),
            "tasks/T046/PLAN.md отсутствует — требование 4 обязывает "
            "приложить к нему подготовленный дифф правок templates/ и "
            "skills/")
        text = plan_path.read_text(encoding="utf-8")

        targets = set(DIFF_TARGET_RE.findall(text))

        self.assertIn(
            "templates/PLAN.md", targets,
            "PLAN.md не содержит диффа для templates/PLAN.md "
            "(ожидаются маркеры унифицированного диффа: 'diff --git', "
            "'--- ', '+++ ' с путём templates/PLAN.md)")
        self.assertIn(
            "templates/REVIEW.md", targets,
            "PLAN.md не содержит диффа для templates/REVIEW.md")
        self.assertTrue(
            any(t.startswith("skills/") for t in targets),
            "PLAN.md не содержит диффа ни для одного файла skills/ "
            "(требование 3 — хотя бы один скил роли)")

    def test_ac5_plan_describes_operator_commit_order(self):
        plan_path = REPO_ROOT / "tasks" / "T046" / "PLAN.md"
        self.assertTrue(
            plan_path.exists(),
            "tasks/T046/PLAN.md отсутствует — требование 4 обязывает "
            "описать в нём порядок финального коммита Оператором")
        text = plan_path.read_text(encoding="utf-8").lower()

        self.assertIn("оператор", text,
                      "PLAN.md не упоминает Оператора — а именно он по "
                      "требованию 4 коммитит подготовленный дифф")
        self.assertIn("коммит", text,
                      "PLAN.md не описывает коммит подготовленного диффа "
                      "Оператором (требование 4)")


if __name__ == "__main__":
    unittest.main()
