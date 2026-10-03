"""Кода репозитория фиксации области проекта в `orchestrator/` больше нет.

Группа: разовый

Красен до реализации: `fixation._fix_external`, `fixation._read_external` и `projects.init_artifact_repo` ещё определены, а `projects.cmd_target_init` зовёт `init_artifact_repo`.

Группа «разовый»: предмет — удаление конкретных имён этой задачей (разница
с базой ветки); после мержа их отсутствие сторожить незачем.

Разбор — AST всех `orchestrator/**/*.py` рабочей копии кода, в которую
выложена планка (`Path(__file__).parents[3]`): определения функций с этими
именами и любые обращения к ним (имя, атрибут, импорт). Упоминания в
комментариях и докстрингах не считаются — критерий говорит о функциях и
вызовах.
"""
import ast
import importlib
import unittest

from _plank import CODE_ROOT

REMOVED = {
    "fixation": ("_fix_external", "_read_external"),
    "projects": ("init_artifact_repo",),
}
ALL_NAMES = {name for names in REMOVED.values() for name in names}


def definitions_and_uses() -> tuple[list, list]:
    """([(файл, строка, имя)] определений, [(файл, строка, имя)] обращений)
    удаляемых функций во всём `orchestrator/`."""
    defs, uses = [], []
    for path in sorted((CODE_ROOT / "orchestrator").rglob("*.py")):
        rel = path.relative_to(CODE_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in ALL_NAMES:
                    defs.append((rel, node.lineno, node.name))
            elif isinstance(node, ast.Attribute) and node.attr in ALL_NAMES:
                uses.append((rel, node.lineno, node.attr))
            elif isinstance(node, ast.Name) and node.id in ALL_NAMES:
                uses.append((rel, node.lineno, node.id))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in ALL_NAMES:
                        uses.append((rel, node.lineno, alias.name))
    return defs, uses


class FixationRepoCodeRemovedTest(unittest.TestCase):

    def test_ac3_no_definitions_of_removed_functions(self):
        """Ни модуль, ни AST `orchestrator/` не несут определений `_fix_external`, `_read_external`, `init_artifact_repo`.

        Сценарий: импорт `orchestrator.fixation` и `orchestrator.projects`
        — атрибутов с этими именами нет; обход AST всех модулей пакета —
        определений функций с этими именами нет нигде (в том числе
        перенесённых в другой модуль).

        Ловит мутацию: функции оставлены «на всякий случай» без вызовов
        (или перенесены под тем же именем в соседний модуль) — атрибут
        модуля или определение в AST находится.
        """
        for module, names in REMOVED.items():
            mod = importlib.import_module(f"orchestrator.{module}")
            for name in names:
                self.assertFalse(hasattr(mod, name),
                                 f"orchestrator.{module}.{name} всё ещё есть")
        defs, _uses = definitions_and_uses()
        self.assertEqual(defs, [], f"определения удаляемых функций: {defs}")

    def test_ac3_no_calls_of_removed_functions(self):
        """В `orchestrator/` нет обращений к `_fix_external`, `_read_external`, `init_artifact_repo`.

        Сценарий: обход AST всех модулей пакета — ни имени, ни атрибута, ни
        импорта с этими именами (упоминания в тексте комментариев и
        докстрингов не в счёт).

        Ловит мутацию: потребитель удалённой функции оставлен
        (`projects.cmd_target_init` по-прежнему зовёт
        `init_artifact_repo`) — обращение находится в AST.
        """
        _defs, uses = definitions_and_uses()
        self.assertEqual(uses, [], f"обращения к удаляемым функциям: {uses}")


if __name__ == "__main__":
    unittest.main()
