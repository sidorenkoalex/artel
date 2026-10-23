"""Тринадцать определений пульта без обращений удалены и не возвращаются.

Группа: долгоживущий
Красен до реализации: все тринадцать определений ещё на месте — `hasattr` истинен по каждой паре, а `retro_path` ещё обращается к `retro_rel_path`.

Держит два свойства кода пульта (ревизия кода 22.10, находка
CR-2026-10-22-12): тринадцати имён нет среди атрибутов их модулей, и ни
один `*.py` под `orchestrator/` и `scripts/` к ним не обращается — возврат
мёртвого определения или висячая ссылка на удалённое имя красит тест.
"""
import ast
import importlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Пары «модуль — имя»: модуль задаётся именем импорта; модуль
# `scripts/core_reference.py` импортируется как `from scripts import
# core_reference` — тем же путём, что `scripts.core_reference`.
REMOVED = (
    ("orchestrator.advance_gates.spec_audit", "answer_names"),
    ("orchestrator.advance_gates.test_integrity", "assertion_observation"),
    ("orchestrator.fixation", "external_code_sha"),
    ("orchestrator.gitcmd", "is_clean"),
    ("orchestrator.merge_after", "has_mandate_line"),
    ("orchestrator.pool_seal", "guids_path"),
    ("orchestrator.retro", "retro_path"),
    ("orchestrator.retro_corpus", "read_cache"),
    ("orchestrator.rounds", "task_rounds"),
    ("orchestrator.models", "VERDICT_APPROVED"),
    ("scripts.core_reference", "SETTING_KEYS"),
    ("scripts.core_reference", "SHA_HEX"),
    ("orchestrator.retro", "retro_rel_path"),
)
REMOVED_NAMES = frozenset(name for _, name in REMOVED)
SCANNED_DIRS = ("orchestrator", "scripts")


def references(tree: ast.AST, names: frozenset) -> list:
    """(строка, имя) каждого обращения к `names` в дереве: чтение имени
    (`ast.Name` в контексте `ast.Load`), атрибут (`ast.Attribute.attr`) и
    импорт (`ast.alias.name`). Цели присваиваний (`ast.Store`), определения
    функций и строковые константы обращениями не считаются."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            hit = node.id
        elif isinstance(node, ast.Attribute):
            hit = node.attr
        elif isinstance(node, ast.alias):
            hit = node.name
        else:
            continue
        if hit in names:
            found.append((getattr(node, "lineno", 0), hit))
    return found


class RemovedDefinitionsTest(unittest.TestCase):

    def test_ac1_removed_names_absent_from_modules(self):
        """Каждый из модулей импортируется, и удалённого имени среди его атрибутов нет.

        Перебор всех тринадцати пар через `subTest`: модуль импортируется
        `importlib.import_module` (для `scripts/core_reference.py` — пакетом
        `scripts`, как `from scripts import core_reference`), затем
        `hasattr(модуль, имя)` обязан быть ложным; текст отказа называет
        модуль и имя.

        Ловит мутацию: возврат любого из удалённых определений — например,
        `def is_clean(...)` снова в `orchestrator/gitcmd.py` или константа
        `VERDICT_APPROVED = "approved"` снова в `orchestrator/models.py` —
        `hasattr` по этой паре становится истинным, тест краснеет с именем
        модуля и имени.
        """
        for module_name, name in REMOVED:
            with self.subTest(module=module_name, name=name):
                module = importlib.import_module(module_name)
                self.assertFalse(
                    hasattr(module, name),
                    f"{module_name}: определение {name} не удалено "
                    f"(hasattr({module_name}, {name!r}) истинен)")

    def test_ac2_no_references_in_orchestrator_and_scripts(self):
        """Разбор AST каждого `*.py` под `orchestrator/` и `scripts/` не находит обращений к тринадцати именам.

        Обращение — чтение имени (`ast.Name`, `ast.Load`), атрибут с таким
        `attr` или импорт `ast.alias` с таким `name`; определения функций,
        цели присваиваний и строки не учитываются. Отказ перечисляет
        файл, строку и имя каждого обращения.

        Ловит мутацию: обращение к удалённому имени в `orchestrator/` или
        `scripts/` — например, оставленный вызов `retro_rel_path(task_id)`
        или `gitcmd.is_clean()` в коде пульта — разбор находит его, и тест
        краснеет с файлом и строкой.
        """
        files = sorted(p for d in SCANNED_DIRS for p in (ROOT / d).rglob("*.py")
                       if "__pycache__" not in p.parts)
        self.assertGreater(len(files), 10,
                           f"под {SCANNED_DIRS} не найдено модулей — неверный корень {ROOT}")
        dangling = []
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for line, name in references(tree, REMOVED_NAMES):
                dangling.append(f"{path.relative_to(ROOT).as_posix()}:{line}: {name}")
        self.assertEqual(dangling, [],
                         "обращения к удалённым определениям:\n" + "\n".join(dangling))


if __name__ == "__main__":
    unittest.main()
