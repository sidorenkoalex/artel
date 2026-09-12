"""AC-10 (tasks/01M2ARQMTYRNPR5HRXAPCBAXNY/SPEC.md), сценарий (г):
классификация `ci_push_class.is_doc_path` относит корневой `README.md` к
документным, а `skills/x.md` — нет.

Красен до реализации: публичное имя `is_doc_path` в `scripts/
ci_push_class.py` ещё не заведено (сегодня только приватное
`_is_doc_path`) — обращение к нему падает `AttributeError` до первого
`assert`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import ci_push_class  # noqa: E402


class ReadmeVsSkillsClassificationTest(unittest.TestCase):

    def test_ac10_scenario_d_readme_is_doc_skills_md_is_not(self):
        """Корневой `README.md` (совпадает с `[^/]+\\.md$` — файл `*.md`
        без слеша в пути) — документный; `skills/x.md` (совпадает с
        каким-либо файлом `*.md`, но НЕ в корне и не под `docs/`/`tasks/`)
        — недокументный.

        Ловит мутацию: `_DOC_PATTERN`/`is_doc_path` подменены на
        безусловное «любой `*.md` документный» (потеря якоря `^` или
        замена `[^/]+\\.md$` на `.*\\.md$`) — `assertFalse` по
        `skills/x.md` покраснеет."""
        self.assertTrue(ci_push_class.is_doc_path("README.md"))
        self.assertFalse(ci_push_class.is_doc_path("skills/x.md"))


if __name__ == "__main__":
    unittest.main()
