"""Допустимые импортёры `orchestrator/knowledge_cards.py` в пакете оркестратора.

Статический разбор исходников пакета `orchestrator/` (AST, без импорта):
модуль карточек знаний вправе импортировать только `notes.py`, `artel.py`,
`role_prompt.py`, `suite_lock.py` и `advance_gates/tests_writing.py` —
любой другой модуль пакета (бриф, гейты, команды ролей) его не трогает.

Группа: долгоживущий
Красен до реализации: файла orchestrator/knowledge_cards.py ещё нет — проверка существования модуля падает.
"""
import ast
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "orchestrator"
MODULE = "knowledge_cards"
ALLOWED = {"notes.py", "artel.py", "role_prompt.py", "suite_lock.py",
           "advance_gates/tests_writing.py"}


def imports_module(source: str, rel: str) -> bool:
    """Исходник модуля пакета `rel` импортирует `knowledge_cards` — любой
    формой: абсолютной, относительной, на верхнем уровне или в функции."""
    depth = rel.count("/")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            if any(alias.name == f"orchestrator.{MODULE}"
                   or alias.name.startswith(f"orchestrator.{MODULE}.")
                   for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = {alias.name for alias in node.names}
            if node.level == 0:
                if module == f"orchestrator.{MODULE}" or (
                        module == "orchestrator" and MODULE in names):
                    return True
            elif node.level == depth + 1:
                if module == MODULE or (module == "" and MODULE in names):
                    return True
    return False


def importers() -> set:
    found = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        rel = path.relative_to(PACKAGE).as_posix()
        if rel == f"{MODULE}.py":
            continue
        if imports_module(path.read_text(encoding="utf-8"), rel):
            found.add(rel)
    return found


class ImportersTest(unittest.TestCase):

    def test_ac15_only_allowed_modules_import_knowledge_cards(self):
        """Модуль `knowledge_cards.py` есть, и его импортируют только модули
        перечня допустимых импортёров.

        Ловит мутацию: бриф (`brief.py`) или гейт импортирует
        `knowledge_cards` (в том числе внутри функции) — импортёр вне
        перечня назван в провале.
        """
        self.assertTrue((PACKAGE / f"{MODULE}.py").is_file(),
                        "orchestrator/knowledge_cards.py нет")
        extra = importers() - ALLOWED
        self.assertEqual(extra, set(), f"недопустимые импортёры: {sorted(extra)}")


if __name__ == "__main__":
    unittest.main()
