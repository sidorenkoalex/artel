"""AC-15: приложения PLAN.md к `skills/spec-authoring.md` и `templates/SPEC.md`.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё нет — в ссылке документов читать нечего.

PLAN.md читается из ссылки документов задачи помощником пульта
(`artifact_text`), приложения разбираются тем же узлом, что гейт
применимости (`scripts/guard.py::plan_appendices`), применимость — `apply_check`
помощника к дереву HEAD кодовой ветки (защищённые пути задача не меняет,
их дерево равно `main`). Приложение, уже наложенное к моменту прогона
(Оператор применил его отдельным MR, ветка подтянула main), засчитывается
обратной проверкой.

Валидация стабом: `artifact_text` временно подменён текстом PLAN.md с двумя
блоками ```diff, снятыми `git diff` правки скила и шаблона, — тесты
позеленели; без подмены красны.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))

from scripts import guard  # noqa: E402

SKILL = "skills/spec-authoring.md"
TEMPLATE = "templates/SPEC.md"
SECTION = "## Обоснование зависимостей мержа"


def added_text(diff: str) -> str:
    """Добавленные строки диффа (без `+++`), склеенные переводом строки."""
    return "\n".join(line[1:] for line in diff.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))


class PlanAppendicesTest(unittest.TestCase):

    def setUp(self):
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md нет в ссылке документов задачи")
        self.appendices, self.errors = guard.plan_appendices(plan)

    def appendix(self, path: str):
        mine = [a for a in self.appendices if path in a.paths]
        self.assertTrue(mine, f"в PLAN.md нет приложения к {path}; ошибки "
                              f"разбора: {self.errors}")
        return mine[0]

    def test_ac15_appendices_pass_git_apply_check(self):
        """Оба приложения проходят `git apply --check` на дереве `main`.

        Сценарий: приложения к `skills/spec-authoring.md` и
        `templates/SPEC.md` из PLAN.md; `apply_check` каждого пуст (git
        согласен) либо пуста обратная проверка — правка уже в дереве.

        Ловит мутацию: хедер хунка приложения не совпадает с реальным
        диапазоном строк файла либо контекст снят с устаревшей версии —
        `git apply --check` отказывает в обе стороны.
        """
        for path in (SKILL, TEMPLATE):
            with self.subTest(path=path):
                diff = self.appendix(path).diff
                forward = apply_check(diff)
                backward = apply_check(diff, reverse=True)

                self.assertTrue(forward == "" or backward == "",
                                f"{path}: git apply --check: {forward}")

    def test_ac15_skill_appendix_states_the_rule(self):
        """Добавленный текст скила несёт «все без исключения», «снять может только Оператор» и раздел обоснования.

        Сценарий: добавленные строки приложения к
        `skills/spec-authoring.md` содержат «все без исключения», фразу о
        снятии заявленной только Оператором и название раздела
        `## Обоснование зависимостей мержа`.

        Ловит мутацию: приложение называет раздел обоснования, но не
        запрещает аналитику терять заявленные (нет «все без исключения» или
        «только Оператор») — проверка называет пропуск.
        """
        text = added_text(self.appendix(SKILL).diff)

        self.assertRegex(text, re.compile(r"все\s+без\s+исключения", re.I))
        self.assertRegex(text, re.compile(r"сня\w*.{0,80}?только\s+Оператор",
                                          re.I | re.S))
        self.assertIn(SECTION, text)


if __name__ == "__main__":
    unittest.main()
