"""AC-1 (tasks/T075/SPEC.md): `templates/ANSWER.md` существует и несёт
frontmatter (как минимум `task`, `type: answer`, `author_role: operator`,
`status`, `schema_version`); `scripts/guard.py`, прогнанный на файле вида
`tasks/<id>/ANSWER-n.md`, построенном по этому шаблону, не даёт
структурных нарушений.

Красен до реализации: на момент написания теста `templates/ANSWER.md` не
существует (`ls templates/` — PLAN.md, QUESTIONS.md, REVIEW.md, SPEC.md,
TEST_REPORT.md, без ANSWER.md), и `scripts/guard.py::RULES` (строки
36-68) не несёт ключа `"answer"` — оба факта проверены на HEAD этой
задачи перед написанием теста. Тест обязан упасть на первой же проверке
(`assertTrue(template_path.exists())`) и остаться красным, пока
разработчик не добавит и файл, и запись в `RULES`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import yamlmini  # noqa: E402
from scripts import guard  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]

REQUIRED_FIELDS = ("task", "type", "author_role", "status", "schema_version")


class AnswerTemplateExistsTest(unittest.TestCase):

    def test_ac1_answer_template_exists_with_required_frontmatter(self):
        template_path = REPO_ROOT / "templates" / "ANSWER.md"

        self.assertTrue(
            template_path.exists(),
            "templates/ANSWER.md обязан существовать (SPEC T075 AC-1)")

        text = template_path.read_text(encoding="utf-8")
        meta = yamlmini.frontmatter(text)
        self.assertIsNotNone(
            meta, "templates/ANSWER.md обязан нести frontmatter (--- ... ---)")

        missing = [f for f in REQUIRED_FIELDS if f not in meta]
        self.assertEqual(
            missing, [],
            f"templates/ANSWER.md: frontmatter без полей {missing} (SPEC "
            f"AC-1 требует как минимум {REQUIRED_FIELDS})")
        self.assertEqual(
            meta.get("type"), "answer",
            "templates/ANSWER.md обязан нести type: answer (SPEC AC-1)")
        self.assertEqual(
            meta.get("author_role"), "operator",
            "templates/ANSWER.md обязан нести author_role: operator "
            "(SPEC AC-1)")


class AnswerTemplateGuardAcceptsBuiltFileTest(unittest.TestCase):

    def test_ac1_guard_accepts_file_built_from_the_template(self):
        template_path = REPO_ROOT / "templates" / "ANSWER.md"
        if not template_path.exists():
            self.skipTest("templates/ANSWER.md отсутствует — см. первый "
                          "тест этого файла (SPEC AC-1)")
        text = template_path.read_text(encoding="utf-8")

        # Файл вида tasks/<id>/ANSWER-n.md, построенный по шаблону: только
        # плейсхолдер задачи заполняется конкретным значением (тот же
        # приём, что guard.py применяет к остальным типам — "task:
        # TASK_ID" сам по себе невалиден, guard.py:368-369) — остальное
        # содержимое (секции тела, статус по умолчанию) — решение
        # разработчика/шаблона, тест не подставляет предположений о нём.
        built = text.replace("task: TASK_ID", "task: T999", 1)

        errors = guard.check_content("tasks/T999/ANSWER-1.md", built)

        self.assertEqual(
            errors, [],
            f"guard.py обязан не давать структурных нарушений на файле, "
            f"построенном из templates/ANSWER.md (SPEC AC-1): {errors}")


if __name__ == "__main__":
    unittest.main()
