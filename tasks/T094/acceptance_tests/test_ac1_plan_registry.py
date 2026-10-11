"""Приёмочный тест T094 — AC-1 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-1: «PLAN.md задачи, реализующей это SPEC, первым разделом содержит
реестр точек чтения артефактов из кодовой ветки, покрывающий как
минимум хэш-фиксацию гейтов, лок acceptance_tests, ветко-корректные
чтения, guard в CI и coldstart, с планом перенаправления каждого пункта
на артефактную ветку пульта.»

Красен до реализации: `tasks/T094/PLAN.md` пишет разработчик на шаге
`in_dev` — на момент написания этого теста (роль test_author, шаг
`tests_writing`) файла ещё нет, и первая же проверка (`assertTrue(
PLAN_PATH.exists())`) обязана падать. Как только разработчик добавит
PLAN.md, тест начинает проверять форму и содержимое его ПЕРВОГО
раздела — придуманного минимума требования 1, не более.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = REPO_ROOT / "tasks" / "T094" / "PLAN.md"

# Каждый пункт — список ключевых слов; пункт засчитан, если В ПЕРВОМ
# РАЗДЕЛЕ встречается хотя бы одно слово из его списка (регистр не
# важен) — формулировку регистра оставляем разработчику, требование 1
# не диктует точный текст.
REQUIRED_ITEMS = {
    "хэш-фиксация гейтов": ("хэш-фиксац", "фиксаци"),
    "лок acceptance_tests": ("acceptance_tests",),
    "ветко-корректные чтения": ("ветко-корректн",),
    "guard в CI": ("guard",),
    "coldstart": ("coldstart", "холодный старт", "холодного старта"),
}

REDIRECT_KEYWORDS = ("перенаправ", "артефактн")


def _first_section(text: str) -> str:
    """Текст ПЕРВОГО `##`-раздела PLAN.md (между заголовком документа и
    следующим `## `), либо весь текст после frontmatter, если разделов
    ещё нет вовсе."""
    body = re.sub(r"^---.*?---\s*", "", text, count=1, flags=re.DOTALL)
    parts = re.split(r"\n## ", body)
    # parts[0] — преамбула/заголовок `# PLAN: ...` до первого `## `;
    # parts[1], если есть, — тело первого именованного раздела.
    return parts[1] if len(parts) > 1 else parts[0]


class Ac1PlanRegistryTest(unittest.TestCase):

    def test_ac1_plan_first_section_is_a_registry_covering_the_minimum(self):
        self.assertTrue(
            PLAN_PATH.exists(),
            "tasks/T094/PLAN.md отсутствует — AC-1 требует реестр точек "
            "чтения первым разделом PLAN.md")
        text = PLAN_PATH.read_text(encoding="utf-8")
        section = _first_section(text).lower()

        missing = [
            label for label, keywords in REQUIRED_ITEMS.items()
            if not any(kw in section for kw in keywords)
        ]
        self.assertEqual(
            missing, [],
            f"первый раздел PLAN.md не упоминает пункты минимума "
            f"требования 1: {missing}")

        self.assertTrue(
            any(kw in section for kw in REDIRECT_KEYWORDS),
            "первый раздел PLAN.md не несёт плана перенаправления "
            "точек чтения на артефактную ветку пульта (AC-1)")


if __name__ == "__main__":
    unittest.main()
